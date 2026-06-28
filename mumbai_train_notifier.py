"""
Mumbai Local Train Telegram Notifier
=====================================
Polls NTES for live train status and sends Telegram alerts.
Designed to run 24/7 on Render.com free tier.
"""

import time
import requests
from datetime import datetime
from ntes import NTESClient

# ─── CONFIG ───────────────────────────────────────────────────────────────────

BOT_TOKEN = "8849944285:AAEBIe0chdC_NqT3AC1JOWpZMHQNMMQevtl"
CHAT_ID = "7798637728"

TRAINS = [
    {"number": "98189", "name": "Harbour Slow Local"},
    {"number": "98191", "name": "Harbour Slow Local"},
]

POLL_INTERVAL = 60          # seconds between each check
DELAY_THRESHOLD = 5         # alert if delayed more than this many minutes

# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

def send_telegram(message):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "HTML"
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            print(f"  ✅ Telegram sent: {message[:60]}...")
        else:
            print(f"  ❌ Telegram error: {r.text}")
    except Exception as e:
        print(f"  ❌ Telegram exception: {e}")

# ─── NTES HELPERS ─────────────────────────────────────────────────────────────

def fetch_status(client, train_number):
    today = datetime.now().strftime("%d-%b-%Y")
    try:
        return client.live_status(train_number, today)
    except Exception as e:
        print(f"  ⚠️  NTES error for {train_number}: {e}")
        return None

def get_delay(status):
    if not status:
        return None
    for key in ["delayInArrival", "delay", "lateBy", "delay_minutes"]:
        val = status.get(key)
        if val is not None:
            try:
                return int(str(val).replace("min", "").strip())
            except ValueError:
                pass
    return None

def get_station(status):
    if not status:
        return "Unknown"
    for key in ["currentStation", "current_station", "stationName", "station"]:
        val = status.get(key)
        if val:
            return val
    return "Unknown"

# ─── MAIN LOOP ────────────────────────────────────────────────────────────────

def main():
    client = NTESClient(timeout=15, retries=3)
    last_delay = {t["number"]: None for t in TRAINS}

    print("🚆 Mumbai Local Train Notifier started")
    send_telegram("🚆 <b>Mumbai Local Notifier started!</b>\nMonitoring trains: " +
                  ", ".join(t["number"] for t in TRAINS))

    while True:
        now = datetime.now().strftime("%H:%M:%S")
        print(f"\n[{now}] Polling...")

        for train in TRAINS:
            num = train["number"]
            name = train["name"]

            status = fetch_status(client, num)

            if status is None:
                print(f"  {num}: No data from NTES")
                continue

            delay = get_delay(status)
            station = get_station(status)

            # Summary line in console
            if delay is not None:
                label = "on time" if delay == 0 else f"{delay} min late"
                print(f"  {num}: {label} at {station}")
            else:
                print(f"  {num}: at {station} (delay unknown)")

            # Alert: newly delayed beyond threshold
            if delay is not None and delay >= DELAY_THRESHOLD:
                if last_delay[num] != delay:
                    send_telegram(
                        f"⚠️ <b>Train {num} Delayed!</b>\n"
                        f"🚂 {name}\n"
                        f"⏱ Running <b>{delay} min late</b>\n"
                        f"📍 Currently at: {station}\n"
                        f"🕐 Checked at: {now}"
                    )
                    last_delay[num] = delay

            # Alert: back on time after being delayed
            elif delay == 0 and last_delay[num] and last_delay[num] > 0:
                send_telegram(
                    f"✅ <b>Train {num} is back on time!</b>\n"
                    f"🚂 {name}\n"
                    f"📍 Currently at: {station}\n"
                    f"🕐 Checked at: {now}"
                )
                last_delay[num] = 0

            elif delay is not None:
                last_delay[num] = delay

        print(f"  ⏳ Sleeping {POLL_INTERVAL}s...")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
