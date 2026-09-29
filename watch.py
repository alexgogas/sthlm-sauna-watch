#!/usr/bin/env python3
"""STHLM Sauna slot watcher.

Reads watches (watches.yml, or the WATCHES env var if set), checks the public
availability API at sthlmsauna.se, and sends a push notification via ntfy.sh
when a matching slot goes from full to having enough free spots.

Read-only: it never books anything.
"""
import hashlib
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import yaml

TZ = ZoneInfo("Europe/Stockholm")
API = "https://sthlmsauna.se/wp-json/sthlmsauna/v1/availability"
BOOK_URL = "https://sthlmsauna.se/boka/"
RESOURCE_ID = 1787  # Vinterviken
PRODUCTS = {
    1793: "Mixbastu",
    1792: "Dambastu",
    1786: "Herrbastu",
    25382: "Yoga & Sauna",
    78381: "Aufguss",
    87268: "Allmänhetens pass",
    36299: "Other",
    50855: "Other",
    73394: "Other",
}
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DEFAULT_LOOKAHEAD_DAYS = 14
MIN_INTERVAL_MINUTES = 5  # the workflow is triggered every 5 min, so faster is impossible
DEFAULT_INTERVAL_MINUTES = 15
STOP_BEFORE_START = timedelta(hours=1)  # no alerts for slots starting sooner than this
STATE_FILE = os.environ.get("STATE_FILE", "state.json")


def load_config():
    raw = os.environ.get("WATCHES", "").strip()
    if raw:
        data = yaml.safe_load(raw)
    else:
        with open(os.environ.get("WATCHES_FILE", "watches.yml"), encoding="utf-8") as f:
            data = yaml.safe_load(f)
    return data or {}


def watch_id(w):
    """Stable id from the watch's settings, so editing a watch re-arms it."""
    blob = json.dumps(w, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()[:10]


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            state = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        state = {}
    if "slots" not in state:  # old format: a flat dict of slot keys
        state = {"slots": {}}
    state.setdefault("done", {})
    return state


def parse_hhmm(s):
    return datetime.strptime(str(s), "%H:%M").time()


def is_expired(w, now):
    """True once the watch's last possible slot starts within STOP_BEFORE_START."""
    last_day = w.get("date") or w.get("to_date")
    if not last_day:
        return False  # open-ended watches roll forward with today
    last_time = w.get("time") or w.get("before")
    last_start = parse_hhmm(last_time) if last_time else time(23, 59)
    return datetime.combine(date.fromisoformat(str(last_day)), last_start, TZ) - STOP_BEFORE_START <= now


def watch_date_range(w, today):
    """Return (first_day, last_day) inclusive that this watch cares about."""
    if w.get("date"):
        d = date.fromisoformat(str(w["date"]))
        return d, d
    start = date.fromisoformat(str(w["from_date"])) if w.get("from_date") else today
    end = (date.fromisoformat(str(w["to_date"])) if w.get("to_date")
           else today + timedelta(days=DEFAULT_LOOKAHEAD_DAYS))
    return max(start, today), end


def fetch(persons, first_day, last_day):
    fixture = os.environ.get("SAUNA_FIXTURE")  # for offline testing
    if fixture:
        with open(fixture, encoding="utf-8") as f:
            return json.load(f)["slots"]
    frm = int(datetime.combine(first_day, time(0), TZ).timestamp())
    to = int(datetime.combine(last_day + timedelta(days=1), time(0), TZ).timestamp())
    qs = urllib.parse.urlencode({
        "product_ids": ",".join(str(p) for p in PRODUCTS),
        "from": frm, "to": to, "persons": persons, "resource_id": RESOURCE_ID,
    })
    req = urllib.request.Request(f"{API}?{qs}", headers={"User-Agent": "sthlm-sauna-watch/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["slots"]


def matches(w, slot, start):
    session = w.get("session")
    if session and PRODUCTS.get(slot["product_id"], "").lower() != str(session).lower():
        return False
    if w.get("date") and start.date() != date.fromisoformat(str(w["date"])):
        return False
    if w.get("time") and start.time() != parse_hhmm(w["time"]):
        return False
    if w.get("days"):
        if DAYS[start.weekday()] not in [str(d).lower()[:3] for d in w["days"]]:
            return False
    if w.get("after") and start.time() < parse_hhmm(w["after"]):
        return False
    if w.get("before") and start.time() > parse_hhmm(w["before"]):
        return False
    return True


def notify(title, message):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        print("NTFY_TOPIC not set; skipping notification")
        return
    server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
    req = urllib.request.Request(
        f"{server}/{topic}",
        data=message.encode("utf-8"),
        headers={
            "Title": title.encode("utf-8"),
            "Click": BOOK_URL,
            "Tags": "hot_springs",
            "Priority": "high",
        },
        method="POST",
    )
    urllib.request.urlopen(req, timeout=30).read()
    print("Notification sent")


# Workflow logs are public in a public repo, so never print watch names or slots.
def main():
    now = datetime.now(TZ)
    today = now.date()
    config = load_config()
    state = load_state()

    # The workflow fires every 5 min; skip runs until check_every_minutes has
    # passed. Half a cron period of slack stops GitHub's delays from pushing a
    # check back a whole extra cycle.
    interval = max(int(config.get("check_every_minutes", DEFAULT_INTERVAL_MINUTES)), MIN_INTERVAL_MINUTES)
    last = state.get("last_check")
    if last:
        elapsed = (now - datetime.fromisoformat(last)).total_seconds() / 60
        if elapsed < interval - MIN_INTERVAL_MINUTES / 2:
            print(f"Last check {elapsed:.0f} min ago, interval {interval} min; skipping")
            return

    # A watch stops once it has alerted. Only done ids that still exist are
    # kept, so editing or re-adding a watch starts checking it again.
    watches = [(watch_id(w), w) for w in config.get("watches") or []]
    done = {i: t for i, t in state["done"].items() if i in {i for i, _ in watches}}
    expired = sum(1 for i, w in watches if i not in done and is_expired(w, now))
    active = [(i, w) for i, w in watches if i not in done and not is_expired(w, now)]
    if not active:
        print(f"Nothing to check: {len(done)} watch(es) found a slot, {expired} expired")
        state = {"slots": {}, "done": done, "last_check": now.isoformat()}
        save_state(state)
        return

    # One API call per group size, covering all dates the watches need.
    ranges = {}
    for _, w in active:
        p = int(w.get("persons", 1))
        a, b = watch_date_range(w, today)
        if b < a:
            continue
        lo, hi = ranges.get(p, (a, b))
        ranges[p] = (min(lo, a), max(hi, b))

    slots_by_persons = {}
    for p, (a, b) in ranges.items():
        try:
            slots_by_persons[p] = fetch(p, a, b)
        except Exception as e:  # keep going for other group sizes
            print(f"Fetch failed for persons={p}: {e}", file=sys.stderr)

    # Keep previous state for group sizes whose fetch failed (avoids re-alerts).
    failed = {p for p in ranges if p not in slots_by_persons}
    old_slots = state["slots"]
    new_slots = {k: v for k, v in old_slots.items() if int(k.rsplit("|", 1)[1]) in failed}
    checked = alerts = 0
    for wid, w in active:
        p = int(w.get("persons", 1))
        name = w.get("name") or "watch"
        for slot in slots_by_persons.get(p, []):
            start = datetime.fromisoformat(slot["start"]).astimezone(TZ)
            if start - STOP_BEFORE_START <= now or not matches(w, slot, start):
                continue
            key = f"{wid}|{slot['product_id']}|{slot['start']}|{p}"
            avail = int(slot.get("available", 0))
            prev = old_slots.get(key)
            new_slots[key] = avail
            checked += 1
            # Alert when it becomes bookable. The first time a slot is seen we
            # only alert if the watch says so (default: yes).
            was_open = prev is not None and prev >= p
            first_seen = prev is None
            if avail >= p and not was_open and (not first_seen or w.get("alert_if_already_open", True)):
                sess = PRODUCTS.get(slot["product_id"], "Sauna")
                when = start.strftime("%a %d %b %H:%M")
                notify(f"🧖 {sess} {when}",
                       f"{avail} spot(s) free for {p} ({name}). Tap to book.")
                alerts += 1
                done[wid] = now.isoformat()

    # Slot history is only needed for watches still being checked.
    new_slots = {k: v for k, v in new_slots.items() if k.split("|", 1)[0] not in done}
    print(f"{len(active)} active watch(es), {checked} matching slot(s), {alerts} alert(s), "
          f"{len(done)} done, {expired} expired")
    save_state({"slots": new_slots, "done": done, "last_check": now.isoformat()})


def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    # Tell the workflow to save the state; skipped runs leave it untouched.
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write("state_changed=true\n")


if __name__ == "__main__":
    main()
