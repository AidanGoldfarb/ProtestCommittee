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
about 200 lines.

## Install (once, about two minutes)

**1. Install Tampermonkey**, the userscript manager, for your browser:

* Chrome, Edge, Brave, Opera: Tampermonkey in the Chrome Web Store
* Firefox: Tampermonkey on addons.mozilla.org
* Safari: Tampermonkey in the Mac App Store

**2. Chrome-based browsers only: allow user scripts.** Tampermonkey cannot run scripts
until you switch this on, and it is off by default:

* click the Tampermonkey icon in the toolbar (puzzle-piece menu if it is hidden)
* choose **Manage extension**
* turn on **Allow User Scripts** (on older Chrome versions the switch is called
  **Developer mode**, at the top right of the `chrome://extensions` page)

If you skip this, the install in step 3 appears to succeed but nothing runs and no
badge appears.

**3. Install the script.** Open this link in the same browser and press **Install**
on the Tampermonkey page that opens:

`https://raw.githubusercontent.com/AidanGoldfarb/ProtestCommittee/main/nettest/regattatron-capture.user.js`

If the link only shows the script text instead of an install page, open the
Tampermonkey dashboard (icon → Dashboard), press the **+** tab, delete the template,
paste the whole script text, and save with Ctrl+S / Cmd+S.

**4. Check it is running.** Open or reload regattatron.com. A small dark badge appears
at the bottom-left of the page:

`capture ○ 0 fr · 0 holds · 0 drops · 0 sock  [export] [reset] [×]`

* `○` becomes `●` once a race socket is open, and `fr` (packets recorded) then climbs
  by about 10 per second during a race.
* `holds` is the number of gaps longer than 300 ms between state packets, `drops` is
  the number of abnormal socket closes.
* `×` hides the badge until the next page load; recording continues.

No badge means the script is not running: check step 2, then check that the script is
enabled in the Tampermonkey dashboard.

Updates are automatic: Tampermonkey checks the link above and installs new versions
itself.

## Use

1. **Just before the regatta you want to report, press reset** on the badge (it asks
   to confirm). That way the file contains only that regatta.
2. **Race (or spectate) as normal from one browser tab.** Do not have the game open in
   a second tab or on a second machine on the same account during the capture; part of
   what we are testing is whether a second session causes the stalls. The script
   survives the game's own page reloads, so disconnects and reconnects are recorded.
3. **After the regatta, press export.** A file named `regattatron-capture-<date>.json`
   lands in your downloads folder. A full regatta is roughly 1–2 MB.
4. **Send that file** to whoever is collecting them, with one line of context: which
   machine (Windows / Mac / Linux), wired or Wi-Fi, roughly where you are, and whether
   you were racing or watching.

The badge is only in your browser; other players cannot see it. The script records
timing only; see "What it records" above.

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
