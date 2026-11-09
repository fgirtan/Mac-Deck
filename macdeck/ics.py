"""Următorul meeting din Google Calendar, citit din adresa secretă iCal a calendarului
(Google Calendar → Settings → calendarul tău → „Secret address in iCal format”).
Suportă evenimente recurente simple (DAILY / WEEKLY cu BYDAY, INTERVAL, UNTIL, COUNT, EXDATE)."""
import datetime as dt
import re
import urllib.request

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

UTC = dt.timezone.utc
DAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}
MEET_RE = re.compile(r"https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}")
URL_RE = re.compile(r"https://[^\s\\<>\"]+")


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "mac-deck"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def _parse_dt(value, params):
    """Întoarce (datetime aware, all_day)."""
    if re.match(r"^\d{8}$", value):
        return dt.datetime.strptime(value, "%Y%m%d").replace(tzinfo=UTC), True
    base = dt.datetime.strptime(value.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        return base.replace(tzinfo=UTC), False
    tz = params.get("TZID")
    if tz and ZoneInfo:
        try:
            return base.replace(tzinfo=ZoneInfo(tz)), False
        except Exception:
            pass
    return base.astimezone(), False  # ora locală


def parse(text):
    events, cur = [], None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT":
            cur = {"exdate": []}
        elif line == "END:VEVENT":
            if cur and "start" in cur:
                events.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            head, value = line.split(":", 1)
            name, *ps = head.split(";")
            params = dict(p.split("=", 1) for p in ps if "=" in p)
            if name == "DTSTART":
                cur["start"], cur["all_day"] = _parse_dt(value, params)
            elif name == "DTEND":
                cur["end"] = _parse_dt(value, params)[0]
            elif name == "SUMMARY":
                cur["title"] = value.replace("\\,", ",").replace("\\;", ";").replace("\\n", " ")
            elif name == "RRULE":
                cur["rrule"] = dict(p.split("=", 1) for p in value.split(";") if "=" in p)
            elif name == "EXDATE":
                for v in value.split(","):
                    cur["exdate"].append(_parse_dt(v, params)[0])
            elif name in ("LOCATION", "DESCRIPTION", "X-GOOGLE-CONFERENCE"):
                cur.setdefault("text", "")
                cur["text"] += " " + value.replace("\\n", " ")
            elif name == "RECURRENCE-ID":
                cur["recurrence_id"] = _parse_dt(value, params)[0]
            elif name == "UID":
                cur["uid"] = value
            elif name == "STATUS":
                cur["status"] = value
    return events


def _occurrences(ev, start, end):
    """Aparițiile evenimentului în intervalul [start, end)."""
    s = ev["start"]
    dur = (ev.get("end") or s) - s
    rr = ev.get("rrule")
    if not rr:
        if start <= s + dur and s < end:
            yield s
        return
    freq = rr.get("FREQ")
    interval = int(rr.get("INTERVAL", "1"))
    until = None
    if "UNTIL" in rr:
        until = _parse_dt(rr["UNTIL"], {})[0]
    count = int(rr["COUNT"]) if "COUNT" in rr else None
    bydays = [DAYS[d[-2:]] for d in rr.get("BYDAY", "").split(",") if d[-2:] in DAYS]
    ex = set(ev.get("exdate", []))
    n = 0
    if freq == "DAILY":
        step, cand = dt.timedelta(days=interval), s
        while cand < end and n < 2000:
            if until and cand > until:
                return
            n += 1
            if count and n > count:
                return
            if cand + dur >= start and cand not in ex:
                yield cand
            cand += step
    elif freq == "WEEKLY":
        days = sorted(bydays or [s.weekday()])
        week0 = s - dt.timedelta(days=s.weekday())
        w = 0
        while n < 2000:
            wk = week0 + dt.timedelta(weeks=w * interval)
            if wk > end:
                return
            for d in days:
                cand = wk + dt.timedelta(days=d)
                if cand < s:
                    continue
                if until and cand > until:
                    return
                n += 1
                if count and n > count:
                    return
                if cand + dur >= start and cand < end and cand not in ex:
                    yield cand
            w += 1
    # alte frecvențe (MONTHLY, YEARLY): doar prima apariție
    elif start <= s < end:
        yield s


def next_meeting(text, now=None, horizon_hours=96):
    now = now or dt.datetime.now(UTC)
    end = now + dt.timedelta(hours=horizon_hours)
    events = parse(text)
    overrides = {(e.get("uid"), e["recurrence_id"]) for e in events if e.get("recurrence_id")}
    best = None
    for ev in events:
        if ev.get("all_day") or ev.get("status") == "CANCELLED":
            continue
        dur = (ev.get("end") or ev["start"]) - ev["start"]
        for occ in _occurrences(ev, now - dur, end):
            if ev.get("rrule") and (ev.get("uid"), occ) in overrides:
                continue  # înlocuită de o excepție
            if occ + dur <= now:
                continue
            if best is None or occ < best[0]:
                best = (occ, ev, dur)
    if not best:
        return None
    occ, ev, dur = best
    text_all = ev.get("text", "")
    m = MEET_RE.search(text_all) or URL_RE.search(text_all)
    return {"title": ev.get("title", "(fără titlu)"), "start": occ.timestamp(),
            "end": (occ + dur).timestamp(), "link": m.group(0) if m else None}
