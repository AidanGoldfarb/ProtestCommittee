#!/usr/bin/env python3
"""Convert a Chrome DevTools HAR export (Network tab -> "Save all as HAR with content") into
the capture format that analyze.py reads (same as regattatron-capture.user.js v2).

usage: python3 har2capture.py in.har [in2.har ...] -o out.json [--label "name"]

Chrome records WebSocket frames in each socket entry's `_webSocketMessages` with a float
epoch `time`, `type` (send/receive) and the full `data`. Only timing, kind, tick, size and
boat count are kept; message bodies (which include chat) are dropped. Several HARs can be
merged into one output; identical sockets (same URL and first-frame time) are de-duplicated,
so exporting the same DevTools session three times yields one capture.
"""
import argparse, json, re
from datetime import datetime, timezone

KIND = {"STATE_DELTA": 1, "WELCOME": 2, "WIND_UPDATE": 3, "PONG": 4, "PING": 4}
K_RE = re.compile(r'"kind":"([A-Z_]+)"')
T_RE = re.compile(r'"tick":(\d+)')


def iso_ms(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


def convert(paths, label):
    out = {"version": 2, "script": "har2capture", "started": None, "ua": label or "chrome-devtools-har",
           "tz": "?", "pages": [], "sockets": [], "events": []}
    seen = {}
    for p in paths:
        har = json.load(open(p, encoding="utf-8"))["log"]
        for pg in har.get("pages", []):
            out["pages"].append({"at": iso_ms(pg["startedDateTime"]), "href": pg.get("title", ""), "navType": "har"})
        for e in har["entries"]:
            msgs = e.get("_webSocketMessages")
            if msgs is None:
                continue
            url = re.sub(r"\?.*", "", e["request"]["url"])
            created = iso_ms(e["startedDateTime"])
            key = (url, created)
            if key in seen:
                continue
            rec = {"id": len(out["sockets"]), "url": url, "page": "", "created": created, "opened": None,
                   "closed": None, "error": None, "frames": [], "sent": [], "spectators": [], "kinds": {},
                   "lastBoats": -1, "source": p.split("/")[-1]}
            seen[key] = rec
            last_sample = 0
            for m in msgs:
                t = int(round(float(m["time"]) * 1000))
                d = m.get("data", "")
                if m.get("opcode") not in (1, None):      # 1 = text frame; skip binary/control
                    continue
                if m["type"] == "send":
                    km = K_RE.search(d[:80])
                    rec["sent"].append([t, len(d), KIND.get(km.group(1), 9) if km else 9])
                    continue
                if rec["opened"] is None:
                    rec["opened"] = t
                kind, tick = 9, -1
                if d.startswith("{"):
                    km = K_RE.search(d[:80])
                    k = km.group(1) if km else "OTHER"
                    rec["kinds"][k] = rec["kinds"].get(k, 0) + 1
                    kind = KIND.get(k, 9)
                    if kind == 1:
                        tm = T_RE.search(d[:160])
                        if tm:
                            tick = int(tm.group(1))
                        n = d.count('"ocs":')
                        if n:
                            rec["lastBoats"] = n
                rec["frames"].append([t, tick, len(d), kind])
                if t - last_sample >= 10000:
                    rec["spectators"].append([t, -1, -1, "har", rec["lastBoats"]])
                    last_sample = t
            if rec["frames"]:
                last = rec["frames"][-1][0]
                rec["closed"] = {"at": last, "code": -1, "reason": "end of HAR", "clean": True, "frames": len(rec["frames"])}
            out["sockets"].append(rec)
            out["events"].append({"at": created, "ev": "ws_create", "id": rec["id"]})
            if rec["opened"]:
                out["events"].append({"at": rec["opened"], "ev": "ws_open", "id": rec["id"]})
    out["sockets"].sort(key=lambda s: s["created"])
    for i, s in enumerate(out["sockets"]):
        s["id"] = i
    out["started"] = min((s["created"] for s in out["sockets"]), default=0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hars", nargs="+")
    ap.add_argument("-o", required=True)
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    out = convert(a.hars, a.label)
    json.dump(out, open(a.o, "w"))
    for s in out["sockets"]:
        print(f"socket {s['id']} {s['url'][-40:]} frames {len(s['frames'])} sent {len(s['sent'])} "
              f"{datetime.fromtimestamp(s['opened'] / 1000) if s['opened'] else '-'} .. "
              f"{datetime.fromtimestamp(s['closed']['at'] / 1000) if s['closed'] else '-'}  from {s['source']}")
    print(f"wrote {a.o}: {len(out['sockets'])} sockets")


if __name__ == "__main__":
    main()
