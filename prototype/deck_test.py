#!/usr/bin/env python3
"""
Deck test - controler de volum.

Rulare pe Mac:   python3 deck_test.py
Apoi pe iPhone (aceeasi retea Wi-Fi) deschide adresa afisata in terminal.

Nu are dependinte externe (doar biblioteca standard Python).
Pe alte sisteme decat macOS ruleaza in mod simulat (volumul e doar in memorie).
"""
import json
import platform
import socket
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 8765
STEP = 6  # cat creste/scade volumul la o apasare (0-100)
IS_MAC = platform.system() == "Darwin"

_lock = threading.Lock()
_sim = {"volume": 50, "muted": False}


# ---------------------------------------------------------------- volum (macOS)

def osa(*lines):
    args = ["osascript"]
    for line in lines:
        args += ["-e", line]
    r = subprocess.run(args, capture_output=True, text=True, timeout=5)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout.strip()


def get_state():
    if not IS_MAC:
        return dict(_sim)
    out = osa(
        "set s to get volume settings",
        'return (output volume of s as text) & "," & (output muted of s as text)',
    )
    vol, muted = out.split(",")
    if vol == "missing value":  # iesire audio fara control de volum (ex. unele HDMI)
        return {"volume": None, "muted": False, "unsupported": True}
    return {"volume": int(vol), "muted": muted == "true"}


def set_volume(v):
    v = max(0, min(100, int(round(v))))
    if not IS_MAC:
        _sim.update(volume=v, muted=False)
        return
    osa(f"set volume output volume {v} without output muted")


def toggle_mute():
    if not IS_MAC:
        _sim["muted"] = not _sim["muted"]
        return
    osa("set volume output muted not (output muted of (get volume settings))")


# ---------------------------------------------------------------- lansatoare
# Doar ce e in lista asta poate fi deschis de pe telefon (nu adrese arbitrare).
LAUNCHERS = {
    "spotify": ["open", "-a", "Google Chrome", "https://open.spotify.com"],
}


def launch(key):
    cmd = LAUNCHERS.get(key)
    if not cmd:
        raise ValueError(f"lansator necunoscut: {key}")
    if not IS_MAC:
        print("  [simulat] " + " ".join(cmd))
        return
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or "nu s-a putut deschide")


def apply(action, value=None):
    with _lock:
        if action == "set":
            set_volume(float(value))
        elif action in ("up", "down"):
            cur = get_state().get("volume") or 0
            set_volume(cur + (STEP if action == "up" else -STEP))
        elif action == "mute":
            toggle_mute()
        else:
            raise ValueError(f"actiune necunoscuta: {action}")
        return get_state()


# ---------------------------------------------------------------- server HTTP

class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, PAGE, "text/html")
        elif self.path == "/api/state":
            try:
                with _lock:
                    self._send(200, json.dumps(get_state()))
            except Exception as e:
                self._send(500, json.dumps({"error": str(e)}))
        else:
            self._send(404, json.dumps({"error": "not found"}))

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            if self.path == "/api/volume":
                self._send(200, json.dumps(apply(body.get("action"), body.get("value"))))
            elif self.path == "/api/open":
                launch(body.get("id"))
                self._send(200, json.dumps({"ok": True}))
            else:
                self._send(404, json.dumps({"error": "not found"}))
        except Exception as e:
            self._send(400, json.dumps({"error": str(e)}))

    def log_message(self, *args):
        pass  # fara zgomot in terminal


def local_urls():
    urls = []
    if IS_MAC:
        try:
            name = subprocess.run(["scutil", "--get", "LocalHostName"],
                                  capture_output=True, text=True).stdout.strip()
            if name:
                urls.append(f"http://{name}.local:{PORT}")
        except Exception:
            pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        urls.append(f"http://{s.getsockname()[0]}:{PORT}")
        s.close()
    except Exception:
        pass
    return urls or [f"http://localhost:{PORT}"]


# ---------------------------------------------------------------- pagina iPhone

PAGE = r"""<!doctype html>
<html lang="ro">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Deck">
<meta name="theme-color" content="#0b0b0f">
<title>Deck</title>
<style>
  :root{--bg:#0b0b0f;--key:#1b1b21;--key-hi:#2b2b35;--text:#f2f2f5;--dim:#8a8a96;--accent:#4f8cff;--warn:#ff5d5d;--ok:#3ddc84}
  *{box-sizing:border-box;-webkit-tap-highlight-color:transparent;-webkit-user-select:none;user-select:none;-webkit-touch-callout:none}
  html,body{margin:0;height:100%;background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,system-ui,sans-serif;overscroll-behavior:none;overflow:hidden}
  body{height:100dvh;display:flex;flex-direction:column;gap:16px;
       padding:calc(env(safe-area-inset-top) + 12px) 16px calc(env(safe-area-inset-bottom) + 16px);touch-action:manipulation}
  header{display:flex;justify-content:space-between;align-items:center;font-size:13px;color:var(--dim)}
  header b{color:var(--text);font-weight:600;letter-spacing:.02em}
  .conn{display:flex;align-items:center;gap:6px}
  .dot{width:8px;height:8px;border-radius:50%;background:var(--warn)}
  .dot.ok{background:var(--ok)}
  .level{text-align:center;font-size:72px;font-weight:700;line-height:1;font-variant-numeric:tabular-nums}
  .level small{font-size:28px;color:var(--dim);font-weight:600;margin-left:2px}
  .sub{text-align:center;color:var(--dim);font-size:13px;margin-top:-8px;min-height:16px}
  .slider{flex:1;min-height:140px;position:relative;border-radius:28px;background:var(--key);overflow:hidden;touch-action:none}
  .fill{position:absolute;left:0;right:0;bottom:0;background:var(--accent);transition:height .12s ease-out}
  .slider.drag .fill{transition:none}
  body.muted .fill{background:#45454f}
  .slider .hint{position:absolute;top:14px;left:0;right:0;text-align:center;font-size:12px;color:var(--dim);pointer-events:none}
  .keys{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}
  .key{aspect-ratio:1;border:0;border-radius:22px;background:var(--key);color:var(--text);
       display:flex;align-items:center;justify-content:center;padding:0;transition:transform .08s,background .08s}
  .key svg{width:42%;height:42%}
  .key.down{transform:scale(.93);background:var(--key-hi)}
  .key.on{background:var(--warn)}
  .key.on.down{background:#e04848}
  .launch{border:0;border-radius:22px;background:var(--key);color:var(--text);height:84px;width:100%;
          display:flex;align-items:center;gap:14px;padding:0 22px;font:600 18px -apple-system,system-ui,sans-serif;
          transition:transform .08s,background .08s}
  .launch .ic{width:44px;height:44px;border-radius:12px;background:#1db954;color:#0b0b0f;display:flex;align-items:center;justify-content:center;flex:none}
  .launch .ic svg{width:24px;height:24px}
  .launch .t{display:flex;flex-direction:column;align-items:flex-start;gap:2px}
  .launch .t small{font-size:12px;font-weight:500;color:var(--dim)}
  .launch.down{transform:scale(.97);background:var(--key-hi)}
  .launch.done .ic{background:var(--ok)}
  .launch.fail .ic{background:var(--warn)}
</style>
</head>
<body>
  <header><b>DECK · TEST</b><span class="conn"><span id="dot" class="dot"></span><span id="conn">Se conectează…</span></span></header>

  <div class="level"><span id="num">–</span><small>%</small></div>
  <div class="sub" id="sub"></div>

  <div class="slider" id="slider"><div class="fill" id="fill"></div><div class="hint">trage în sus / jos</div></div>

  <div class="keys">
    <button class="key" id="down" aria-label="Volum minus">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M5 12h14"/></svg>
    </button>
    <button class="key" id="mute" aria-label="Mute"></button>
    <button class="key" id="up" aria-label="Volum plus">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M5 12h14M12 5v14"/></svg>
    </button>
  </div>

  <button class="launch" id="spotify" aria-label="Deschide Spotify în Chrome">
    <span class="ic"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l11-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="17" cy="16" r="3"/></svg></span>
    <span class="t">Spotify<small id="spotify-sub">open.spotify.com · Chrome</small></span>
  </button>

<script>
const $ = id => document.getElementById(id);
const STEP = 6;
const ICON_ON  = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H3v6h3l5 4V5z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/></svg>';
const ICON_OFF = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 5 6 9H3v6h3l5 4V5z"/><path d="m16 9 6 6M22 9l-6 6"/></svg>';

let state = {volume: null, muted: false};
let dragging = false, holdUntil = 0;

function render() {
  const v = state.volume;
  $('num').textContent = v == null ? '–' : v;
  $('fill').style.height = (v || 0) + '%';
  $('sub').textContent = state.unsupported ? 'Ieșirea audio curentă nu permite controlul volumului'
                        : state.muted ? 'Sunet oprit' : '';
  document.body.classList.toggle('muted', !!state.muted);
  $('mute').classList.toggle('on', !!state.muted);
  $('mute').innerHTML = state.muted ? ICON_OFF : ICON_ON;
}
function setConn(ok) {
  $('dot').classList.toggle('ok', ok);
  $('conn').textContent = ok ? 'Conectat' : 'Deconectat';
}
async function api(path, body) {
  const opts = body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}
                    : {cache: 'no-store'};
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(r.status);
  return r.json();
}
async function send(body) {
  holdUntil = Date.now() + 800;
  try {
    const s = await api('/api/volume', body);
    if (!dragging) { state = s; render(); }
    setConn(true);
  } catch (e) { setConn(false); }
}
async function poll() {
  if (document.hidden || dragging || Date.now() < holdUntil) return;
  try { state = await api('/api/state'); render(); setConn(true); }
  catch (e) { setConn(false); }
}

// ---- butoane (+/- se repetă dacă ții apăsat)
function bindKey(el, fire, repeat) {
  let t1, t2;
  const stop = () => { el.classList.remove('down'); clearTimeout(t1); clearInterval(t2); };
  el.addEventListener('pointerdown', e => {
    e.preventDefault();
    el.classList.add('down');
    fire();
    if (repeat) t1 = setTimeout(() => { t2 = setInterval(fire, 110); }, 380);
  });
  ['pointerup', 'pointercancel', 'pointerleave'].forEach(ev => el.addEventListener(ev, stop));
}
function step(dir) {
  if (state.volume != null) {
    state.volume = Math.max(0, Math.min(100, state.volume + dir * STEP));
    state.muted = false; render();
  }
  send({action: dir > 0 ? 'up' : 'down'});
}
bindKey($('up'),   () => step(+1), true);
bindKey($('down'), () => step(-1), true);
bindKey($('mute'), () => { state.muted = !state.muted; render(); send({action: 'mute'}); }, false);

// ---- lansator Spotify
async function openLauncher(el, id, defaultSub) {
  const sub = el.querySelector('small');
  el.classList.remove('done', 'fail');
  try {
    const r = await fetch('/api/open', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({id})});
    const j = await r.json();
    if (!r.ok) throw new Error(j.error || r.status);
    el.classList.add('done'); sub.textContent = 'Deschis'; setConn(true);
  } catch (e) {
    el.classList.add('fail'); sub.textContent = 'Eroare: ' + e.message;
  }
  setTimeout(() => { el.classList.remove('done', 'fail'); sub.textContent = defaultSub; }, 1800);
}
bindKey($('spotify'), () => openLauncher($('spotify'), 'spotify', 'open.spotify.com · Chrome'), false);

// ---- slider vertical
const sl = $('slider');
let lastSent = 0;
function valueAt(e) {
  const r = sl.getBoundingClientRect();
  return Math.round(Math.max(0, Math.min(100, (r.bottom - e.clientY) / r.height * 100)));
}
function move(e) {
  state.volume = valueAt(e); state.muted = false; render();
  const now = Date.now();
  if (now - lastSent > 70) { lastSent = now; send({action: 'set', value: state.volume}); }
}
sl.addEventListener('pointerdown', e => { dragging = true; sl.classList.add('drag'); sl.setPointerCapture(e.pointerId); move(e); });
sl.addEventListener('pointermove', e => { if (dragging) move(e); });
function endDrag() {
  if (!dragging) return;
  dragging = false; sl.classList.remove('drag');
  send({action: 'set', value: state.volume});
}
sl.addEventListener('pointerup', endDrag);
sl.addEventListener('pointercancel', endDrag);

// fără scroll / zoom accidental
document.addEventListener('touchmove', e => e.preventDefault(), {passive: false});
document.addEventListener('gesturestart', e => e.preventDefault());

render();
poll();
setInterval(poll, 1500);
document.addEventListener('visibilitychange', poll);
</script>
</body>
</html>
"""


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print("\n  Deck test pornit" + ("" if IS_MAC else "  (MOD SIMULAT - nu e macOS)"))
    print("  Deschide pe iPhone (aceeasi retea Wi-Fi):\n")
    for u in local_urls():
        print("     " + u)
    print("\n  Ctrl+C pentru oprire.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Oprit.")


if __name__ == "__main__":
    main()
