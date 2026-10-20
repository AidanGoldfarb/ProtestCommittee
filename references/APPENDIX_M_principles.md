# Appendix M — Protest Committee Procedure (principles for our reviews)

Distilled from RRS 2025–2028 **Appendix M, Recommendations for Protest
Committees** (advisory). Authoritative text:
https://www.racingrulesofsailing.org/rules?part_id=159

These are paraphrased principles, mapped to how our automated committee should
behave. Consult the source for the exact wording.

## Core stance (Appendix M preamble)
- Weigh all evidence with equal care; honest accounts can differ and conflict.
- **No boat is "guilty" until a breach has been established** to the committee's
  satisfaction. Default to "not established", not to the engine's call.
- **Keep an open mind** until all evidence is in; be willing to conclude you were
  wrong (M4.1). *(We did exactly this when we corrected the bad rounding-gap
  metric — that is the behaviour, not an exception to it.)*

## Finding facts (M3.3 / M3.4)
- Write the facts down; **resolve doubts one way or the other** where the
  evidence allows — and where it genuinely does not, say so rather than forcing
  a verdict (ties to our "indeterminate at replay resolution" rule).
- **Decide on the facts found. If you can't decide, find more facts.** For us:
  pull a wider sample window, compute the missing quantity, or state the data
  gap and the backend ask that would close it.
- Note the quantitative evidence specifically — **times, distances, speeds**
  (M3.2). Our reconstruction should always report these, not just a conclusion.
- **Draw a diagram from the facts found** (M3.3). Our frame/gap/heading figure
  is that diagram; it should be endorsed by the facts, not decorative.

## Sufficiency of facts (M7, appeals)
- A fact must be definite: **"Was there an overlap? Yes or No. 'Perhaps' is not a
  fact found."** For us: overlap/clear-astern, tack, zone entry, and ROW must be
  emitted as definite booleans **with the assumption and tolerance stated**
  (e.g. "overlapped, using L≈33.6 m"), or explicitly as indeterminate — never a
  vague hedge.
- Record enough that someone who saw none of it can picture the whole incident.
  Our verdict should stand on its cited facts + diagram alone.

## Photographic / video evidence (M8) — maps directly to replay analysis
Appendix M warns that camera evidence is limited, and the warnings transfer to
our replay (which is our "video"):
- **View it several times / from the data, not a glance.** We read the sample
  series, not one frame.
- **Depth and distance are hard to judge from a single view.** Our advantage: we
  have true top-down coordinates, so distance is reliable — *but* hull-to-hull
  contact still depends on the assumed length/beam, so treat "contact" as modelled,
  not observed.
- **Overlap is hard to see unless substantial.** Same for us near the
  clear-astern/overlap boundary — flag marginal overlaps rather than asserting.
- **Frame rate / panning limits timing.** Our analogue is the **1 Hz sample
  rate**: sub-second turn-order and exact contact instants are beyond resolution.
  Always state this when a verdict depends on timing finer than the sample step.

## Penalties and escalation (M5/M6, for completeness)
- Rule 64 allows discretionary penalties; Rule 69 covers misconduct. Out of scope
  for routine incident review, but if a reviewed incident suggests gross or
  repeated conduct, flag it for a human rather than ruling on it.
