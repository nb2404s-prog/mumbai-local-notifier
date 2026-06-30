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
from flask import Flask, request
import requests

app = Flask(__name__)

# ─── CONFIG (set these in Render Environment Variables) ──────────────────────

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
RAILRADAR_API_KEY = os.environ.get("RAILRADAR_API_KEY")

TRAINS = {
    "98189": "6:14 PM Local",
    "98191": "6:27 PM Local"
}

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Track active /track sessions per chat_id to avoid duplicate loops
active_tracking = {}

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
    """Normalize RailRadar response into a flat dict. Adjust keys if needed."""
    if not raw:
        return None
    data = raw.get("data", raw)
    live = data.get("liveData", data)
    return {
        "train": data.get("trainNumber", data.get("train_number", "")),
        "current_station": live.get("currentStation", live.get("current_station", "Unknown")),
        "next_station": live.get("nextStation", live.get("next_station", "Unknown")),
        "delay": live.get("delay", live.get("delayMinutes", 0)) or 0,
        "status": live.get("status", live.get("currentPosition", ""))
    }

def format_status_message(alias, status):
    delay = status["delay"]
    if delay == 0:
        delay_text = "✅ On Time"
    elif delay <= 5:
        delay_text = f"🟡 {delay} min late"
    else:
        delay_text = f"🔴 {delay} min late"

    time_str = datetime.now().strftime("%I:%M %p")

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
        now = datetime.now()
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
