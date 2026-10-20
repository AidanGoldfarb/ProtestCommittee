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
  (`centroid + L/2` along heading). Cross-checked on race cacbaec5: the bow
  model reproduces all four gun-line calls that the centroid alone gets wrong.

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

## Result on race cacbaec5 (8 flagged incidents)

```
AGREE        OCS 22     Yahooz        (bow over at gun)
AGREE        OCS 22     trim.on       (bow over at gun)
AGREE        R11        ViperMamboKings windward of Cam
AGREE        R10        Johnny (port) vs zinger (starboard)
UNDETERMINED R31 x2     mark touch — needs contact model
UNDETERMINED R11        engine event had no counterparty slot
UNDETERMINED R18        mark-room — needs time window
=> 4 AGREE, 0 DISAGREE, 4 UNDETERMINED
```

Zero disagreements on this sample, as expected for a shipped engine; the value
is the method and the fact that every UNDETERMINED maps to a concrete data gap.

## Limitations / what to ask the game's author for

1. **Hull dimensions.** No boat length/beam in the replay. `L ≈ 33.6 m` is
   inferred from `zoneRadiusM / 3` and corroborated by the OCS bow model, but
   confirm it. Needed for overlap (11/12/18) and all contact rules (14/31).
2. **Contact geometry.** `MARK_TOUCH` / Rule 14 need actual hull polygons or a
   collision radius; positions alone can't confirm contact.
3. **Finer timing.** The debrief replay is ~1 Hz. The native sim tick rate
   (and the `flags`/`sail` fields the replay drops) would sharpen OCS-at-the-gun
   and mark-rounding windows.
4. **Counterparty on every event.** The reciprocal Rule 11 event (slot 9) had
   no `counterpartySlot`; with it, that case becomes adjudicable.
5. **The engine's own rule logic + constants** (zone test, overlap definition,
   proper-course model) — to compare against, rather than infer.

## Next increments

- Window-based assessors for 15/16/17 and 18 (consume a ±N-sample slice around
  the event, not one instant), and a tack/overlap time series.
- A contact module once hull size is known, unlocking 14 and 31.
- Batch audit across many races to surface systematic disagreements.
