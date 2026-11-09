"""Configurația deck-ului: valori implicite, încărcare, salvare, reîncărcare la modificare."""
import copy
import json
import os
import threading
import time

HOME = os.path.expanduser(os.environ.get("MACDECK_HOME", "~/.macdeck"))
CONFIG_PATH = os.path.join(HOME, "config.json")

PLAN_SAPT = (
    "Fă-mi planificarea săptămânală, citește Gmail, Slack, CRM, MeetGeek și fă-mi "
    "planificarea în Notion. Dă-mi și aici informația."
)
PLAN_ZI = "Fă-mi planificarea zilnică și adaugă în Notion task-urile."


def _app(id, label, app, **kw):
    b = {"id": id, "label": label, "action": {"type": "app", "app": app}}
    b.update(kw)
    return b


def _chrome(id, label, url, **kw):
    b = {"id": id, "label": label, "action": {"type": "chrome", "url": url}}
    match = kw.pop("match", None)
    if match:
        b["action"]["match"] = match
    b.update(kw)
    return b


def _soon(id, label, glyph, phase, **kw):
    b = {"id": id, "label": label, "icon": {"type": "glyph", "name": glyph},
         "action": {"type": "soon", "phase": phase}}
    b.update(kw)
    return b


DEFAULT_CONFIG = {
    "version": 1,
    "ui": {
        "columns": 5,
        "rows": 3,
        "sleep_minutes": 5,
        "sound": True,
        "haptics": True,
    },
    "sets": [
        {
            "name": "Lucru zilnic",
            "buttons": [
                _chrome("gmail", "Gmail", "https://mail.google.com",
                        long={"type": "chrome", "url": "https://mail.google.com/mail/?view=cm&fs=1",
                              "new_tab": True, "label": "Email nou"}),
                _app("claude", "Claude", "Claude", page="claude"),
                _app("slack", "Slack", "Slack"),
                _chrome("spotify", "Spotify", "https://open.spotify.com", page="spotify"),
                _chrome("gemini", "Gemini", "https://gemini.google.com"),

                {"id": "raport", "label": "Raport zilnic", "icon": {"type": "glyph", "name": "report"},
                 "action": {"type": "claude", "item": "Raport zilnic echipă David",
                            "prompts": [{"label": "Pornește raportul", "text": "pornește raportul"}]}},
                {"id": "planificare", "label": "Planificare", "icon": {"type": "glyph", "name": "calendar-check"},
                 "action": {"type": "claude", "item": "Planificare săptămânală workflow",
                            "prompts": [
                                {"label": "📅 Săptămânal", "text": PLAN_SAPT},
                                {"label": "☀️ Zilnic", "text": PLAN_ZI},
                            ]}},
                _chrome("david", "Dashboard David",
                        "https://david01.du.ro/daily/management/dashboard/florin"),
                _app("finder", "Finder", "Finder"),
                {"id": "chrome-fgirtan", "label": "Chrome fgirtan",
                 "icon": {"type": "app", "app": "Google Chrome"},
                 "action": {"type": "chrome_profile", "email": "fgirtan@gmail.com"}},

                _chrome("seogets", "SEO Gets", "https://seogets.com/", match="https://seogets.com"),
                _chrome("dwf", "DWF", "https://app.dwf.ro/login", match="https://app.dwf.ro"),
                _app("sfrog", "Screaming Frog", "Screaming Frog SEO Spider", page="sfrog"),
                _app("meetgeek", "MeetGeek", "MeetGeek", page="meetgeek"),
                _chrome("notion", "Notion",
                        "https://app.notion.com/p/020088990c49423d82f7f29c5b91ff3e?v=7a2f6b94707842d1ac572d3924844823",
                        match="020088990c49423d82f7f29c5b91ff3e"),
            ],
        },
        {
            "name": "Întâlniri, productivitate, SEO",
            "buttons": [
                _chrome("meet", "Google Meet", "https://meet.google.com", page="meet"),
                _chrome("calendar", "Calendar", "https://calendar.google.com",
                        long={"type": "chrome", "url": "https://calendar.google.com/calendar/r/eventedit",
                              "new_tab": True, "label": "Eveniment nou"}),
                _soon("next-meeting", "Următorul meeting", "clock", 6),
                _soon("start-day", "Pornește ziua", "sunrise", 6),
                _soon("voice", "Prompt vocal", "mic", 6),

                _soon("snippets", "Snippets", "text", 6),
                _soon("focus", "Focus", "moon", 6),
                _soon("pomodoro", "Pomodoro", "timer", 6),
                _soon("analyze", "Analizează pagina", "search", 6),
                _soon("crawl-current", "Crawl site curent", "spider", 5),

                _soon("mic-mute", "Mic mute", "mic-off", 6),
                _soon("audio-out", "Ieșire audio", "headphones", 6),
                _app("safari", "Safari", "Safari"),
                _app("mission", "Mission Control", "Mission Control"),
                _app("activity", "Activity Monitor", "Activity Monitor", page="activity"),
            ],
        },
        {
            "name": "Control Mac",
            "buttons": [
                _soon("windows", "Ferestre", "layout", 6),
                {"id": "screenshot", "label": "Screenshot", "icon": {"type": "glyph", "name": "camera"},
                 "action": {"type": "screenshot"},
                 "long": {"type": "screenshot", "mode": "screen-recording", "label": "Înregistrare ecran"}},
                {"id": "lock", "label": "Blochează Mac", "icon": {"type": "glyph", "name": "lock"},
                 "action": {"type": "lock"}},
                {"id": "display-off", "label": "Stinge ecranul", "icon": {"type": "glyph", "name": "monitor-off"},
                 "action": {"type": "display_sleep"}},
                {"id": "caffeinate", "label": "Ține treaz", "icon": {"type": "glyph", "name": "coffee"},
                 "action": {"type": "caffeinate"}, "state": "caffeinate"},
            ],
        },
    ],
    # Paginile dedicate. "phase" = etapa din SPEC.md în care primesc controalele.
    "pages": {
        "spotify": {"title": "Spotify", "phase": 3},
        "meet": {"title": "Google Meet", "phase": 3},
        "activity": {"title": "Activity Monitor", "phase": 3},
        "claude": {"title": "Claude", "phase": 4},
        "sfrog": {"title": "Screaming Frog", "phase": 5},
        "meetgeek": {"title": "MeetGeek", "phase": 5},
    },
}


class Config:
    """Ține configurația în memorie și o reîncarcă atunci când fișierul se schimbă pe disc."""

    def __init__(self, path=CONFIG_PATH, on_change=None):
        self.path = path
        self.on_change = on_change
        self._lock = threading.Lock()
        self._mtime = None
        self.data = None
        self.load()

    def load(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        if not os.path.exists(self.path):
            self.save(copy.deepcopy(DEFAULT_CONFIG))
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            print("  ! config.json invalid (%s) - folosesc configurația anterioară" % e)
            return False
        with self._lock:
            self.data = data
            self._mtime = os.path.getmtime(self.path)
        return True

    def save(self, data):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)
        with self._lock:
            self.data = data
            self._mtime = os.path.getmtime(self.path)

    def get(self):
        with self._lock:
            return self.data

    def find_button(self, button_id):
        for s in self.get().get("sets", []):
            for b in s.get("buttons", []):
                if b.get("id") == button_id:
                    return b
        return None

    def watch(self, interval=1.0):
        def loop():
            while True:
                time.sleep(interval)
                try:
                    m = os.path.getmtime(self.path)
                except OSError:
                    continue
                if m != self._mtime and self.load() and self.on_change:
                    self.on_change()
        threading.Thread(target=loop, daemon=True).start()
