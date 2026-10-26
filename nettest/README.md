# Regattatron connection capture

A small, read-only browser script that records **when** each game packet reaches your
browser during a Regattatron race, so lag and disconnects can be measured instead of
argued about. Several people running it in the same race lets us tell apart
"the server stalled for everyone" from "my connection stalled".

Nothing is uploaded anywhere. The script keeps its data in your own browser until you
press **export**, which saves a `.json` file you can send (or not).

## What it records

* for every packet the game sends you: arrival time, packet type (state / wind / pong /
  other), the server's tick number, and the size in bytes
* for every packet your browser sends: time, size, and whether it was a ping
* socket opens, closes and close codes, page loads and reloads, tab visibility
* the "N spectators" / "online N" numbers on the page, every 10 s
* your browser's user-agent string, your time zone, and the race URLs you opened

It never stores packet contents, chat, names, or anything you type. You can read all of
it: the whole script is [`regattatron-capture.user.js`](regattatron-capture.user.js),
about 170 lines.

## Install (once)

1. Install the Tampermonkey extension for your browser
   (Chrome / Edge / Brave: Chrome Web Store; Firefox: addons.mozilla.org; Safari: App Store).
   In Chrome you also need to turn on **Developer mode** on `chrome://extensions` for
   userscripts to run; Tampermonkey shows a notice if it is off.
2. Open this link in that browser and click **Install** in the Tampermonkey page that
   appears:

   `https://raw.githubusercontent.com/AidanGoldfarb/ProtestCommittee/main/nettest/regattatron-capture.user.js`

   If the link does not open an install page, open Tampermonkey's dashboard, choose
   **Utilities → Import from file** (or **+** to create a new script), and paste the
   contents of the file.
3. Open regattatron.com. A small dark badge appears at the bottom-left:

   `capture ● 1234 fr · 0 holds · 0 drops · 1 sock  [export] [reset] [×]`

   `●` means a race socket is open and being recorded. `fr` is packets recorded,
   `holds` is the number of gaps longer than 300 ms between state packets, `drops` is
   abnormal socket closes. `×` hides the badge until the next page load; recording continues.

## Use

1. Race (or spectate) as normal. Do nothing else. The script survives the game's own
   page reloads, so a disconnect and reconnect is recorded too.
2. After the regatta, press **export** on the badge. A file named
   `regattatron-capture-<date>.json` lands in your downloads. A full regatta is roughly
   1–3 MB.
3. Send that file to whoever is collecting them, with one line of context: which
   machine (OS), wired or Wi-Fi, roughly where you are, and whether you were racing or
   watching.
4. Press **reset** when you want to start clean (for example before the next regatta
   you want to report). Reset asks for confirmation and deletes the recorded data.

The badge is only in your browser; other players cannot see it.

### Without Tampermonkey

Open the browser devtools console on the **lobby** page (F12, "Console" tab), paste the
contents of [`capture.js`](capture.js) and press Enter (Chrome may ask you to type
`allow pasting` first). Then enter the race through the game's own buttons. This
version does not survive a page reload, so after any disconnect it has to be pasted
again. `__rtExport()` in the console downloads the file.

## For the person analysing the files

```
python3 nettest/analyze.py capture1.json [capture2.json ...] [--ping ping.txt] [--period 15] [--hold-ms 300]
```

Per socket it prints the state-packet rate, inter-arrival percentiles, late and
bunched packet counts, server-tick continuity, every hold with the burst that
followed it, and a periodic-hold test: mean gap by phase within a 15 s cycle, plus
a period scan from 8 to 24 s. The verdict line says `flat`, `holds present but not
periodic`, or `PERIODIC HOLD`.

Per abnormal disconnect it prints how long the feed had been silent, whether the
app closed the socket itself (its 4 s watchdog) or the peer did, and what the
replacement socket did.

When several files contain the same race, it aligns their holds by **server tick**
(so the players' clocks do not need to agree) and reports, for each client, how
many of its holds every other connected client saw at the same moment. Holds seen
by everyone are produced upstream of all of them, in the race's server process.
Holds seen by one client only belong to that client's path or machine.

`--ping` accepts `ping --apple-time` logs recorded on the same machine as the first
capture, and reports how many holds coincided with a local ping spike. See
`pingrun.sh`.

The `tick_phase_s` column in the hold table is `(tick × 20 ms) mod 15 s`. Holds that
share one value across clients and across sockets are locked to the server's clock.

## Known findings so far

See [`runs/noon/REPORT.md`](runs/noon/REPORT.md) for the 2026-10-23 lunch-regatta
capture: 10 Hz feed, periodic 0.4–3.1 s holds on an exact 15 s server-anchored grid
in an 18-boat race with no packet loss, and the client's watchdog turning a 4 s stall
into a full reload. Races earlier in the same regatta were flat. The open question,
which the multi-client capture is designed to answer, is what triggers the hold.
