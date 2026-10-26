# 2026-10-26 14:30 regatta, Windows wired, single session (aidan-windows.json)

Four races (a11f8259, 0fe7f947, 5e847f75, 80da33db), 10–12 boats, userscript v2.0.2.
Analysis: `python3 nettest/analyze.py nettest/runs/2026-10-26-1430/aidan-windows.json`.

## The 750-tick job was quiet

Every race flat: 10.00 Hz, every tick accounted for, no holds over 300 ms except two small
ones in race 4 and the end-of-regatta 3.5 s pause. The job is still visible at every boundary,
but small: boundary packet late by 15–20 ms (mean 115–121 ms vs 100), next packet on schedule.
Compare the noon regatta: 140–230 ms in the short form, 0.5–2.1 s holds in the long form.
So the job's cost varies by an order of magnitude between regattas with similar boat counts.
Server region was not recorded (the script does not capture it yet).

## Four abrupt socket cuts, page reloaded each time despite a working reconnect

| cut | socket age | last tick before cut | reconnect socket | first tick after | sim gap | wall gap |
|---|---|---|---|---|---|---|
| 14:30:19.754 | 48.1 s | 22430 | #3 opened, got frames | 22500 | 1.40 s | 1.43 s |
| 14:43:27.524 | 67.6 s | 3440 | #6 opened, got frames | 3485 | 0.90 s | 0.89 s |
| 14:52:32.117 | 130.6 s | 6550 | #9 opened, got frames | 6600 | 1.00 s | 1.01 s |
| 14:57:31.263 | 297.3 s | 21505 | #11 opened, got frames | 21555 | 1.00 s | 1.0 s |

All four: frames flowing to within 0.1 s of the close, close code 1006 with no close frame,
no sends or pings in the seconds before, no tab visibility change. The replacement socket
opened within ~0.8 s and was receiving packets, and the page then did a full reload 1.3–2.1 s
after the cut anyway, opening a third socket. The race object did not restart: tick numbers
continue across the cut with only the wall-clock gap missing.

Cut spacing 788 s, 545 s, 299 s; socket ages 48 s, 68 s, 131 s, 297 s; tick mod 750 at the
cut 680, 440, 550, 505. No pattern in age, sim time, boundary phase or traffic.
With this morning's two, that is six cuts today on this machine, all with the same shape.
Neither noon capture (this machine, other racer) had any, so no cross-client sample yet.

For the author: (1) something upstream drops the socket without a close frame while the race
object is healthy; (2) the client's 1006 handler reloads the page even after its own reconnect
has succeeded, which is the part the player feels. Cancel the reload once the new socket opens.
