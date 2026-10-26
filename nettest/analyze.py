#!/usr/bin/env python3
"""Analyse one or more Regattatron capture files (from regattatron-capture.user.js or capture.js).

usage: python3 analyze.py capture1.json [capture2.json ...] [--ping ping.txt ...] [--period 15] [--hold-ms 300]

Per socket: state-frame rate, inter-arrival percentiles, late frames, bunching, server-tick
continuity, a table of every hold (gap > --hold-ms) with the burst that followed it, and a
periodic-hold test (phase binning over a --period second cycle plus a period scan 8-24 s).
Per disconnect: silence before the app gave up, close code, what the replacement socket did.
Across files: sockets in the same race are aligned by server tick, and each hold is marked as
seen by every client (server-side), by some, or by this client only (that client's path).
Optional --ping files are `ping --apple-time` logs from the same machine as the first capture.
"""
import argparse, json, re, statistics, sys
from bisect import bisect_left
from collections import Counter, defaultdict
from datetime import datetime

KIND = {1: "STATE_DELTA", 2: "WELCOME", 3: "WIND_UPDATE", 4: "PONG", 9: "other", 0: "other"}
NORMAL_CLOSE = {1000, 4041}          # 4041 = server "race-over"
BURST_WINDOW_MS = 120                # frames arriving this soon after a hold count as its flush


def fmt_t(ms):
    return datetime.fromtimestamp(ms / 1000).strftime("%H:%M:%S.%f")[:-3]


def pct(sv, p):
    return sv[min(len(sv) - 1, int(p * (len(sv) - 1)))] if sv else None


def race_id(url):
    m = re.search(r"/ws/race/([0-9a-f-]+)", url or "")
    return m.group(1)[:8] if m else ("lobby" if "/ws/lobby" in (url or "") else "?")


def load_ping(path):
    rows = []
    for line in open(path, errors="replace"):
        m = re.match(r"(\d+):(\d+):(\d+\.\d+).*time=([\d.]+)", line)
        if m:
            h, mi, s, t = m.groups()
            rows.append((int(h) * 3600 + int(mi) * 60 + float(s), float(t)))
    return rows


def local_secs(epoch_ms):
    d = datetime.fromtimestamp(epoch_ms / 1000)
    return d.hour * 3600 + d.minute * 60 + d.second + d.microsecond / 1e6


# ---------------------------------------------------------------------------
def socket_stats(s, hold_ms):
    fr = s["frames"]
    state = [f for f in fr if f[3] == 1]
    out = {"state": state, "n": len(fr)}
    if len(state) < 3:
        return out
    t = [f[0] for f in state]
    gaps = [t[i] - t[i - 1] for i in range(1, len(t))]
    out["t"] = t
    out["gaps"] = gaps
    out["dur_s"] = (t[-1] - t[0]) / 1000
    out["hz"] = (len(t) - 1) / out["dur_s"] if out["dur_s"] else 0
    out["bytes_avg"] = statistics.mean(f[2] for f in state)
    # holds: [t_before, gap_ms, frames_within_burst_window_after, tick_span_of_burst, tick_before]
    holds = []
    for i, g in enumerate(gaps):
        if g > hold_ms:
            j = i + 1
            k = j
            while k + 1 < len(t) and t[k + 1] - t[k] <= 15:
                k += 1
            burst = k - j + 1
            bt = [state[x][1] for x in range(j, k + 1) if state[x][1] >= 0]
            span = max(bt) - state[i][1] if bt and state[i][1] >= 0 else -1
            holds.append([t[i], g, burst, span, state[i][1]])
    out["holds"] = holds
    out["bunched"] = sum(1 for g in gaps if g < 15)
    ticks = [f[1] for f in state if f[1] >= 0]
    out["tick_deltas"] = Counter(ticks[i] - ticks[i - 1] for i in range(1, len(ticks)))
    return out


def phase_test(t, period_s, nbins=30):
    """Mean inter-arrival gap by phase within a period_s cycle (epoch-anchored), plus period scan."""
    if len(t) < 50:
        return None
    gaps = [(t[i - 1], t[i] - t[i - 1]) for i in range(1, len(t))]

    def bins_for(p_ms):
        acc = [[] for _ in range(nbins)]
        for t0, g in gaps:
            acc[int((t0 % p_ms) / p_ms * nbins)].append(g)
        means = [statistics.mean(b) if b else 0 for b in acc]
        return means

    means = bins_for(period_s * 1000)
    overall = statistics.mean(g for _, g in gaps)
    scan = []
    for p in [x / 2 for x in range(16, 49)]:  # 8.0 .. 24.0 s in 0.5 s steps
        m = bins_for(p * 1000)
        scan.append((max(m) / overall if overall else 0, p))
    scan.sort(reverse=True)
    return {"bins": means, "overall": overall, "peak_ratio": max(means) / overall if overall else 0,
            "best": scan[:3]}


def verdict(pt, holds, dur_s):
    if pt is None:
        return "too short to test"
    if pt["peak_ratio"] > 1.8 and holds:
        return f"PERIODIC HOLD (peak bin {pt['peak_ratio']:.1f}x mean, best period {pt['best'][0][1]:.1f} s)"
    if holds:
        return f"holds present but not periodic ({len(holds)} in {dur_s:.0f} s)"
    return "flat, no holds"


# ---------------------------------------------------------------------------
def report_disconnects(cap, sockets_by_id):
    evs = sorted(cap["events"], key=lambda e: e["at"])
    lines = []
    for i, e in enumerate(evs):
        if e["ev"] != "ws_close" or e.get("code") in NORMAL_CLOSE:
            continue
        s = sockets_by_id.get(e["id"])
        last = max((f[0] for f in s["frames"]), default=None) if s else None
        silence = f"{(e['at'] - last) / 1000:.1f} s after last frame" if last else "no frames received"
        app = [x for x in evs if x["ev"] == "app_close_called" and x.get("id") == e["id"] and x["at"] <= e["at"]]
        who = "app called close()" if app else "closed by peer/network"
        nxt = [x for x in evs[i + 1:] if x["ev"] in ("ws_open", "ws_close", "ws_error", "pagehide") and x["at"] - e["at"] < 15000]
        follow = "; ".join(f"{x['ev']}{'#' + str(x['id']) if 'id' in x else ''} +{(x['at'] - e['at']) / 1000:.1f}s"
                           + (f" code {x['code']}" if x['ev'] == 'ws_close' else "") for x in nxt[:4])
        lines.append(f"  {fmt_t(e['at'])} socket {e['id']} code {e.get('code')} {e.get('reason') or ''!s:<12} {silence}, {who}; then {follow or 'nothing'}")
    return lines


def analyse_file(path, args, pings):
    cap = json.load(open(path))
    print(f"\n######## {path}")
    print(f"capture v{cap.get('version')} started {fmt_t(cap['started'])}  tz {cap.get('tz', '?')}  ua {cap.get('ua', '')[:70]}")
    print(f"pages {len(cap['pages'])}, sockets {len(cap['sockets'])}, events {len(cap['events'])}")
    reloads = [p for p in cap["pages"] if p.get("navType") == "reload"]
    if reloads:
        print("  reloads: " + ", ".join(fmt_t(p["at"]) for p in reloads))
    by_id = {s["id"]: s for s in cap["sockets"]}
    dl = report_disconnects(cap, by_id)
    print(f"abnormal disconnects: {len(dl)}")
    for l in dl:
        print(l)
    spike_times = sorted(t for rows in pings for t, r in rows if r > 25)

    results = []
    for s in cap["sockets"]:
        st = socket_stats(s, args.hold_ms)
        rid = race_id(s["url"])
        print(f"\n=== socket {s['id']}  race {rid}  {s['url']}")
        print(f"    opened {s['opened'] and fmt_t(s['opened'])}  closed {s['closed'] and (fmt_t(s['closed']['at']) + ' code ' + str(s['closed']['code']))}")
        kinds = ", ".join(f"{k} {v}" for k, v in sorted(s["kinds"].items(), key=lambda kv: -kv[1]))
        print(f"    frames {st['n']} ({kinds}); sent {len(s['sent'])}")
        if "t" not in st:
            continue
        sg = sorted(st["gaps"])
        print(f"    duration {st['dur_s']:.0f} s, state rate {st['hz']:.2f} Hz, {st['bytes_avg']:.0f} B/frame, ~{8 * st['bytes_avg'] * st['hz'] / 1000:.0f} kbps")
        print(f"    inter-arrival ms: p50 {pct(sg, .5):.0f}  p90 {pct(sg, .9):.0f}  p99 {pct(sg, .99):.0f}  max {sg[-1]:.0f}")
        n = len(st["gaps"])
        print(f"    late frames: >150 ms {sum(1 for g in sg if g > 150)} ({100 * sum(1 for g in sg if g > 150) / n:.1f}%), "
              f">300 ms {sum(1 for g in sg if g > 300)}, >1000 ms {sum(1 for g in sg if g > 1000)}; "
              f"bunched (<15 ms after previous) {st['bunched']} ({100 * st['bunched'] / n:.1f}%)")
        td = dict(sorted(st["tick_deltas"].items())[:8])
        print(f"    server tick deltas: {td}  (5 = consecutive broadcasts; larger = frames missing)")
        sp = [x for x in s["spectators"] if x[1] >= 0 or x[2] >= 0]
        if sp:
            print(f"    spectators {sp[0][1]} -> {sp[-1][1]}, online {sp[0][2]} -> {sp[-1][2]}")
        if spike_times:
            near = 0
            for t0, g, *_ in st["holds"]:
                a = local_secs(t0)
                i = bisect_left(spike_times, a - 0.15)
                if i < len(spike_times) and spike_times[i] <= a + g / 1000 + 0.05:
                    near += 1
            print(f"    holds coinciding with a local ping spike: {near}/{len(st['holds'])}")
        pt = phase_test(st["t"], args.period)
        print(f"    verdict: {verdict(pt, st['holds'], st['dur_s'])}")
        if pt:
            print(f"    phase bins ({args.period} s cycle, {len(pt['bins'])} bins, mean gap ms): " + " ".join(f"{b:.0f}" for b in pt["bins"]))
            print("    period scan top: " + ", ".join(f"{p:.1f}s x{r:.2f}" for r, p in pt["best"]))
        if st["holds"]:
            print(f"    holds (> {args.hold_ms} ms):")
            print("      time_before      gap_ms  burst_frames  tick_span  local_phase_s  tick_phase_s")
            for t0, g, burst, span, tick in st["holds"][:40]:
                tp = ((tick * 20) % (args.period * 1000)) / 1000 if tick >= 0 else float('nan')
                print(f"      {fmt_t(t0)}  {g:6.0f}  {burst:12d}  {span:9d}  {(t0 % (args.period * 1000)) / 1000:13.2f}  {tp:12.2f}")
            if len(st["holds"]) > 40:
                print(f"      ... {len(st['holds']) - 40} more")
            note = "burst frames x5 == tick span -> frames were held then flushed, nothing lost" \
                if all(h[2] * 5 == h[3] for h in st["holds"] if h[3] >= 0) else \
                "burst does not account for all missing ticks -> some frames lost or sim fell behind"
            print(f"    reading: {note}")
        tk = [f[1] for f in st["state"] if f[1] >= 0]
        results.append({"file": path, "sock": s["id"], "race": rid, "holds": st["holds"], "state": st["state"],
                        "opened": s["opened"], "ticks": (min(tk), max(tk)) if tk else (0, -1)})
    return results


def cross_client(all_results, tol_ms):
    by_race = defaultdict(list)
    for r in all_results:
        if r["race"] not in ("?", "lobby") and r["state"]:
            by_race[r["race"]].append(r)
    for rid, socks in by_race.items():
        files = {r["file"] for r in socks}
        if len(files) < 2:
            continue
        print(f"\n######## cross-client alignment, race {rid}: {len(socks)} sockets from {len(files)} captures")
        # map every socket's holds to server tick (clock-independent) and compare
        tol = tol_ms // 20   # ticks (20 ms each) either side
        for r in socks:
            others = [o for o in socks if o["file"] != r["file"]]
            shared = alone = uncovered = partial = 0
            for h in r["holds"]:
                tick = h[4]
                covering = [o for o in others if o["ticks"][0] <= tick <= o["ticks"][1]]
                if not covering:
                    uncovered += 1
                    continue
                seen = 0
                for o in covering:
                    ot = sorted(x[4] for x in o["holds"])
                    i = bisect_left(ot, tick - tol)
                    if i < len(ot) and ot[i] <= tick + tol:
                        seen += 1
                if seen == len(covering):
                    shared += 1
                elif seen:
                    partial += 1
                else:
                    alone += 1
            print(f"  {r['file']} socket {r['sock']}: {len(r['holds'])} holds: {shared} seen by every other connected client, "
                  f"{partial} by some, {alone} only here, {uncovered} while no other client was connected")
        print("  reading: holds seen by every client at the same server tick are produced upstream of all of them (the race object);")
        print("           holds seen by one client only are on that client's path or machine.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("captures", nargs="+")
    ap.add_argument("--ping", action="append", default=[])
    ap.add_argument("--period", type=float, default=15.0, help="cycle length in s for the phase test")
    ap.add_argument("--hold-ms", type=int, default=300)
    ap.add_argument("--align-ms", type=int, default=1000)
    args = ap.parse_args()
    pings = []
    for p in args.ping:
        rows = load_ping(p)
        pings.append(rows)
        rtts = sorted(r for _, r in rows)
        if rtts:
            print(f"ping {p}: n={len(rtts)} median={pct(rtts, .5):.1f} p90={pct(rtts, .9):.1f} max={rtts[-1]:.1f} ms; "
                  f">25 ms: {sum(1 for r in rtts if r > 25)}")
    results = []
    for c in args.captures:
        results += analyse_file(c, args, pings)
    cross_client(results, args.align_ms)


if __name__ == "__main__":
    main()
