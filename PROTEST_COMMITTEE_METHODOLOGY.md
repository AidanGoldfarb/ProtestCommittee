# Protest Committee Methodology

A repeatable procedure for independently adjudicating sailing-racing incidents in
Regattatron from replay data, and for auditing the game's own rules engine.
Written to be followed by an AI agent or an engineer. It is deliberately
explicit about data provenance, conventions, what is and is not adjudicable,
and where the method can be improved.

The companion toolkit referenced throughout lives beside this file:
`rrs_geometry.py`, `committee.py`, `audit.py`, `test_protest.py`.

Authoritative reference material (Section 0.1) lives in the `references/`
subfolder. Only `APPENDIX_M_principles.md` is committed. The World Sailing Case
Book files (`WS-Case-Book-2025-2028.pdf`, `casebook_parsed.json`,
`CASEBOOK_REFERENCE.md`) are copyrighted and are **generated locally** with
`references/build_casebook.py` — see `references/README.md`.

**Glossary** (used throughout):
- **RRS** — the Racing Rules of Sailing, 2025–2028 edition.
- **ROW** — right of way; the "ROW boat" is the one the other must keep clear of.
- **OCS** — On the Course Side: a boat whose bow is over the start line at the
  starting signal (Rule 22 event in the replay).
- **DSQ** — disqualified.
- **Regattatron** — the browser sailing-racing game whose rules engine this
  toolkit audits. Site paths below (e.g. `/debrief`) are relative to its host.

---

## 0. What this is and is not

- **Goal:** given a flagged incident, independently apply the Racing Rules of
  Sailing (RRS, 2025–2028 edition) to the reconstructed state and compare the
  verdict to what the engine recorded. It is an **auditor**, not a replacement
  engine, and not a trained model.
- **Why symbolic, not an ML model:** a protest committee must cite the rule and
  the facts. A network trained on the engine's own calls would only imitate the
  engine (including its errors) and could not audit it. Keep the core
  deterministic and explainable. A learned component, if ever added, is only for
  genuinely fuzzy sub-questions (e.g. "was contact avoidable"), and even those
  are better attacked geometrically first.
- **The engine is never the oracle of correctness.** It is the thing under
  audit. Verify the committee against hand-constructed cases and hand-labelled
  real incidents (Section 7), never against the engine's agreement rate.

---

## 0.1 Reference sources — consult on every review

Three sources govern how incidents are judged: the rule text, the procedure a
committee follows, and the published interpretations. Use all three; a verdict
cites the rule **and** the interpretation.

1. **The rule text (RRS 2025–2028).** The letter of each rule, browseable at
   https://www.racingrulesofsailing.org/rules (no local copy is bundled — fetch
   the specific rule when wording matters). Part 2 (When Boats Meet) rules 10–24,
   plus 31 (touching a mark), 43 (exoneration) and 44 (penalties) are the ones
   this toolkit touches.
2. **Procedure — Appendix M** (`APPENDIX_M_principles.md`, full text at
   https://www.racingrulesofsailing.org/rules?part_id=159). How a protest
   committee should *operate*: presume no breach until established, decide on the
   facts found, state facts definitely ("overlap? Yes/No, not Perhaps"), draw a
   diagram, keep an open mind, and respect the limits of "video" evidence (its
   M8 cautions map directly onto our 1 Hz replay and modelled-contact limits).
   **Read this before writing a verdict** — it defines the stance, not just the
   geometry.
3. **Interpretations — the World Sailing Case Book** (`CASEBOOK_REFERENCE.md`
   for the rule→case index; `casebook_parsed.json` for full case text; source
   `WS-Case-Book-2025-2028.pdf`). 150 cases, each listed under every rule it
   interprets. This is how close calls are actually decided.

**How to use them in a review:**
1. Identify the rule(s) in play from the geometry (Section 5).
2. Open `CASEBOOK_REFERENCE.md` at those rule(s); read the on-point case
   principles; pull full text from `casebook_parsed.json["cases"]["<n>"].body`
   for any that match the situation.
3. Apply the case's interpretation to the found facts.
4. **Cite the rule and the case number(s)** in the verdict.

Worked relevance: for the start-line Rule 11-vs-16 question (Case C in the
worked case studies, Section 10),
the directly on-point cases are **CASE 13** (before the start, a leeward boat may
sail above a close-hauled course / higher than proper course — there is no proper
course before starting, but rule 16 still applies), **CASE 46** (a leeward boat
may luff, including after establishing a leeward overlap, subject to rule 16),
**CASE 92** (a keep-clear boat need only respond to what the right-of-way boat
actually does, and gets room to respond), and **CASE 147** (a right-of-way boat
that changes course must give the keep-clear boat room to keep clear). Reviewing
that incident against these cases is the correct next pass.

---

## 1. Fetching a replay

**If you already have a replay blob as a JSON file, skip to Section 2.** This
section is only about getting the blob out of the Regattatron web app, and it is
the most environment-specific (and most brittle) part of the method.

### 1.1 Prerequisites
- A **logged-in account with Pro** enabled. Pro is required for the full
  per-race debrief replay (the tick-level data). Without it you only get summary
  pages.
- A **scriptable browser** with a persistent, signed-in session on the site
  (for an AI agent, the Claude desktop app's built-in browser pane; for a human,
  the normal devtools console works). The agent cannot type passwords; a human
  logs in once, after which the session persists.

### 1.2 Procedure
1. Request site access for the pane if gated, then navigate to the **Debrief
   Room** (`/debrief`). It lists the signed-in user's races, newest first, each
   linking to `/race/<race-id>/debrief`.
2. To target "the most recent race", read the first debrief link. Re-check this
   every session — it changes as new races are sailed.
3. Navigate to `/race/<race-id>/debrief` and wait for the replay canvas to
   render (a `<canvas>` appears; ~2–3 s).
4. The full replay object ("the blob") is **server-rendered into the page and
   held in the React component tree** — there is no separate client-side fetch
   to intercept (confirmed: no `supabase.co` / storage XHR fires on the debrief
   page). Extract it by walking the fiber up from the canvas and scanning
   component props/state for an object that has a `.samples` array:

   ```js
   const cv = document.querySelector('canvas');
   const key = Object.keys(cv).find(k => k.startsWith('__reactFiber$'));
   let f = cv[key]; for (let i=0;i<8 && f.return;i++) f = f.return;
   let blob = null;
   (function scan(n,d){ if(!n||d>8||blob) return;
     for(const bag of [n.memoizedProps, n.memoizedState]) if(bag&&typeof bag==='object')
       for(const k of Object.keys(bag)) { try{ if(k==='blob'&&bag[k]&&bag[k].samples){blob=bag[k];return;} }catch(e){} }
     scan(n.child,d+1); scan(n.sibling,d);
   })(f,0);
   ```

5. The blob is ~1–2 MB of JSON — too large to return through a tool call
   directly. **Compress and base64 it in the page, move the string across, then
   decode in your analysis environment:**

   ```js
   // in the page:
   const data = new TextEncoder().encode(JSON.stringify(blob));
   const cs = new CompressionStream('gzip');
   const w = cs.writable.getWriter(); w.write(data); w.close();
   const bytes = new Uint8Array(await new Response(cs.readable).arrayBuffer());
   let bin=''; for (let i=0;i<bytes.length;i++) bin += String.fromCharCode(bytes[i]);
   window.__b64 = btoa(bin);   // return window.__b64
   ```

   ```python
   # in the analysis environment:
   import base64, gzip, re, json
   # transferred_text = whatever string the browser tool returned for window.__b64
   b64 = re.search(r'(H4sI[A-Za-z0-9+/=]+)', transferred_text).group(1)  # gzip magic
   blob = json.loads(gzip.decompress(base64.b64decode(b64)))
   ```

   The `H4sI…` regex robustly recovers the base64 even if the transfer wraps it
   in quotes/whitespace.

### 1.3 Improvement opportunities (fetch)
- **Bulk export.** This per-debrief scrape is one race at a time. For a training
  / audit corpus, ask the game's author for a direct export of replay blobs (the
  table or bucket they are rendered from). That also removes the fiber-walk,
  which is brittle against front-end refactors.
- **Robustness.** The fiber walk depends on a `blob.samples` prop. If the build
  changes, fall back to searching `self.__next_f` (the RSC flight payload) for
  the `samples`/`events` keys, or intercept the server component stream.

---

## 2. The replay blob (schemaVersion 2)

Top-level keys and meaning:

| key | meaning |
|-----|---------|
| `raceId` | UUID of the race |
| `schemaVersion` | 2 (assert this; a new version may move fields) |
| `windPresetId` | named wind/venue preset (e.g. a river venue) |
| `gunElapsedMs` | start-signal time on the `tMs` clock |
| `sampleIntervalSimMs` | nominal sample spacing (commonly 1000; some races mix 500/1000) |
| `course` | geometry (below) |
| `boats` | roster (below) |
| `samples` | time series of boat kinematics (below) |
| `events` | the engine's recorded rule events (below) — the audit targets |
| `broadcast` | stream-quality telemetry; ignore for adjudication |

**`course`**: `{ kind:"WL", windDir, startLine:{a,b}, finishLine:{a,b}, marks[], legs[], lapCount, finishZoneRadiusM }`
- `marks[]`: each `{ id, x, y, roundingSide:"PORT"|"STARBOARD", requiredSweptDeg, zoneRadiusM }`.
  Mark ids seen: `WW` (windward), `OFF` (offset), `LWP`/`LWS` (leeward gate port/starboard).
- `legs[]`: ordered `{ kind, fromId, toId }` — START → WINDWARD → OFFSET → LEEWARD → FINISH.
- `zoneRadiusM` is the Rule 18 zone, given explicitly (no need to derive from hull length).

**`boats`**: `[{ slot, displayName, countryCode, isBot, isPro, finishPos, status, hullColor, sprayColor, cosmetics }]`
- `status`: `FINISHED | RETIRED | DSQ`. `slot` is the stable per-race index used everywhere else.

**`samples`**: `[{ tMs, w, boats:[{ slot, x, y, hdg, sog }] }]`
- `tMs` sim-time ms; `w` wind direction (deg, see conventions); per-boat position
  `x,y` (m), heading `hdg` (deg), speed-over-ground `sog` (kt).
- The replay **drops** two fields that the live game WebSocket carries per boat:
  `sail` and `flags`. `flags` likely encodes right-of-way/penalty/protest state —
  request it from the author; it would be a strong cross-check.

**`events`**: `[{ kind, boatSlot, tMs, rule?, counterpartySlot?, markId? }]`
- `kind`: `OCS` (rule 22), `MARK_TOUCH` (rule 31, has `markId`), `INFRACTION`
  (Part 2, has `rule` and often `counterpartySlot`), `EXONERATION` (penalty
  taken / cleared), `DSQ` (disqualified, carries the `rule`).
- An `INFRACTION` names the **offender** (`boatSlot`), the rule, and usually the
  other boat (`counterpartySlot`). **Sometimes `counterpartySlot` is absent** —
  that incident then cannot be geometrically placed; record it as UNDETERMINED
  and ask the author to always include it.
- A boat that breaks a rule and does **not** produce a matching `EXONERATION`
  typically ends with a `DSQ` on that rule (it never took its penalty).

---

## 3. Conventions (verified from data — do not re-guess)

- **Coordinates:** metres. `+y` is upwind (toward the windward mark). `hdg` and
  `w` are **compass degrees: 0 = +y (north), 90 = +x (east), clockwise.** A
  heading's unit vector is `(sin h, cos h)`.
- **`w` is the direction the wind blows FROM.** Verified: in a frame with
  `w ≈ 345`, the close-hauled fleet split into heading clusters ≈ 300° and ≈ 30°
  — exactly ±45° around the wind axis. So tack and windward/leeward are derivable
  from `hdg` and `w` alone.
- **`(x,y)` is the hull CENTROID.** Line/mark tests must use the **bow**, modelled
  as `centroid + (L/2)·heading_unit`. Verified: at a start gun, the bow model
  reproduced *every* OCS call that a centroid-only test got wrong (both the boats
  the engine flagged and the clean ones).
- **Hull length `L`** is **not** in the data. Infer `L ≈ zoneRadiusM / 3 ≈ 33.6 m`
  (RRS zone = 3 hull lengths) and **flag it for confirmation.** Beam is also
  absent; assume ≈ `L/4 ≈ 8.4 m` only when you must, and label it.
- **`tMs` clock:** events map to samples by `idx = round(tMs / sampleIntervalSimMs)`;
  with 1000 ms spacing, `idx == tMs/1000`. Always verify by checking
  `samples[idx].tMs == event.tMs` and fall back to nearest-by-scan.
- **Ghost / did-not-start boats** sit far up-course (e.g. tens of km away) at
  ~0 kt with `DSQ` status and no events. Any line/zone test must gate on
  proximity (e.g. within ~3× line length of the start line) or these produce
  false positives.

---

## 4. Locating and classifying the incident

1. Decode the blob (Section 1). Build `names = {slot: displayName}`.
2. Print `events` with `idx = round(tMs / sampleIntervalSimMs)` (Section 3 —
   verify the sample's `tMs` matches; do not hardcode 1000), the rule, offender,
   counterparty, and `markId`. This is the list of things to audit.
3. To find a specific incident ("foul on the line", "first windward rounding"):
   - **At the start:** filter events near `gunElapsedMs`; OCS and early
     Part-2/31 events cluster there.
   - **At a mark:** compute each boat's distance to that mark over time; the
     rounding window is where the subject boat is within the zone. Beware the
     metric pitfall in Section 5.1.
4. Map the event `tMs` to its sample index and extract the frame
   `{slot: boat}` for that index (and a window around it for sequence rules).

---

## 5. Analysis

### 5.1 Position / ordering — use along-course progress, NOT closest-approach
**Pitfall (learned the hard way):** ranking boats by *closest distance to a mark*
wrongly scores an **overstanding** boat (one that sailed past the layline and
rounds wide) as far "behind", because its minimum distance to the mark occurs
late in time. This produced a fake ~22 s gap in one analysis that was actually
~a few seconds. **Measure race position by along-course progress / distance to
the _next_ mark**, or boat-to-boat separation directly — not closest approach to
the current mark.

### 5.2 Right-of-way predicates (`rrs_geometry.py`)
- `tack(hdg, w)`: STARBOARD if `norm180(w - hdg) > 0` (wind on starboard side), else PORT.
- `windward_boat(posA, posB, w)`: A is windward iff `(posA - posB) · windFrom > 0`.
- `clear_astern` / `overlapped`: project `(posA - posB)` onto a heading axis;
  A is clear astern of B if that projection `< -L`. Overlap = neither clear astern.
  (Uses the assumed `L`; mark that in the output.)
- `on_course_side(bow, lineA, lineB, towardMark)`: sign test vs the first mark,
  using the **bow** point.

### 5.3 Rule assignment audit (`committee.py`)
For each `INFRACTION`/`OCS` event, route to the rule assessor, compute the frame
state, and decide **who had the keep-clear obligation** vs **who the engine
charged**:
- Rule 10 (opposite tacks): port keeps clear of starboard. In each rule the
  "keep-clear" boat is the one that must avoid the right-of-way (ROW) boat.
- Rule 11 (same tack, overlapped): windward keeps clear of leeward.
- Rule 12 (same tack, not overlapped): clear-astern boat keeps clear.
- Rule 22 (OCS): bow on the course side of the start line at `gunElapsedMs`.
Output `AGREE` if the engine's offender == the committee's keep-clear boat,
`DISAGREE` otherwise, `UNDETERMINED` if not adjudicable from state.

**The toolkit produces only the AGREE / DISAGREE / UNDETERMINED assignment
check and its numeric basis.** The written verdict below is composed by the
reviewer (human or agent) from that output plus the case research in
Section 0.1; nothing in `audit.py` emits it.

**Verdict format (every reviewed incident):** state (a) the found facts with
numbers — times, distances, speeds, tack, overlap Yes/No (Appendix M); (b) the
rule(s) applied; (c) the on-point World Sailing Case number(s) and what they say
(Section 0.1); (d) the conclusion; (e) the assumptions and resolution limits
that qualify it. If the facts are not sufficient to decide, say so and name the
data that would settle it — do not force a verdict.

**This checks the right-of-way _assignment_, which is fully determined by
geometry. It does NOT by itself confirm an infringement _occurred_** (that needs
keep-clear-breach + contact; see 5.4–5.5).

### 5.4 Sequence rules need a time window, not one instant
Rules **15** (acquiring ROW), **16** (changing course), **17** (proper course),
**18** (mark-room), and **13** (while tacking) cannot be judged from a single
sample. Consume a window (±~10 s of samples) and compute:
- **Tack / overlap time series** (did an overlap exist, and for how long, before
  the zone / the incident).
- **Course-change (luff/bear-away) onset** per boat: `Δhdg` per sample; who
  altered course first and by how much.
- For Rule 16: did the ROW boat's course change deprive the other of room to
  keep clear? Compare the ROW boat's turn onset to the keep-clear boat's response,
  and whether the ROW boat's change actually closed the gap (vs. the gap closing
  from legitimate overtaking).

### 5.5 Proximity, contact, and timing
- **Centroid distance misleads for elongated hulls.** Model each boat as a
  **segment** of length `L` centred on the centroid along its heading, and use
  **segment-to-segment distance** as the hull-to-hull gap. Contact ≈ gap <
  combined half-beams (needs beam — flag the assumption).
- **"Foul recorded before contact" is normal, not an error.** Under Rule 11 (and
  the keep-clear definition) a boat breaks the rule the moment the ROW boat can
  no longer sail her course without avoiding action — always *before* any touch.
  Expect the engine's `INFRACTION` timestamp to precede the nearest-approach
  frame. Confirm with the author whether the `INFRACTION` `tMs` marks
  first-keep-clear-breach or contact; that one fact resolves many "premature
  call?" questions.
- **1 Hz is a hard limit on turn-order questions.** When an 11-vs-16 call turns
  on who committed to a luff within the same ~1 s, the replay literally cannot
  resolve it. Say so explicitly and flag "indeterminate at replay resolution;
  needs engine tick data."

---

## 6. Visualization spec (incident diagram)

A frame diagram makes close calls legible. Reproduce the standard tactical view:

- **Wind from the top.** Rotate all positions and hull polygons into a
  wind-aligned frame so the wind-FROM direction points straight up. For wind
  direction `W` (deg), with `f = (sin W, cos W)` (up) and `r = (cos W, -sin W)`
  (right): map each world point `(x,y) → (u,v) = ( (x,y)·r , (x,y)·f )` and plot
  `(u,v)`. This is a proper rotation (det = 1), so port/starboard are preserved.
  Do **not** `invert_xaxis` (that mirrors the scene and flips port/starboard).
- **Boats as oriented hull polygons** (pointed bow), length `L`, beam ≈ `L/4`,
  coloured by role (subject vs other), with a short heading arrow each.
- **Panel: hull-to-hull gap vs time**, with vertical markers for the recorded
  foul time and the nearest-approach time, and a shaded band at the combined
  half-beam (the contact threshold).
- **Panel: heading vs time** for both boats, with the luff-onset of each marked.
  **Improvement:** also draw the **foul-time** vertical line on this panel (it is
  currently only on the gap panel) so turn-order and foul-time are read together.
- Label everything with sim time `t = idx` seconds and the hull gap per frame.

A reference implementation (matplotlib) produced the frames for the worked
Case C below; reuse and parameterise it per incident.

---

## 7. Verifying the committee itself

- **Never use the engine as the correctness oracle** (circular — it is under
  audit).
- **Synthetic cases:** hand-construct geometries with a known-correct answer
  (clear port/starboard crossing; abeam overlap with a known windward boat; a
  boat clearly clear astern; a boat bow-over at the gun). Assert the predicate
  and the rule assignment. These are the primary tests (`test_protest.py`).
- **Hand-labelled real incidents:** a knowledgeable human labels a set of real
  incidents (rule, offender, and for sequence rules the reasoning). Test against
  those.
- **Engine-corroboration (supporting, not oracle):** you *may* check that the
  committee reproduces the engine's clear calls (e.g. the OCS bow model matched
  every gun-line call). Treat matches as a sanity signal and mismatches as
  candidates for human review — not as pass/fail of the committee.

---

## 8. Known limitations (and the asks that remove them)

| limitation | effect | ask the author for |
|---|---|---|
| No hull dimensions | overlap (11/12/18) and all contact rules (14/31) rely on assumed `L≈33.6 m`, beam `≈8.4 m` | exact hull length & beam, or confirm the inference |
| ~1 Hz sampling | can't resolve sub-second turn order; marginal OCS at the gun | native sim tick rate / finer replay |
| `sail`, `flags` dropped | lose right-of-way/penalty/protest state the live feed has | include `flags`/`sail` in the replay |
| `counterpartySlot` sometimes missing | some INFRACTIONs can't be placed | always populate counterparty |
| `INFRACTION` timestamp semantics unknown | ambiguity over "foul before contact" | document: first-breach vs contact |
| Contact taken on engine's word | can't independently confirm a touch | hull polygons or a collision radius |
| Engine rule logic opaque | can't compare our logic to its spec | the engine's own rule constants/logic |

---

## 9. Improvement backlog

1. **Window-based assessors** for Rules 13/15/16/17/18 (consume a sample window;
   compute tack/overlap/course-change series). This is the biggest capability gap
   — most interesting incidents are sequence-dependent.
2. **Contact module** once hull size is known → unlocks Rules 14 and 31.
3. **Position module** using along-course progress (fixes the closest-approach
   pitfall, 5.1) so rounding gaps are correct even with overstanding boats.
4. **Rule 44 screen:** flag any `MARK_TOUCH`/Part-2 breach where the boat *gained*
   net places across the penalty window (a "did 44.1(b) deserve a look" filter).
5. **Diagram:** add the foul-time line to the heading panel (Section 6).
6. **Batch audit** across many races to surface systematic engine disagreements;
   depends on bulk export (1.3).
7. **Resolution-aware verdicts:** when a call depends on timing finer than the
   sample interval, emit "indeterminate at replay resolution" rather than a
   verdict.

---

## 10. Worked case studies (method in action)

Roles are generic (subject boat / other boat); boats are referred to by role or
slot, not by player identity.

**Case A — Start-line OCS, bow model.** At the gun, the subject boat's centroid
read *behind* the line yet the engine flagged OCS. Modelling the line test at the
bow (`centroid + L/2` along heading) reproduced the engine's call for that boat
and for every other boat at the gun (flagged and clean). *Lesson:* `(x,y)` is the
centroid; judge lines/marks at the bow; this simultaneously corroborated the
`L≈33.6 m` inference.

**Case B — Windward-mark touch and Rule 44.1(b).** The subject touched the mark
(Rule 31) and took a One-Turn penalty. Question: did the touch yield a
significant advantage despite the penalty (→ 44.1(b) requires retirement)?
Reconstruction showed the lead came from winning the beat, and the subject's
margin over the nearest rival *shrank* across the touch-and-penalty — so the
breach conferred no advantage; the One-Turn was sufficient. *Lesson:* 44.1(b)
turns on advantage gained *by the breach*; measure margin before vs after. Also:
the first position metric used was wrong (closest-approach), inflating a gap to
~22 s when boats were actually a few seconds apart — see 5.1.

**Case C — Start-line Rule 11 vs Rule 16.** Engine charged the windward boat under
Rule 11 (then DSQ, no penalty taken). Defense considered: was it Rule 16 on the
leeward (ROW) boat for changing course without room? Frame-by-frame (hull-segment
gaps, heading-onset timing, wind-from-top diagram) showed: the leeward boat had
established her overlap from clear astern with room (Rule 15 satisfied); the
windward boat began luffing *first*; the recorded foul preceded nearest approach
(normal for keep-clear); and the windward boat's hard luff swung its stern toward
the leeward boat. Verdict leaned Rule 11 on the windward boat, with the honest
caveat that the one surviving Rule-16 argument (did the leeward boat's later luff
remove the last of the windward boat's room?) depends on sub-1 s timing the 1 Hz
replay cannot resolve. *Lessons:* 5.4 (sequence window), 5.5 (hull gap, foul-vs-
contact timing, resolution limit), Section 6 (diagram).
