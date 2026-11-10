"""Serverul HTTP/HTTPS: servește deck-ul pentru iPhone, primește apăsările și trimite starea
în timp real (Server-Sent Events)."""
import json
import os
import re
import sys
import queue
import secrets
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from . import actions, admin, certs, icons, system, uiauto
from .features import Features
from .config import HOME, Config

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
TOKENS_PATH = os.path.join(HOME, "tokens.json")

STATIC = {
    "/": ("index.html", "text/html"),
    "/index.html": ("index.html", "text/html"),
    "/app.js": ("app.js", "application/javascript"),
    "/app.css": ("app.css", "text/css"),
    "/glyphs.js": ("glyphs.js", "application/javascript"),
    "/pages.js": ("pages.js", "application/javascript"),
    "/setup": ("setup.html", "text/html"),
    "/config.js": ("config.js", "application/javascript"),
    "/config.css": ("config.css", "text/css"),
    "/nosleep.mp4": ("nosleep.mp4", "video/mp4"),
    "/manifest.webmanifest": ("manifest.webmanifest", "application/manifest+json"),
}


_web_version = None


def web_version():
    """Versiunea fișierelor web (se schimbă la fiecare actualizare, ca telefonul să le reîncarce)."""
    global _web_version
    if _web_version is None:
        import hashlib
        h = hashlib.sha1()
        for n in sorted(os.listdir(WEB)):
            h.update(n.encode())
            h.update(str(os.path.getmtime(os.path.join(WEB, n))).encode())
        _web_version = h.hexdigest()[:10]
    return _web_version


# ------------------------------------------------------------------ evenimente către telefon

class Hub:
    def __init__(self):
        self.clients = set()
        self.lock = threading.Lock()

    def add(self):
        q = queue.Queue(maxsize=100)
        with self.lock:
            self.clients.add(q)
        return q

    def remove(self, q):
        with self.lock:
            self.clients.discard(q)

    def send(self, event):
        data = json.dumps(event, ensure_ascii=False)
        with self.lock:
            for q in list(self.clients):
                try:
                    q.put_nowait(data)
                except queue.Full:
                    pass

    def count(self):
        with self.lock:
            return len(self.clients)


# ------------------------------------------------------------------ asociere cu telefonul

class Auth:
    def __init__(self):
        self.code = self._new_code()
        self.failures = 0
        try:
            with open(TOKENS_PATH) as f:
                self.tokens = set(json.load(f))
        except (OSError, ValueError):
            self.tokens = set()

    @staticmethod
    def _new_code():
        return "%06d" % secrets.randbelow(1000000)

    def pair(self, code):
        if not secrets.compare_digest(str(code), self.code):
            self.failures += 1
            if self.failures >= 5:  # prea multe încercări: cod nou
                self.code = self._new_code()
                self.failures = 0
                print("  Prea multe încercări greșite. Cod nou de asociere: %s" % self.code)
            return None
        token = secrets.token_urlsafe(24)
        self.tokens.add(token)
        os.makedirs(HOME, exist_ok=True)
        with open(TOKENS_PATH, "w") as f:
            json.dump(sorted(self.tokens), f)
        os.chmod(TOKENS_PATH, 0o600)
        self.code = self._new_code()
        print("  ✓ Telefon asociat. (cod nou pentru alt dispozitiv: %s)" % self.code)
        return token

    def ok(self, token):
        return bool(token) and token in self.tokens


# ------------------------------------------------------------------ aplicația

class Deck:
    def __init__(self):
        self.hub = Hub()
        self.auth = Auth()
        self.config = Config(on_change=lambda: self.hub.send({"type": "config"}))
        self.config.watch()
        self._last = None
        self.features = Features(self)

    def state(self):
        v = system.get_volume()
        live = self.features.snapshot()
        t = actions.toggles()
        tm = live.get("timer") or {}
        t.update(focus=bool(live.get("focus")), mic_muted=bool(live.get("mic_muted")),
                 timer=bool(tm.get("running")), meet_call=bool(live.get("meet_call")))
        return {"volume": v["volume"], "muted": v["muted"],
                "brightness": system.get_brightness(),
                "toggles": t, "live": live}

    def push_state(self, force=False):
        try:
            s = self.state()
        except Exception as e:
            print("  ! nu pot citi starea: %s" % e)
            return
        if force or s != self._last:
            self._last = s
            self.hub.send(dict(s, type="state"))

    def poll_forever(self):
        while True:
            time.sleep(1)
            if self.hub.count():
                self.push_state()

    def ctx(self):
        return {"state_changed": lambda: self.push_state(force=True), "features": self.features,
                "deck": self, "cfg": self.config.get()}

    def run_button(self, button_id, long=False, choice=None):
        b = self.config.find_button(button_id)
        if not b:
            raise ValueError("buton necunoscut")
        action = b.get("long") if long else b.get("action")
        if not action:
            return {"ok": True, "msg": ""}
        if choice is not None:
            action = dict(action, choice=int(choice))
        try:
            msg = actions.execute(action, self.ctx())
            return {"ok": True, "msg": msg}
        except actions.Soon as e:
            return {"ok": False, "soon": e.phase, "msg": "Vine în etapa %s" % e.phase}


DECK = None


class Handler(BaseHTTPRequestHandler):
    server_version = "MacDeck/1"
    protocol_version = "HTTP/1.1"

    # -------------------------------------------------------- utilitare
    def setup(self):
        if isinstance(self.request, ssl.SSLSocket):
            self.request.settimeout(10)
            self.request.do_handshake()
            self.request.settimeout(None)
        super().setup()

    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json", extra=None):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith(("text", "application/j")) else ""))
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False))

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def _is_local(self):
        return self.client_address[0] in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    def _authed(self, query):
        if self._is_local():
            return True
        token = self.headers.get("X-Deck-Token") or (query.get("k") or [None])[0]
        return DECK.auth.ok(token)

    # -------------------------------------------------------- GET
    def do_GET(self):
        url = urlsplit(self.path)
        path, query = url.path, parse_qs(url.query)

        if path in STATIC:
            name, ctype = STATIC[path]
            with open(os.path.join(WEB, name), "rb") as f:
                return self._send(200, f.read(), ctype)
        if path in ("/config", "/config/"):
            if not self._is_local():
                return self._send(403, "Configuratorul se deschide doar pe Mac: http://localhost:8765/config", "text/plain")
            with open(os.path.join(WEB, "config.html"), "rb") as f:
                return self._send(200, f.read(), "text/html")
        if path == "/apple-touch-icon.png":
            return self._send(200, icons.app_icon_png(), "image/png",
                              {"Cache-Control": "max-age=86400"})
        m = re.match(r"^/icon-(192|512)(-maskable)?\.png$", path)
        if m:
            return self._send(200, icons.app_icon_png(int(m.group(1)), bool(m.group(2))), "image/png",
                              {"Cache-Control": "max-age=86400"})
        m = re.match(r"^/splash-(\d+)x(\d+)\.png$", path)
        if m and (int(m.group(1)), int(m.group(2))) in icons.SPLASH_SIZES:
            return self._send(200, icons.splash_png(int(m.group(1)), int(m.group(2))), "image/png",
                              {"Cache-Control": "max-age=604800"})
        if path == "/sw.js":
            with open(os.path.join(WEB, "sw.js"), encoding="utf-8") as f:
                js = f.read().replace("__VERSION__", web_version())
            return self._send(200, js, "application/javascript", {"Service-Worker-Allowed": "/"})
        if path == "/ca.crt":
            with open(certs.CA_CRT, "rb") as f:
                return self._send(200, f.read(), "application/x-x509-ca-cert",
                                  {"Content-Disposition": 'attachment; filename="MacDeck-CA.crt"'})
        if path.startswith("/icons/") and path.endswith(".png"):
            b = DECK.config.find_button(path[len("/icons/"):-4])
            p = icons.icon_path(b) if b else None
            if not p:
                return self._send(404, b"", "image/png")
            ext = os.path.splitext(p)[1].lower()
            ctype = {".jpg": "image/jpeg", ".webp": "image/webp", ".gif": "image/gif",
                     ".svg": "image/svg+xml"}.get(ext, "image/png")
            with open(p, "rb") as f:
                return self._send(200, f.read(), ctype, {"Cache-Control": "max-age=86400"})

        if not path.startswith("/api/"):
            return self._json(404, {"error": "not found"})
        if not self._authed(query):
            return self._json(401, {"error": "neasociat"})

        if path == "/api/config":
            return self._json(200, {"config": DECK.config.get(), "state": DECK.state(),
                                    "sim": system.SIM})
        if path == "/api/events":
            return self._events()
        if path == "/api/admin/meta" and self._is_local():
            return self._json(200, admin.meta())
        if path.startswith("/api/page/"):
            try:
                return self._json(200, DECK.features.page_state(path[len("/api/page/"):]))
            except Exception as e:
                return self._json(200, {"error": str(e)})
        return self._json(404, {"error": "not found"})

    def _events(self):
        q = DECK.hub.add()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        self.close_connection = True
        try:
            self.wfile.write(b"retry: 1500\n\n")
            DECK.push_state(force=True)
            while True:
                try:
                    data = q.get(timeout=15)
                    self.wfile.write(("data: %s\n\n" % data).encode("utf-8"))
                except queue.Empty:
                    self.wfile.write(b": ping\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ssl.SSLError, OSError):
            pass
        finally:
            DECK.hub.remove(q)

    # -------------------------------------------------------- POST
    def do_POST(self):
        url = urlsplit(self.path)
        path, query = url.path, parse_qs(url.query)
        try:
            body = self._body()
        except ValueError:
            return self._json(400, {"error": "JSON invalid"})

        if path == "/api/pair":
            token = DECK.auth.pair(body.get("code", ""))
            return self._json(200 if token else 403, {"token": token} if token else {"error": "cod greșit"})

        if not self._authed(query):
            return self._json(401, {"error": "neasociat"})
        if path.startswith("/api/admin/"):
            if not self._is_local():
                return self._json(403, {"error": "doar de pe Mac"})
            return self._admin(path, body)
        if path.startswith("/api/page/"):
            try:
                msg = DECK.features.page_cmd(path[len("/api/page/"):], body)
                return self._json(200, {"ok": True, "msg": msg if isinstance(msg, str) else ""})
            except Exception as e:
                return self._json(200, {"ok": False, "msg": str(e)})
        try:
            if path == "/api/action":
                return self._json(200, DECK.run_button(body.get("id"), bool(body.get("long")),
                                                       body.get("choice")))
            if path == "/api/system":
                if "volume" in body:
                    system.set_volume(body["volume"])
                if body.get("mute"):
                    system.toggle_mute()
                if "brightness" in body:
                    system.set_brightness(body["brightness"])
                DECK.push_state(force=True)
                return self._json(200, {"ok": True})
        except Exception as e:
            return self._json(200, {"ok": False, "msg": str(e)})
        return self._json(404, {"error": "not found"})


    def _admin(self, path, body):
        try:
            if path == "/api/admin/config":
                cfg = body.get("config")
                errs = admin.validate(cfg)
                if errs:
                    return self._json(200, {"ok": False, "errors": errs})
                DECK.config.save(cfg)
                DECK.hub.send({"type": "config"})
                return self._json(200, {"ok": True})
            if path == "/api/admin/icon":
                return self._json(200, {"ok": True, "file": admin.save_icon(body.get("id"), body.get("data"))})
            if path == "/api/admin/simfront" and system.SIM:
                DECK.features._sim_front = body.get("app")
                return self._json(200, {"ok": True})
            if path == "/api/admin/info":
                from . import autostart
                info = dict(getattr(DECK, "urls", {}), code=DECK.auth.code, phones=len(DECK.auth.tokens),
                            mac=system.IS_MAC)
                if system.IS_MAC:
                    info.update(autostart=autostart.installed(), python=autostart.real_python())
                return self._json(200, {"ok": True, "info": info})
            if path == "/api/admin/autostart":
                from . import autostart
                if not system.IS_MAC:
                    return self._json(200, {"ok": False, "msg": "doar pe macOS"})
                if body.get("on"):
                    autostart.install()
                    return self._json(200, {"ok": True, "msg": "Pornire automată activată. Închide fereastra Terminal: serverul rulează acum în fundal."})
                autostart.uninstall()
                return self._json(200, {"ok": True, "msg": "Pornire automată oprită."})
            if path == "/api/admin/uidump":
                return self._json(200, {"ok": True, "items": uiauto.dump(body.get("app") or "")})
            if path == "/api/admin/test":
                try:
                    return self._json(200, {"ok": True, "msg": actions.execute(body.get("action") or {}, DECK.ctx())})
                except actions.Soon as e:
                    return self._json(200, {"ok": False, "msg": "Vine în etapa %s" % e.phase})
        except Exception as e:
            return self._json(200, {"ok": False, "msg": str(e)})
        return self._json(404, {"error": "not found"})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        pass  # conexiuni întrerupte, certificat încă neacceptat pe telefon etc.


def serve(http_port=8765, https_port=8766):
    global DECK
    DECK = Deck()
    host = system.hostname_local()
    ip = system.local_ip()

    try:
        servers = [Server(("0.0.0.0", http_port), Handler)]
    except OSError as e:
        if getattr(e, "errno", None) in (48, 98):  # adresă ocupată (macOS / Linux)
            print("\n  Mac Deck rulează deja (probabil pornit automat, în fundal).")
            print("  Configurator: http://localhost:%d/config\n" % http_port)
            sys.exit(3)
        raise
    https_ok = False
    try:
        crt, key = certs.ensure([host], [ip])
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(crt, key)
        s = Server(("0.0.0.0", https_port), Handler)
        # handshake-ul se face în firul fiecărei cereri, nu blochează serverul
        s.socket = ctx.wrap_socket(s.socket, server_side=True, do_handshake_on_connect=False)
        servers.append(s)
        https_ok = True
    except Exception as e:
        print("  ! HTTPS indisponibil (%s). Deck-ul merge pe HTTP." % e)

    DECK.urls = {
        "deck": ("https://%s:%d" % (host, https_port)) if https_ok else ("http://%s:%d" % (host, http_port)),
        "deck_ip": ("https://%s:%d" % (ip, https_port)) if https_ok else ("http://%s:%d" % (ip, http_port)),
        "setup": "http://%s:%d/setup" % (host, http_port),
        "setup_ip": "http://%s:%d/setup" % (ip, http_port),
    }
    for s in servers:
        threading.Thread(target=s.serve_forever, daemon=True).start()
    threading.Thread(target=DECK.poll_forever, daemon=True).start()
    DECK.features.start()

    print()
    print("  ┌─ Mac Deck pornit" + ("  (MOD SIMULAT)" if system.SIM else ""))
    print("  │")
    if https_ok:
        print("  │  Pe iPhone deschide:   https://%s:%d" % (host, https_port))
        print("  │  (sau prin IP:          https://%s:%d)" % (ip, https_port))
        print("  │  Prima dată, certificatul: http://%s:%d/setup" % (host, http_port))
    else:
        print("  │  Pe iPhone deschide:   http://%s:%d" % (host, http_port))
    print("  │")
    print("  │  Cod de asociere:  %s" % DECK.auth.code)
    print("  │  Configurator:     http://localhost:%d/config" % http_port)
    print("  │  Configurație:     %s" % DECK.config.path)
    print("  └─ Ctrl+C pentru oprire")
    print()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print("\n  Oprit.")
