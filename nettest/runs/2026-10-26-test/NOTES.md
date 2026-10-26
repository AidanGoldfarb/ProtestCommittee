# 2026-10-26 11:09 single-session test (aidan-mac.json)

Setup: Aidan racing from the Mac (Wi-Fi), one tab, userscript v2.0.0, no other session
on the account. Race e1323f9a: Aidan + one other human + several bots (exact boat count
not recorded; the script records it from v2.0.1 on). Packet size 2.85–3.0 KB.

Result: 10.0 Hz throughout, every tick accounted for, no periodic hold (phase bins 97–108 ms).
Three isolated 0.4 s holds, each flushed with the missed frames.

Two disconnects of a new kind: socket cut with 1006 while frames were flowing (last frame
12 ms / 70 ms before the close), no silence, no watchdog. The app reconnected in ~1 s and
was receiving on the new socket, then the page reloaded anyway ~1.4 s after the close.
Cuts were 200 s apart (two samples only).
