from railradar import get_live_status, extract_status
from state_manager import load_state, save_state
from telegram_bot import send_message
from datetime import datetime

trains = {
    "98189": {"alias": "6:14 PM Local"},
    "98191": {"alias": "6:27 PM Local"}
}


def main():

    previous_state = load_state()
    current_state = {}
    now = datetime.utcnow()
    time_str = datetime.now().strftime("%I:%M %p")

    for train, train_info in trains.items():

        alias = train_info["alias"]

        try:
            raw = get_live_status(train)
            status = extract_status(raw)

            current_state[train] = {
                "current_station": status["current_station"],
                "status": status["status"],
                "delay": status["delay"]
            }

            # Delay emoji
            delay = status["delay"]
            if delay == 0:
                delay_text = "✅ On Time"
            elif delay <= 5:
                delay_text = f"🟡 {delay} min late"
            else:
                delay_text = f"🔴 {delay} min late"

            # Always send full status every run
            message = (
                f"🚆 {alias}\n"
                f"━━━━━━━━━━━━━━━\n"
                f"🔢 Train   : {status['train']}\n"
                f"📍 Current : {status['current_station']}\n"
                f"➡️ Next    : {status['next_station']}\n"
                f"⏱ Delay   : {delay_text}\n"
                f"🕐 Updated : {time_str}"
            )

            print(f"[SENT] {alias} | {status['current_station']} | Delay: {delay} min")
            send_message(message)

        except Exception as e:
            print(f"[ERROR] {alias}: {e}")
            send_message(f"⚠️ {alias} - Could not fetch status\nError: {str(e)}")

    save_state(current_state)


if __name__ == "__main__":
    main()
