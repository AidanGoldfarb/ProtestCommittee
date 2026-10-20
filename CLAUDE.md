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
- `past_rulings/` — finished rulings as PDFs,
  `YYYY-MM-DD_race-<id8>_<incident>_<boats>.pdf`.
- `references/` — rulebook/casebook material. `APPENDIX_M_principles.md` is
  committed. The World Sailing Case Book files are **not** committed (copyright);
  build them locally with `references/build_casebook.py`.

## Conventions (verified from data — see methodology §3; do not re-guess)
- Positions are **game units (u), not metres**, despite the schema label; state
  distances in u and hull lengths (BL = 24 u). `+y` upwind. `hdg`/`w` are
  compass degrees (0=+y, cw). `w` is the wind's FROM direction.
- `(x,y)` is the boat's **position point, not the centroid**: bow is 14 u ahead,
  stern 10 u behind, beam 10 u (measured from the replay viewer's sprite). Judge
  lines/marks/zone at the bow (`pos + 14·u`); overlap uses stern vs bow points.
- **Never infer hull length from the zone** (the game's zone is 4.2 BL, not 3).
  `DEFAULT_BOAT_LENGTH_M = 33.6` in `rrs_geometry.py` is stale (backlog item 0).
- **Diagrams in a ruling are live captures of the replay viewer**
  (`/race/<id>/replay`) with overlays drawn in its coordinates — never
  self-generated images (methodology §6, §1.3).
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
0. Fix the hull model in code to the measured 24 u / +14 / −10 / beam 10.
1. Window-based assessors for Rules 13/15/16/17/18 (biggest gap; most incidents
   are sequence-dependent).
2. Contact module (hull now measured from the renderer) → unlocks Rules 14 and 31.
3. Position module using along-course progress (not closest-approach — that
   metric mis-scores overstanding boats).
4. Rule 44.1(b) "gained advantage despite penalty" screen.
5. Batch audit across many races (needs a bulk replay export).
