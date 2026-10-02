#!/usr/bin/env python3
"""One-shot Ticketmaster check, designed for a scheduled GitHub Action.
Compares against state.json from the previous run and notifies on changes."""
import json
import os
import pathlib

import requests

API_KEY = os.environ["TM_API_KEY"]
EVENT_IDS = [e.strip() for e in os.environ["EVENT_IDS"].split(",") if e.strip()]
NTFY_TOPIC = os.environ["NTFY_TOPIC"]

STATE_FILE = pathlib.Path("state.json")
API = "https://app.ticketmaster.com/discovery/v2/events/{}.json"


def notify(title, message, url=None):
    headers = {"Title": title, "Priority": "urgent", "Tags": "tickets"}
    if url:
        headers["Click"] = url
    requests.post(f"https://ntfy.sh/{NTFY_TOPIC}",
                  data=message.encode("utf-8"), headers=headers, timeout=10)


def snapshot(event_id):
    r = requests.get(API.format(event_id), params={"apikey": API_KEY}, timeout=15)
    r.raise_for_status()
    ev = r.json()
    return {
        "name": ev.get("name", event_id),
        "status": ev.get("dates", {}).get("status", {}).get("code", "unknown"),
        "has_prices": bool(ev.get("priceRanges")),
        "url": ev.get("url"),
        "date": ev.get("dates", {}).get("start", {}).get("localDate", ""),
    }


def main():
    state = json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}
    for eid in EVENT_IDS:
        try:
            s = snapshot(eid)
        except requests.RequestException as e:
            print(f"[{eid}] error: {e}")
            continue

        prev = state.get(eid)
        print(f"{s['name']} {s['date']}: {s['status']} prices={s['has_prices']}")

        if prev is None:
            notify("Ticket watcher is live",
                   f"{s['name']} ({s['date']}) currently: {s['status']}", s["url"])
        elif ((s["status"] == "onsale" and prev["status"] != "onsale")
              or (s["has_prices"] and not prev["has_prices"])):
            notify(f"Tickets available: {s['name']}",
                   f"{s['date']} status is now '{s['status']}'. Go go go!", s["url"])
        state[eid] = {k: s[k] for k in ("status", "has_prices")}

    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
