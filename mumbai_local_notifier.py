"""
Mumbai Local Train Notifier
============================
Polls live status for Mumbai local trains via NTES
and sends desktop/console notifications on delays or arrival.

Install dependencies:
    pip install ntes-client plyer

Usage:
    python mumbai_local_notifier.py
"""

from ntes import NTESClient
from datetime import datetime
import time
import json
import sys

# ─── CONFIG ──────────────────────────────────────────────────────────────────

TRAINS = [
    {"number": "98189", "name": "Harbour Slow Local"},
    {"number": "98191", "name": "Harbour Slow Local"},
]

# How often to poll in seconds (60 = every 1 minute)
POLL_INTERVAL = 60

# Alert if train is delayed more than this many minutes
DELAY_ALERT_THRESHOLD = 5

# Station code you care about (e.g. PNVL = Panvel, CSMT = Mumbai CSMT)
# Set to None to get full route status
TARGET_STATION = None

# ─── NOTIFICATION ─────────────────────────────────────────────────────────────

def notify(title, message):
    """Send a desktop notification. Falls back to console print."""
    try:
        from plyer import notification
        notification.notify(
            title=title,
            message=message,
            app_name="Mumbai Local Notifier",
            timeout=10
        )
    except Exception:
        pass
    # Always print to console too
    print(f"\n🔔 [{datetime.now().strftime('%H:%M:%S')}] {title}")
    print(f"   {message}")

# ─── STATUS FETCHER ───────────────────────────────────────────────────────────

def fetch_status(client, train_number):
    """Fetch live status for a train. Returns parsed dict or None on failure."""
    today = datetime.now().strftime("%d-%b-%Y")
    try:
        status = client.live_status(train_number, today)
        return status
    except Exception as e:
        print(f"  ⚠️  Could not fetch {train_number}: {e}")
        return None

def parse_delay(status):
    """Extract delay minutes from status dict. Returns int or None."""
    if not status:
        return None
    # ntes-client returns a dict — try common keys
    for key in ["delayInArrival", "delay", "lateBy", "delay_minutes"]:
        val = status.get(key)
        if val is not None:
            try:
                return int(str(val).replace("min", "").strip())
            except ValueError:
                pass
    return None

def parse_current_station(status):
    """Extract current station name from status dict."""
    if not status:
        return "Unknown"
    for key in ["currentStation", "current_station", "stationName", "station"]:
        val = status.get(key)
        if val:
            return val
    return "Unknown"

def parse_running_status(status):
    """Returns a human-readable one-liner of train status."""
    if not status:
        return "No data"
    delay = parse_delay(status)
    station = parse_current_station(status)
    if delay is not None:
        if delay == 0:
            return f"On time — currently at {station}"
        elif delay > 0:
            return f"Running {delay} min late — currently at {station}"
        else:
            return f"Running {abs(delay)} min early — currently at {station}"
    return f"Currently at {station}"

# ─── MAIN LOOP ────────────────────────────────────────────────────────────────

def main():
    client = NTESClient(timeout=15, retries=3)
    print("=" * 55)
    print("  🚆 Mumbai Local Train Notifier")
    print("=" * 55)
    print(f"  Monitoring trains: {[t['number'] for t in TRAINS]}")
    print(f"  Poll interval   : {POLL_INTERVAL}s")
    print(f"  Delay threshold : {DELAY_ALERT_THRESHOLD} min")
    print("=" * 55)

    # Track last known delay per train to avoid repeated alerts
    last_delay = {t["number"]: None for t in TRAINS}
    last_station = {t["number"]: None for t in TRAINS}

    while True:
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now}] Polling {len(TRAINS)} trains...")

        for train in TRAINS:
            num = train["number"]
            name = train["name"]
            print(f"\n  → Train {num} ({name})")

            status = fetch_status(client, num)

            if status is None:
                print(f"     Status: Could not fetch (NTES may not have data yet)")
                continue

            # Print raw status for debugging on first run
            readable = parse_running_status(status)
            delay = parse_delay(status)
            station = parse_current_station(status)

            print(f"     Status : {readable}")

            # Alert on new delay exceeding threshold
            if delay is not None and delay >= DELAY_ALERT_THRESHOLD:
                if last_delay[num] != delay:
                    notify(
                        f"🚆 Train {num} Delayed!",
                        f"{name} is running {delay} min late.\nCurrently at: {station}"
                    )
                    last_delay[num] = delay

            # Alert when train reaches target station
            if TARGET_STATION and station:
                if TARGET_STATION.lower() in station.lower():
                    if last_station[num] != station:
                        notify(
                            f"🚉 Train {num} at {TARGET_STATION}",
                            f"{name} has reached {station}"
                        )
                        last_station[num] = station

            # Alert when train is on time after being delayed
            if delay == 0 and last_delay[num] and last_delay[num] > 0:
                notify(
                    f"✅ Train {num} Back on Time",
                    f"{name} is now running on time at {station}"
                )
                last_delay[num] = 0

        print(f"\n  ⏳ Next poll in {POLL_INTERVAL}s... (Ctrl+C to stop)")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Notifier stopped.")
        sys.exit(0)
