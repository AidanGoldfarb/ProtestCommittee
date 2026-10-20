"""CLI: audit a Regattatron replay blob's flagged incidents.

Usage:  python audit.py <replay_blob.json> [boat_length_m]
"""
import sys, json
import committee as C
import rrs_geometry as g


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    blob = json.load(open(sys.argv[1]))
    boat_len = float(sys.argv[2]) if len(sys.argv) > 2 else g.DEFAULT_BOAT_LENGTH_M
    audits = C.audit_blob(blob, boat_len)

    print(f"Race {blob['raceId']}  | boat_len assumed = {boat_len} m")
    print(f"{len(audits)} flagged incident(s)\n")
    tally = {}
    for a in audits:
        tally[a.agreement] = tally.get(a.agreement, 0) + 1
        cp = f" vs {a.engine_counterparty}" if a.engine_counterparty else ""
        rule = a.engine_rule if a.engine_rule is not None else "-"
        print(f"[{a.agreement:12}] t={a.event_tMs:>8}ms idx={a.sample_idx:<4} "
              f"{a.engine_kind} rule {rule}: engine charged {a.engine_offender}{cp}")
        print(f"               committee: {a.note}")
        if a.verdict.basis:
            print(f"               basis: {a.verdict.basis}")
        print()
    print("summary:", tally)


if __name__ == "__main__":
    main()
