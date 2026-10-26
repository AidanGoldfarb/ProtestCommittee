# Regattatron delivery-stall test — Daily East Coast Lunch Regatta, 2026-10-23 12:00 EDT

Probe: a Mac on Wi-Fi in the Toronto area, Chrome, with `window.WebSocket` hooked to timestamp every
frame (`nettest/capture.js`), plus timestamped pings (5/s) to the home router, `regattatron.com`
and `api.regattatron.com` for the whole window (`ping_*.txt`). Curated data: `capture_summary.json`.

## Summary

* The server broadcasts one `STATE_DELTA` every 100 ms (tick counter +5 per frame, so the sim ticks
  at 20 ms). Frames are 3–5.5 KB of JSON; size grows with boat count.
* Races 1 and 2 (14 and 17 boats, viewer mode, Newark then Chicago): clean. 10.0 Hz, p99 inter-arrival
  185 ms, worst gap 272 ms, HUD HEALTHY with jitter 70–130 ms throughout. No disconnects.
* Race 3 (18 boats, Chicago, this tab auto-joined as the player's boat; the player was racing from a
  second Chrome tab on the same Mac, so one boat had two sessions on one machine): the feed stalled for 0.4–3.1 s roughly every 15 s, then every missed frame arrived
  at once. The player (second tab, same Mac) saw "4 s jitter" and a disconnect; this tab saw jitter 3369 ms and
  the same disconnect at the same second. The Windows machine was not part of this test.
* During every stall the local link and the path to Cloudflare were clean: 35 minutes of pings, zero
  timeouts on gateway and site host, one on the API host, worst RTT 112 ms, nothing over 200 ms in the
  12:19–12:24 stall window.
* The same stall → disconnect signature hit a quiet 10-boat race (Atlanta host, viewer mode) twice in
  four minutes before the regatta.

## Stall anatomy (race 3, sockets 11 and 12)

| stall start (UTC) | gap | frames that arrived in the next 120 ms | tick span of that burst |
|---|---|---|---|
| 16:19:53.98 | 1574 ms | 17 | 85 |
| 16:20:08.96 | 875 ms | 9 | 45 |
| 16:20:23.96 | 2090 ms | 21 | 105 |
| 16:20:38.97 | 1753 ms | 18 | 90 |
| 16:21:08.97 | 3139 ms | 21 | 105 |
| 16:21:23.97 | 744 ms | 8 | 40 |
| 16:21:38.94 | 1669 ms | 17 | 85 |
| 16:21:54.04 | 575 ms | 7 | 35 |
| 16:22:23.95 | 1615 ms | 17 | 85 |
| 16:22:38.95 | 408 ms | 5 | 25 |
| 16:22:53.93 | 522 ms | 6 | 30 |
| 16:22:57.62 | 8239 ms | 2 | 10 → socket closed 1006 |

Reading: a 1574 ms gap followed by 17 frames spanning 85 ticks is exactly the frames that should
have arrived during the gap. Nothing was lost; delivery was held back and then flushed. The
15-second cadence (:53, :08, :23, :38 …) is a periodic server-side task blocking the race object's
send loop for a time that scales with load.

## Disconnect anatomy (seen 4 times)

1. Frames stop. 2. After exactly 4.0 s of silence the client calls `close()` and opens a new socket.
3. The new socket does not open within 2.5 s; the client closes it (error, code 1006) and does a full
page reload (to `/lobby?notice=race-interrupted` when spectating, back into the race when racing).
The failed handshake is the telling part: a brand-new connection to `api.regattatron.com` could not
complete while ICMP to the same edge was fine, so the race object itself was unresponsive.

## Baseline comparison

| | quiet race (Atlanta, 10 boats) | race 1 (Newark, 14) | race 2 (Chicago, 17) | race 3 (Chicago, 18) |
|---|---|---|---|---|
| state rate | 9.98 Hz | 10.0 Hz | 10.0 Hz | 10 / 9.42 Hz |
| p99 gap | 184 ms | 185 ms | 186 ms | 189 / 192 ms |
| gaps > 300 ms | 1 (then disconnect) | 0 | 0 | 12 |
| disconnects | 2 in 4 min | 0 | 0 | 2 |
| HUD | n/a | HEALTHY, jitter 71–131 | HEALTHY, jitter 87–125 | spikes 438–3369 ms |

The 150–200 ms gaps (7–8 % of frames in every race) are the Mac's own Wi-Fi: its radio leaves the
channel for up to ~100 ms on a fixed cycle (AWDL). They never exceed ~110 ms of extra delay and are
not what players feel.

## Client behaviour worth changing

* The jitter buffer targets ~225 ms and adapts to ~400 ms; a 1–3 s stall overruns it every time.
* A 4 s watchdog + 2.5 s connect timeout + full page reload turns a stall into a lost race. A longer
  reconnect budget with state resync would keep the player in the race.

## Server-side asks

* Find the ~15 s periodic task (persistence, snapshot, alarm, replay flush) and move it off the hot
  path, or make it incremental.
* Measure tick lateness with a real clock or client-reported arrival jitter; the isolate clock reports
  a perfect 100 ms (`broadcast` block in every replay) while clients see multi-second stalls.
* Shrink frames (binary, deltas) so per-client serialization stops scaling with boats × connections.
* Drop or coalesce frames for a client that is behind instead of queueing them.

## What the owner can fix without touching hosting or Cloudflare

Evidence: edge reachable throughout, connection never dropped by the network, every missed frame
delivered late in a burst. This is application behaviour, not transport or platform throttling.

1. **Find the 15 s periodic task on the race object** (stalls at :53/:08/:23/:38, length scales with
   boats). Make it incremental, run it between ticks, or move it to another object.
2. **Reconnect instead of reload.** Replace 4 s silence → one 2.5 s attempt → page reload with
   15–20 s of backoff retries and a resync from the last received tick.
3. **Shrink frames.** Binary deltas against the last acknowledged tick instead of 3–5.5 KB JSON of
   full state per client per 100 ms.
4. **Don't queue for slow clients.** Track last acknowledged tick; send only the newest frame to a
   client that is behind rather than flushing a burst.
5. **Let the jitter buffer grow** beyond ~400 ms under sustained jitter.
6. **Measure with a real clock.** Client-reported arrival jitter or send timestamps vs. client acks;
   the isolate clock reports a perfect 100 ms during 3 s holes.

Not indicated by the data: a hosting move, dedicated servers, UDP transport, or Cloudflare settings.

## Is the 15 s stall present in every race? (checked 2026-10-23 afternoon from the stored capture)

Method: every STATE_DELTA inter-arrival gap binned by its phase inside a 15 s cycle (30 bins of
0.5 s), plus a period scan from 8 s to 24 s looking for the period that maximises the peak bin.

| race | mean gap per phase bin | best period (peak/mean) | verdict |
|---|---|---|---|
| race 1, 14 boats, viewer | 99–102 ms in every bin | none (1.03) | flat, no periodic hold |
| race 2, 17 boats, viewer | 97–103 ms in every bin | none (1.05) | flat, no periodic hold |
| race 3, 18 boats, player session | one bin at 334 ms, next at 0 (burst) | 15.0–15.5 s (4.0) | strong 15 s hold |
| quiet Atlanta race, 10 boats | flat | none | single 973 ms hold then disconnect |

Race-3 hold times sat on an exact 15.0 s grid anchored to the server clock across two different
sockets (16:19:53.98, 16:20:08.96, 16:20:23.96, 16:20:38.97, 16:21:08.97, 16:21:23.97, 16:21:38.94,
16:21:54.04, 16:22:23.95, 16:22:38.95, 16:22:53.93). A hold of even ~10 ms per cycle would have
shown in races 1–2 as a +2 ms bump in one bin; none is there. So the periodic hold is **not
omnipresent**: it appeared only in race 3. Race 3 differed in three ways at once: 18 boats, this
tab was a player session rather than a viewer, and the player's boat had two sessions attached
(the auto-joined capture tab + the player's own tab, both on the same Mac). Which of those triggers the hold is not yet separated.
