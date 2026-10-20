# Regattatron protest committee (v1)

A **deterministic** reviewer that independently applies the Racing Rules of
Sailing (2025–2028) to a flagged incident and checks whether the game's rules
engine assigned right-of-way to the correct boat. No neural network: a protest
committee must cite the rule and the facts, so the core is symbolic geometry.

## What it does / does not do (v1)

- **Checks:** *"Did the engine charge the correct boat under the cited rule?"* —
  the right-of-way **assignment**, which is fully determined by the kinematic
  state (position, heading, wind direction, course geometry).
- **Does not yet check:** whether an infringement *actually occurred*
  (keep-clear breach + contact). That needs a contact model and hull
  dimensions, which the replay does not carry (see Limitations).

## Files

| file | purpose |
|------|---------|
| `rrs_geometry.py` | pure predicates: tack, wind angle, overlap/clear-astern, windward/leeward, line side, bow reference point |
| `committee.py`    | rule assessors (10, 11, 12, 22) + audit orchestration over a replay blob |
| `audit.py`        | CLI: `python audit.py <replay_blob.json> [boat_length_m]` |
| `test_protest.py` | synthetic verification suite (the oracle) + real-data corroboration |

Run: `pytest -q` then `python audit.py <blob.json>`.

## Conventions (verified from data, not assumed)

- `(x,y)` metres; `+y` is upwind (toward the windward mark).
- `hdg`, `w` are compass degrees: `0 = +y`, `90 = +x`, clockwise.
- `w` is the direction the wind blows **from** — confirmed: at a frame with
  `w≈345`, the close-hauled fleet split into heading clusters ~300° and ~30°,
  i.e. ±45° around the wind axis.
- `(x,y)` is the hull **centroid**; the start line is judged at the **bow**
  (`centroid + L/2` along heading). Cross-checked on real replay data: the bow
  model reproduces every gun-line OCS call that the centroid alone gets wrong.

## Rule coverage

| rule | status | note |
|------|--------|------|
| 10 opposite tacks | ✅ implemented | port keeps clear of starboard |
| 11 windward/leeward | ✅ implemented | needs overlap + boat length |
| 12 same tack, clear astern | ✅ implemented | astern keeps clear |
| 22 OCS (start) | ✅ implemented | bow model + start-area gate |
| 13 while tacking | ⛔ not yet | needs head-to-wind detection over a window |
| 14 avoid contact | ⛔ blocked | needs contact model + hull dims (absent) |
| 15 acquiring ROW | ⛔ not yet | needs the transition sequence |
| 16 changing course | ⛔ not yet | needs heading-change over a window |
| 17 proper course | ⛔ not yet | needs proper-course estimate over a window |
| 18 mark-room | 🟡 partial | zone radius known; overlap-at-zone-entry needs a window |
| 31 touching a mark | ⛔ blocked | needs contact model + hull dims (absent) |

## Verification strategy

The oracle is **hand-constructed geometry with known answers**, never the
engine (which would be circular). `test_protest.py` builds explicit incidents
(a clear port/starboard crossing, an abeam overlap, a boat clear astern, etc.)
and asserts the expected ROW assignment. One real-data test corroborates the
OCS bow model against the engine's own gun-line calls.

## Output

For each flagged event the audit prints `AGREE`, `DISAGREE` or `UNDETERMINED`
with the numeric basis (tack, overlap, bow-to-line distance, assumed hull
length). Every `UNDETERMINED` names the concrete data gap that would make the
incident adjudicable. Boats are referred to by slot or role, never by player
identity (methodology §10).

## References — every verdict cites the rule and the case

The geometry only establishes the facts. A verdict is then written against
credible, authoritative sources (methodology §0.1):

1. **The rule text** — RRS 2025–2028, Part 2 (rules 10–24) plus 31, 43 and 44.
   Not bundled; fetch the exact wording from
   https://www.racingrulesofsailing.org/rules when it matters.
2. **Appendix M** (Recommendations for Protest Committees) — how a committee
   operates: presume no breach until established, find facts definitely, respect
   the limits of replay evidence. Distilled in `references/APPENDIX_M_principles.md`.
3. **The World Sailing Case Book 2025–2028** — the official interpretations
   that decide close calls (e.g. Cases 13, 46, 92 and 147 for a start-line
   Rule 11 vs 16 question). It is World Sailing copyright, so it is not
   committed; build the local rule→case index and parsed text with
   `python references/build_casebook.py` (see `references/README.md`).

A verdict without a rule number and an on-point case number is incomplete.

## Limitations / what to ask the game's author for

1. **Hull dimensions.** No boat length/beam in the replay. `L ≈ 33.6 m` is
   inferred from `zoneRadiusM / 3` and corroborated by the OCS bow model, but
   confirm it. Needed for overlap (11/12/18) and all contact rules (14/31).
2. **Contact geometry.** `MARK_TOUCH` / Rule 14 need actual hull polygons or a
   collision radius; positions alone can't confirm contact.
3. **Finer timing.** The debrief replay is ~1 Hz. The native sim tick rate
   (and the `flags`/`sail` fields the replay drops) would sharpen OCS-at-the-gun
   and mark-rounding windows.
4. **Counterparty on every event.** Some `INFRACTION` events carry no
   `counterpartySlot`; without it the incident cannot be placed geometrically.
5. **The engine's own rule logic + constants** (zone test, overlap definition,
   proper-course model) — to compare against, rather than infer.

## Next increments

- Window-based assessors for 15/16/17 and 18 (consume a ±N-sample slice around
  the event, not one instant), and a tack/overlap time series.
- A contact module once hull size is known, unlocking 14 and 31.
- Batch audit across many races to surface systematic disagreements.
