# ProtestCommittee — project context

A deterministic "protest committee": it reconstructs a sailing-racing incident
from a Regattatron replay, independently applies the Racing Rules of Sailing
(RRS 2025–2028), and audits the game's own rules engine. It is an **auditor**,
not a trained model and not a replacement engine — verdicts must cite the rule
and the facts, so the core is symbolic geometry, not ML.

## Layout
- `rrs_geometry.py` — pure RRS predicates (tack, windward/leeward, overlap /
  clear-astern, line side, bow reference). No I/O.
- `committee.py` — rule assessors (10, 11, 12, 22) + the audit orchestration.
- `audit.py` — CLI: `python audit.py <replay_blob.json> [boat_length_m]`.
- `test_protest.py` — synthetic verification suite (the oracle) + optional
  real-data corroboration. Run: `pytest -q`.
- `PROTEST_COMMITTEE_METHODOLOGY.md` — the full runbook: how replays are fetched
  and analyzed, conventions, what is/ isn't adjudicable, verification, limits,
  and the improvement backlog. **Read this first.**
- `README.md` — short public overview (rule coverage table, sample result).
  It repeats the conventions and file table; the methodology is the source of
  truth. When conventions change, update all three documents together.
- `references/` — rulebook/casebook material. `APPENDIX_M_principles.md` is
  committed. The World Sailing Case Book files are **not** committed (copyright);
  build them locally with `references/build_casebook.py`.

## Conventions (verified from data — see methodology §3; do not re-guess)
- Positions in metres, `+y` upwind. `hdg`/`w` are compass degrees (0=+y, cw).
- `w` is the wind's FROM direction. `(x,y)` is the hull centroid; judge
  lines/marks at the bow (`centroid + L/2`). Hull length `L ≈ 33.6 m` is inferred
  from `zoneRadiusM/3` and should be confirmed with the game's author.
- Replay is ~1 Hz: sub-second turn-order / exact-contact questions are below
  resolution — emit "indeterminate at replay resolution" rather than forcing a
  verdict.

## Working rules for this repo
- Every verdict cites the rule(s) **and** the on-point World Sailing Case
  number(s) (methodology §0.1, §5.3), with numeric facts and stated assumptions.
- The game engine is **never** the correctness oracle (it is what we audit).
  Verify against synthetic cases and hand-labelled incidents only.
- Do not commit World Sailing copyrighted files (the Case Book PDF / its full
  parsed text). The `.gitignore` already excludes them.

## Status / next steps (methodology §9)
1. Window-based assessors for Rules 13/15/16/17/18 (biggest gap; most incidents
   are sequence-dependent).
2. Contact module once hull length/beam are known → unlocks Rules 14 and 31.
3. Position module using along-course progress (not closest-approach — that
   metric mis-scores overstanding boats).
4. Rule 44.1(b) "gained advantage despite penalty" screen.
5. Batch audit across many races (needs a bulk replay export).
