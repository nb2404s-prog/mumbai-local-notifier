"""
Mumbai Local Train Telegram Bot - Webhook Version
====================================================
Responds to /status (anytime) and /track (auto-updates 5:45-6:45 PM IST)

Deploy on Render as a Web Service (not Background Worker).
"""

import os
import threading
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

IST = ZoneInfo('Asia/Kolkata')

def ist_now():
    return datetime.now(IST)
from flask import Flask, request
import requests

app = Flask(__name__)

# ─── CONFIG (set these in Render Environment Variables) ──────────────────────

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
RAILRADAR_API_KEY = os.environ.get("RAILRADAR_API_KEY")
MY_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")  # your personal chat id, for auto-start

TRAINS = {
    "98189": "6:14 PM Local",
    "98191": "6:27 PM Local"
}

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Track active /track sessions per chat_id to avoid duplicate loops
active_tracking = {}
last_auto_start_date = None  # prevents starting twice on the same day

# ─── TELEGRAM HELPERS ──────────────────────────────────────────────────────────

def send_message(chat_id, text):
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage", json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML"
        }, timeout=10)
    except Exception as e:
        print(f"Telegram send error: {e}")

# ─── RAILRADAR HELPERS ──────────────────────────────────────────────────────────

def get_live_status(train_number):
    """Fetch live status from RailRadar API."""
    url = f"https://api.railradar.in/v1/trains/{train_number}/live"
    headers = {"Authorization": f"Bearer {RAILRADAR_API_KEY}"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        print(f"[DEBUG] RailRadar raw response for {train_number}: {data}")
        return data
    except Exception as e:
        print(f"RailRadar error for {train_number}: {e}")
        return None

def extract_status(raw):
    """Normalize RailRadar response into a flat dict, matching actual API structure."""
    if not raw or not raw.get("success"):
        return None

    data = raw.get("data", {})
    train = data.get("train", {})
    current = data.get("currentLocation", {}) or {}
    next_halt = data.get("nextHalt", {}) or {}
    route = data.get("route", [])

    # Build a lookup of stationCode -> stationName from the route
    code_to_name = {stop.get("stationCode"): stop.get("stationName") for stop in route}

    current_code = current.get("stationCode")
    current_station = code_to_name.get(current_code) or current_code or "Awaiting location"

    if current.get("status") == "at-station":
        current_station = f"{current_station} (at station)"
    elif current.get("isHalt") is False:
        current_station = f"Near {current_station} (moving)"

    next_station = next_halt.get("stationName") or code_to_name.get(next_halt.get("stationCode")) or "Journey Completed"

    return {
        "train": train.get("number", ""),
        "current_station": current_station,
        "next_station": next_station,
        "delay": data.get("delayMinutes", 0) or 0,
        "status": data.get("status", ""),
        "start_date": data.get("startDate")
    }

def format_status_message(alias, status):
    time_str = ist_now().strftime("%I:%M %p")

    journey_completed = False
    start_date = status.get("start_date")
    if start_date:
        try:
            today = ist_now().date()
            train_date = datetime.fromisoformat(start_date).date()
            if train_date > today:
                journey_completed = True
        except Exception:
            pass

    if status["status"] == "not-started":
        status_text = "🏁 Journey completed" if journey_completed else "⏳ Today's service has not started yet"
        return (
            f"🚆 {alias}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🔢 Train   : {status['train']}\n"
            f"{status_text}\n"
            f"🕐 Checked : {time_str}"
        )

    delay = status["delay"]
    if delay == 0:
        delay_text = "✅ On Time"
    elif delay <= 5:
        delay_text = f"🟡 {delay} min late"
    else:
        delay_text = f"🔴 {delay} min late"

    return (
        f"🚆 {alias}\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔢 Train   : {status['train']}\n"
        f"📍 Current : {status['current_station']}\n"
        f"➡️ Next    : {status['next_station']}\n"
        f"⏱ Delay   : {delay_text}\n"
        f"🕐 Updated : {time_str}"
    )

def get_all_status_text():
    messages = []
    for train_number, alias in TRAINS.items():
        raw = get_live_status(train_number)
        status = extract_status(raw)
        if status:
            messages.append(format_status_message(alias, status))
        else:
            messages.append(f"⚠️ {alias} - Could not fetch status right now")
    return "\n\n".join(messages)

# ─── TRACKING LOOP (for /track command) ──────────────────────────────────────

def tracking_loop(chat_id):
    """Sends status every 5 min until 6:45 PM IST or until stopped."""
    active_tracking[chat_id] = True
    send_message(chat_id, "🟢 Tracking started! You'll get updates every 5 minutes until 6:45 PM.\n\nSend /stop anytime to cancel.")

    while active_tracking.get(chat_id):
        now = ist_now()
        end_time = now.replace(hour=18, minute=45, second=0, microsecond=0)

        if now >= end_time:
            send_message(chat_id, "🏁 Tracking window ended (6:45 PM). Stopping updates.")
            break

        text = get_all_status_text()
        send_message(chat_id, text)

        # Sleep 5 minutes, but check every 5s if stopped
        for _ in range(60):
            if not active_tracking.get(chat_id):
                break
            time.sleep(5)

    active_tracking[chat_id] = False

# ─── WEBHOOK ENDPOINT ──────────────────────────────────────────────────────────

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json()

    if "message" not in update:
        return "ok"

    message = update["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip().lower()

    if text == "/start":
        send_message(chat_id,
            "👋 Mumbai Local Train Notifier ready!\n\n"
            "Commands:\n"
            "/status - Get live status now\n"
            "/track - Auto-updates every 5 min till 6:45 PM\n"
            "/stop - Stop tracking"
        )

    elif text == "/status":
        send_message(chat_id, "⏳ Fetching live status...")
        text_reply = get_all_status_text()
        send_message(chat_id, text_reply)

    elif text == "/track":
        if active_tracking.get(chat_id):
            send_message(chat_id, "⚠️ Tracking already running. Send /stop to cancel first.")
        else:
            thread = threading.Thread(target=tracking_loop, args=(chat_id,))
            thread.daemon = True
            thread.start()

    elif text == "/stop":
        if active_tracking.get(chat_id):
            active_tracking[chat_id] = False
            send_message(chat_id, "🛑 Tracking stopped.")
        else:
            send_message(chat_id, "No active tracking to stop.")

    else:
        send_message(chat_id, "Unknown command. Try /status, /track, or /stop")

    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "Mumbai Train Notifier Bot is running!"

# ─── AUTO-START SCHEDULER (runs inside the app, checks every 30s) ───────────

def auto_start_watcher():
    """Background thread: checks the clock and auto-starts tracking at 5:45 PM IST daily."""
    global last_auto_start_date

    while True:
        try:
            now = ist_now()
            target_start = now.replace(hour=17, minute=45, second=0, microsecond=0)
            today_str = now.strftime("%Y-%m-%d")
            is_weekday = now.weekday() < 5  # Mon-Fri

            # Trigger only once per day, within a 60s window after 5:45 PM, on weekdays
            if (is_weekday and
                target_start <= now < target_start + timedelta(seconds=60) and
                last_auto_start_date != today_str and
                MY_CHAT_ID):

                last_auto_start_date = today_str
                if not active_tracking.get(MY_CHAT_ID):
                    print(f"[AUTO-START] Starting tracking for chat {MY_CHAT_ID} at {now}")
                    thread = threading.Thread(target=tracking_loop, args=(MY_CHAT_ID,))
                    thread.daemon = True
                    thread.start()

        except Exception as e:
            print(f"[AUTO-START ERROR] {e}")

        time.sleep(30)

# Start the watcher thread when the app boots
watcher_thread = threading.Thread(target=auto_start_watcher)
watcher_thread.daemon = True
watcher_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
