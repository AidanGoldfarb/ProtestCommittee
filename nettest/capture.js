// Regattatron live-feed capture hook.
// Paste into the devtools console on the LOBBY page (type "allow pasting" first if Chrome asks),
// then enter the race through the app's own buttons (no address-bar navigation, no reload).
// Records every WebSocket frame's arrival time, server tick, size and kind, plus closes,
// reloads and spectator counts, into localStorage so it survives a page reload.
//   __rtSummary()  -> quick stats in the console
//   __rtExport()   -> downloads regattatron-capture-<time>.json
//   __rtReset()    -> clears stored data
(function () {
  const KEY = 'rt_capture_v1';
  const load = () => { try { return JSON.parse(localStorage.getItem(KEY) || 'null'); } catch (e) { return null; } };
  const save = (st) => { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) { st.events.push({ at: Date.now(), ev: 'save_failed', msg: String(e).slice(0, 80) }); } };

  let st = load();
  if (!st) st = { version: 1, started: Date.now(), ua: navigator.userAgent, pages: [], sockets: [], events: [] };
  const nav = performance.getEntriesByType('navigation')[0];
  st.pages.push({ at: Date.now(), href: location.href, navType: nav ? nav.type : '?' });
  st.events.push({ at: Date.now(), ev: 'hook_installed', href: location.href });
  save(st);

  if (window.__rtInstalled) { console.log('capture hook already installed'); return; }
  window.__rtInstalled = true;

  const Orig = window.WebSocket;
  function Hooked(url, protocols) {
    const s = protocols === undefined ? new Orig(url) : new Orig(url, protocols);
    const rec = {
      id: st.sockets.length, url: String(url).replace(/\?.*/, '?...'), page: location.href,
      created: Date.now(), opened: null, closed: null, error: null,
      // frames: [arrivalEpochMs, tick|-1, bytes, kindCode]  kindCode 1=STATE_DELTA 2=WELCOME 3=WIND_UPDATE 9=other
      frames: [], sent: [], spectators: [], kinds: {}
    };
    st.sockets.push(rec);
    st.events.push({ at: Date.now(), ev: 'ws_create', id: rec.id });
    const kindCode = { STATE_DELTA: 1, WELCOME: 2, WIND_UPDATE: 3 };
    s.addEventListener('open', () => { rec.opened = Date.now(); st.events.push({ at: rec.opened, ev: 'ws_open', id: rec.id }); });
    s.addEventListener('message', (e) => {
      const now = Date.now();
      const d = e.data;
      const bytes = typeof d === 'string' ? d.length : (d.byteLength || d.size || 0);
      let kind = 0, tick = -1;
      if (typeof d === 'string' && d.charCodeAt(0) === 123) {
        const km = /"kind":"([A-Z_]+)"/.exec(d.slice(0, 60));
        const k = km ? km[1] : 'OTHER';
        rec.kinds[k] = (rec.kinds[k] || 0) + 1;
        kind = kindCode[k] || 9;
        if (kind === 1) { const tm = /"tick":(\d+)/.exec(d.slice(0, 120)); if (tm) tick = +tm[1]; }
      }
      rec.frames.push([now, tick, bytes, kind]);
    });
    s.addEventListener('close', (e) => {
      rec.closed = { at: Date.now(), code: e.code, reason: e.reason, clean: e.wasClean, frames: rec.frames.length };
      st.events.push({ at: Date.now(), ev: 'ws_close', id: rec.id, code: e.code, reason: e.reason, clean: e.wasClean });
      save(st);
    });
    s.addEventListener('error', () => { rec.error = Date.now(); st.events.push({ at: Date.now(), ev: 'ws_error', id: rec.id }); });
    const origSend = s.send.bind(s);
    s.send = function (d) { rec.sent.push(Date.now()); return origSend(d); };
    return s;
  }
  Hooked.prototype = Orig.prototype;
  Hooked.CONNECTING = 0; Hooked.OPEN = 1; Hooked.CLOSING = 2; Hooked.CLOSED = 3;
  window.WebSocket = Hooked;

  document.addEventListener('visibilitychange', () => st.events.push({ at: Date.now(), ev: 'visibility', hidden: document.hidden }));
  window.addEventListener('pagehide', () => { st.events.push({ at: Date.now(), ev: 'pagehide', href: location.href }); save(st); });
  window.addEventListener('online', () => st.events.push({ at: Date.now(), ev: 'online' }));
  window.addEventListener('offline', () => st.events.push({ at: Date.now(), ev: 'offline' }));

  setInterval(() => {
    const sock = st.sockets[st.sockets.length - 1];
    if (sock && !sock.closed) {
      const txt = document.body.innerText || '';
      const sp = /(\d+)\s*spectat/i.exec(txt); const on = /online\s*(\d+)/i.exec(txt);
      sock.spectators.push([Date.now(), sp ? +sp[1] : -1, on ? +on[1] : -1, location.href.slice(-60)]);
    }
    save(st);
  }, 5000);

  window.__rtSummary = function () {
    return st.sockets.map(s => {
      const f = s.frames.filter(x => x[3] === 1).map(x => x[0]);
      const gaps = []; for (let i = 1; i < f.length; i++) gaps.push(f[i] - f[i - 1]);
      const so = gaps.slice().sort((a, b) => a - b); const q = p => so.length ? so[Math.floor(p * (so.length - 1))] : null;
      return { id: s.id, url: s.url, opened: s.opened && new Date(s.opened).toISOString(), closed: s.closed, frames: s.frames.length,
        stateFrames: f.length, hz: f.length > 1 ? +(1000 * (f.length - 1) / (f[f.length - 1] - f[0])).toFixed(2) : null,
        gap_ms: { p50: q(.5), p90: q(.9), p99: q(.99), max: q(1) }, over150: gaps.filter(g => g > 150).length, over300: gaps.filter(g => g > 300).length,
        kinds: s.kinds, sent: s.sent.length, lastSpectators: s.spectators[s.spectators.length - 1] };
    });
  };
  window.__rtExport = function () {
    save(st);
    const blob = new Blob([JSON.stringify(st)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob);
    a.download = 'regattatron-capture-' + new Date().toISOString().replace(/[:.]/g, '-') + '.json'; a.click();
    return 'exported ' + st.sockets.length + ' socket(s), ' + st.sockets.reduce((n, s) => n + s.frames.length, 0) + ' frames';
  };
  window.__rtReset = function () { localStorage.removeItem(KEY); st = { version: 1, started: Date.now(), ua: navigator.userAgent, pages: [], sockets: [], events: [] }; return 'reset'; };
  window.__rtState = () => st;
  console.log('Regattatron capture hook installed. Now enter the race via the app buttons. __rtSummary() / __rtExport() when done.');
})();
