# Regattatron noon regatta, 2026-10-26: the 15 s hold is a per-750-tick job on the race object

Capture: `aidan-windows.json` (the **Windows machine**, wired Ethernet, Chrome, userscript v2.0.1, single tab, nothing else on the
account). Reset pressed 11:57:23, export 12:19:21. Three races, no page reloads, no
watchdog disconnects. Analysis: `python3 nettest/analyze.py nettest/runs/2026-10-26-noon/aidan-windows.json`.

## Summary

* Every race is broadcast at a steady 10 Hz with every server tick accounted for. Nothing
  was lost in any race.
* **Every race shows a periodic job on the race object at server tick ≡ 0 mod 750**, that is
  every 15 s of simulation time. It delays the packet at the boundary by 0.1–0.5 s in
  otherwise clean races, and no other packets are affected.
* In race 2 (7 boats), from 2 min 51 s into the race until the finish, that job began
  **holding the whole feed 0.5–2.1 s on every cycle**, then flushing all held packets in a
  burst. 15 cycles in a row. The player sees a freeze and jump every 15 s.
* This happened on wired Windows, one session, 7 boats. It is not the Mac, not Wi-Fi, not a
  duplicate session, and not boat count. The 2026-10-23 sighting (Mac, 18 boats, two tabs)
  was the same job.
* The job is tied to the **tick counter**, not the wall clock, so it is in the simulation
  loop itself: something like `if (tick % 750 === 0) { … }`.

## Per race

| race | boats | duration | boundary-frame delay (mean / max) | hold after boundary (mean / max) | all other gaps | verdict |
|---|---|---|---|---|---|---|
| 1 `7394d4bd` | 10 → 5 | 493 s | 143 ms / 566 ms, >150 ms in 6 of 33 cycles | 78 ms / 203 ms | 99.9 ms, 5 of 4860 >150 ms | job visible, mild |
| 2 `fde93f11` | 7 | 389 s | 111 ms / 186 ms | **672 ms / 2072 ms, >150 ms in 15 of 26 cycles** | 96.1 ms, 9 of 3839 >150 ms | job holding the feed |
| 3 `2b7e0056` | 8 → 9 | 394 s | **228 ms / 517 ms, >150 ms in 20 of 26 cycles** | 23 ms / 100 ms | 100.3 ms, 9 of 3862 >150 ms | job visible every cycle |

"Boundary frame" is the packet carrying tick 750·k. "Hold after boundary" is the gap
between that packet and the next one (tick 750·k + 5).

Race 2, gap after each boundary packet in order (ms), from the start of the race:

```
 94  76  86  86  81  82  87  88  85  84  87  102 | 1211 1031 542 2072 1899 727 888 893 950 1110 1128 1160 907 924 1101
```

The switch at 12:08:55 is abrupt and persists to the end of the race. Each hold was
followed by a burst containing exactly the missed packets (burst frames × 5 = tick span),
so the simulation kept running on time and only delivery was blocked.

## Two shapes of the same job

* **Short form** (races 1 and 3, and race 2 before 12:08:55): the boundary packet itself is
  late by 15–500 ms and the following packet arrives on its normal schedule. That is
  synchronous CPU work done before the tick-750·k broadcast, for example serialising a
  snapshot of the race state.
* **Long form** (race 2 after 12:08:55, and 2026-10-23 race 3): the boundary packet is on
  time, and everything after it is held 0.5–3 s, then flushed at once. That is the shape of
  a Durable Object storage write with the output gate engaged: outgoing WebSocket messages
  are held until the write is confirmed, and the hold length is the storage commit latency.

The two forms together fit one routine: build a snapshot (CPU, always visible a little),
then persist it (I/O, usually fast enough to hide, sometimes 1–2 s for the rest of a race).

## What this rules out

| suspect | evidence |
|---|---|
| Mac Wi-Fi / AWDL | today's capture is wired Windows; same job, worse than Thursday per cycle |
| the player's machine | two different machines, same tick-locked signature |
| a second session on the account | one tab, nothing else connected |
| boat count | 7 boats in the affected race; the 18-boat race on Thursday was the earlier sighting |
| the local path | the 7.3 % of 150–200 ms gaps seen on the Mac are absent here (0.2–0.7 %) |
| packet loss | zero in all three races |

## For the author

1. Find what runs when `tick % 750 === 0` on the race Durable Object. It is present in
   every race.
2. If it writes to storage, the hold is the output gate. Options: `allowUnconfirmed: true`
   on that write, write incrementally instead of a full snapshot, or move persistence to a
   separate object or alarm so the race object's socket output is never gated by it.
3. The synchronous part (serialisation) also shows: 0.2 s on the boundary packet in race 3
   every cycle. Chunk it or do it off the broadcast path.
4. Separately (seen 2026-10-26 morning, `runs/2026-10-26-test`): a socket closed with 1006
   while packets were flowing, the client reconnected in about 1 s, and the page then
   reloaded anyway. Cancel the reload once the replacement socket opens.

## Not seen today

No watchdog disconnects and no reloads: the longest hold was 2.1 s, under the client's 4 s
limit. No abrupt 1006 cuts either, so the morning's 200 s spacing has no second sample yet.
