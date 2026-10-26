// ==UserScript==
// @name         Regattatron connection capture
// @namespace    https://github.com/AidanGoldfarb/ProtestCommittee
// @version      2.0.2
// @description  Passively records when each game-state packet arrives (timing only, never message contents) so lag and disconnects can be analysed. Nothing is sent anywhere; export the file yourself with the badge button.
// @author       Aidan Goldfarb
// @match        https://regattatron.com/*
// @match        https://www.regattatron.com/*
// @run-at       document-start
// @grant        none
// @noframes
// @downloadURL  https://raw.githubusercontent.com/AidanGoldfarb/ProtestCommittee/main/nettest/regattatron-capture.user.js
// @updateURL    https://raw.githubusercontent.com/AidanGoldfarb/ProtestCommittee/main/nettest/regattatron-capture.user.js
// ==/UserScript==

// What this records (and nothing else):
//   * for every WebSocket message: arrival time (ms), message kind (STATE_DELTA / WELCOME /
//     WIND_UPDATE / PONG / other), server tick number, byte length
//   * for every message the game sends: time, byte length, whether it was a PING
//   * socket open / close / error, close codes, page loads and reloads, tab visibility
//   * every 10 s: the number of boats in the last state packet and the "N spectators" /
//     "online N" numbers shown on the page
//   * your browser's user-agent string and the race URLs you opened
// It never stores message bodies, chat, names or anything typed. Data stays in this
// browser's localStorage until you press Export (downloads a .json) or Reset.

(function () {
  'use strict';
  const KEY = 'rt_capture_v2';
  const VERSION = '2.0.2';
  const MAX_FRAMES = 250000;              // ~7 hours at 10 Hz; oldest sockets are dropped beyond this
  const HOLD_MS = 300;                    // gap between state frames that counts as a "hold" on the badge
  const kindCode = { STATE_DELTA: 1, WELCOME: 2, WIND_UPDATE: 3, PONG: 4, PING: 4 };

  const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } };
  const fresh = () => ({ version: 2, script: VERSION, started: Date.now(), ua: navigator.userAgent,
    tz: Intl.DateTimeFormat().resolvedOptions().timeZone, pages: [], sockets: [], events: [] });
  let st = load() || fresh();
  let dirty = false;
  let gen = 0;                            // bumped on reset so sockets from before it stop logging
  const save = () => {
    try { localStorage.setItem(KEY, JSON.stringify(st)); dirty = false; }
    catch (e) { st.events.push({ at: Date.now(), ev: 'save_failed', msg: String(e).slice(0, 80) }); }
  };
  const trim = () => {
    let total = st.sockets.reduce((n, s) => n + s.frames.length, 0);
    while (total > MAX_FRAMES && st.sockets.length > 1) {
      const s = st.sockets.shift();
      total -= s.frames.length;
      st.events.push({ at: Date.now(), ev: 'trimmed_socket', id: s.id, frames: s.frames.length });
    }
  };

  const nav = performance.getEntriesByType('navigation')[0];
  st.pages.push({ at: Date.now(), href: location.href, navType: nav ? nav.type : '?' });
  st.events.push({ at: Date.now(), ev: 'script_start', href: location.href });
  save();

  if (window.__rtInstalled) return;
  window.__rtInstalled = true;

  // ---- WebSocket hook -------------------------------------------------------
  const Orig = window.WebSocket;
  function Hooked(url, protocols) {
    const s = protocols === undefined ? new Orig(url) : new Orig(url, protocols);
    const rec = {
      id: (st.sockets.length ? st.sockets[st.sockets.length - 1].id + 1 : 0),
      url: String(url).replace(/\?.*/, ''), page: location.href,
      created: Date.now(), opened: null, closed: null, error: null,
      // frames: [arrivalEpochMs, tick|-1, bytes, kindCode]   kindCode 1=STATE_DELTA 2=WELCOME 3=WIND_UPDATE 4=PONG 9=other
      // sent:   [epochMs, bytes, kindCode]                    kindCode 4=PING 9=other
      // spectators: [epochMs, spectatorsShown|-1, onlineShown|-1, pathTail, boatsInLastState|-1]
      frames: [], sent: [], spectators: [], kinds: {}, lastBoats: -1
    };
    const myGen = gen;
    const live = () => myGen === gen;
    st.sockets.push(rec);
    st.events.push({ at: Date.now(), ev: 'ws_create', id: rec.id });
    s.addEventListener('open', () => { if (!live()) return; rec.opened = Date.now(); st.events.push({ at: rec.opened, ev: 'ws_open', id: rec.id }); dirty = true; });
    s.addEventListener('message', (e) => {
      if (!live()) return;
      const now = Date.now();
      const d = e.data;
      const bytes = typeof d === 'string' ? d.length : (d.byteLength || d.size || 0);
      let kind = 9, tick = -1;
      if (typeof d === 'string' && d.charCodeAt(0) === 123) {
        const km = /"kind":"([A-Z_]+)"/.exec(d.slice(0, 80));
        const k = km ? km[1] : 'OTHER';
        rec.kinds[k] = (rec.kinds[k] || 0) + 1;
        kind = kindCode[k] || 9;
        if (kind === 1) {
          const tm = /"tick":(\d+)/.exec(d.slice(0, 160)); if (tm) tick = +tm[1];
          let n = 0, p = -1; while ((p = d.indexOf('"ocs":', p + 1)) !== -1) n++;
          if (n) rec.lastBoats = n;
        }
      }
      rec.frames.push([now, tick, bytes, kind]);
      dirty = true;
    });
    s.addEventListener('close', (e) => {
      if (!live()) return;
      rec.closed = { at: Date.now(), code: e.code, reason: e.reason, clean: e.wasClean, frames: rec.frames.length };
      st.events.push({ at: Date.now(), ev: 'ws_close', id: rec.id, code: e.code, reason: e.reason, clean: e.wasClean });
      save();
    });
    s.addEventListener('error', () => { if (!live()) return; rec.error = Date.now(); st.events.push({ at: Date.now(), ev: 'ws_error', id: rec.id }); dirty = true; });
    const origSend = s.send.bind(s);
    s.send = function (d) {
      if (!live()) return origSend(d);
      let kind = 9;
      if (typeof d === 'string') { const km = /"kind":"([A-Z_]+)"/.exec(d.slice(0, 80)); if (km && kindCode[km[1]]) kind = kindCode[km[1]]; }
      rec.sent.push([Date.now(), typeof d === 'string' ? d.length : (d.byteLength || d.size || 0), kind]);
      return origSend(d);
    };
    const origClose = s.close.bind(s);
    s.close = function (code, reason) {
      if (live()) st.events.push({ at: Date.now(), ev: 'app_close_called', id: rec.id, readyState: s.readyState, code: code });
      return origClose(code, reason);
    };
    return s;
  }
  Hooked.prototype = Orig.prototype;
  // lastBoats counts the per-boat '"ocs":' key in the latest STATE_DELTA (one per boat)
  Hooked.CONNECTING = 0; Hooked.OPEN = 1; Hooked.CLOSING = 2; Hooked.CLOSED = 3;
  window.WebSocket = Hooked;

  // ---- page-level events ----------------------------------------------------
  document.addEventListener('visibilitychange', () => { st.events.push({ at: Date.now(), ev: 'visibility', hidden: document.hidden }); dirty = true; });
  window.addEventListener('pagehide', () => { st.events.push({ at: Date.now(), ev: 'pagehide', href: location.href }); save(); });
  window.addEventListener('online', () => { st.events.push({ at: Date.now(), ev: 'online' }); dirty = true; });
  window.addEventListener('offline', () => { st.events.push({ at: Date.now(), ev: 'offline' }); dirty = true; });

  // ---- helpers --------------------------------------------------------------
  const stateTimes = (s) => s.frames.filter(f => f[3] === 1).map(f => f[0]);
  const holds = (s) => { const t = stateTimes(s); let n = 0; for (let i = 1; i < t.length; i++) if (t[i] - t[i - 1] > HOLD_MS) n++; return n; };

  window.__rtSummary = function () {
    return st.sockets.map(s => {
      const t = stateTimes(s);
      const gaps = []; for (let i = 1; i < t.length; i++) gaps.push(t[i] - t[i - 1]);
      const so = gaps.slice().sort((a, b) => a - b); const q = p => so.length ? so[Math.floor(p * (so.length - 1))] : null;
      return { id: s.id, url: s.url, opened: s.opened && new Date(s.opened).toISOString(), closed: s.closed,
        frames: s.frames.length, stateFrames: t.length,
        hz: t.length > 1 ? +(1000 * (t.length - 1) / (t[t.length - 1] - t[0])).toFixed(2) : null,
        gap_ms: { p50: q(.5), p90: q(.9), p99: q(.99), max: q(1) },
        over150: gaps.filter(g => g > 150).length, over300: gaps.filter(g => g > 300).length,
        kinds: s.kinds, sent: s.sent.length, lastSpectators: s.spectators[s.spectators.length - 1] };
    });
  };
  window.__rtExport = function () {
    save();
    const blob = new Blob([JSON.stringify(st)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = 'regattatron-capture-' + new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19) + '.json';
    document.body.appendChild(a); a.click(); a.remove();
    return 'exported ' + st.sockets.length + ' socket(s), ' + st.sockets.reduce((n, s) => n + s.frames.length, 0) + ' frames';
  };
  window.__rtReset = function () { gen++; localStorage.removeItem(KEY); st = fresh(); st.events.push({ at: Date.now(), ev: 'reset' }); save(); render(); return 'reset'; };
  window.__rtState = () => st;

  // ---- badge ----------------------------------------------------------------
  let badge = null, txt = null;
  function makeBadge() {
    if (badge || !document.body) return;
    badge = document.createElement('div');
    badge.id = 'rt-capture-badge';
    badge.style.cssText = 'position:fixed;left:8px;bottom:8px;z-index:2147483647;font:11px/1.4 ui-monospace,Menlo,monospace;' +
      'background:rgba(0,0,0,.72);color:#cde;padding:4px 6px;border-radius:5px;display:flex;gap:8px;align-items:center;pointer-events:auto;user-select:none';
    txt = document.createElement('span');
    const mk = (label, title, fn) => {
      const b = document.createElement('button');
      b.textContent = label; b.title = title;
      b.style.cssText = 'font:inherit;background:#234;color:#cde;border:1px solid #467;border-radius:3px;padding:0 5px;cursor:pointer';
      b.addEventListener('click', (ev) => { ev.stopPropagation(); fn(); });
      return b;
    };
    badge.appendChild(txt);
    badge.appendChild(mk('export', 'Download the capture as a .json file', () => { txt.textContent = window.__rtExport(); }));
    badge.appendChild(mk('reset', 'Delete everything recorded so far', () => { if (confirm('Delete all recorded capture data?')) window.__rtReset(); }));
    badge.appendChild(mk('×', 'Hide badge until next page load', () => { badge.style.display = 'none'; }));
    document.body.appendChild(badge);
    render();
  }
  function render() {
    if (!txt) return;
    const live = st.sockets.filter(s => s.opened && !s.closed).length;
    const frames = st.sockets.reduce((n, s) => n + s.frames.length, 0);
    const nh = st.sockets.reduce((n, s) => n + holds(s), 0);
    const closes = st.events.filter(e => e.ev === 'ws_close' && e.code !== 4041 && e.code !== 1000).length;
    txt.textContent = 'capture ' + (live ? '● ' : '○ ') + frames + ' fr · ' + nh + ' holds · ' + closes + ' drops · ' + st.sockets.length + ' sock';
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', makeBadge); else makeBadge();

  // ---- periodic sampler + saver -------------------------------------------
  setInterval(() => {
    const sock = st.sockets[st.sockets.length - 1];
    if (sock && sock.opened && !sock.closed && document.body) {
      const t = document.body.innerText || '';
      const sp = /(\d+)\s*spectat/i.exec(t); const on = /online\s*(\d+)/i.exec(t);
      sock.spectators.push([Date.now(), sp ? +sp[1] : -1, on ? +on[1] : -1, location.pathname.slice(-40), sock.lastBoats]);
      dirty = true;
    }
    if (!badge && document.body) makeBadge();
    render();
    trim();
    if (dirty) save();
  }, 10000);

  console.log('[rt-capture] installed v' + VERSION + ' — badge bottom-left; __rtSummary() / __rtExport() / __rtReset() in console');
})();
