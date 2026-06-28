from railradar import get_live_status, extract_status
from state_manager import load_state, save_state, has_changed
from telegram_bot import send_message

trains = {
    "98189": {
        "alias": "6:14 PM Local"
    },
    "98191": {
        "alias": "6:27 PM Local"
    }
}


def main():

    previous_state = load_state()
    current_state = {}

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

            if train not in previous_state:

                message = (
                    f"🚆 {alias}\n\n"
                    f"Train Number : {status['train']}\n"
                    f"Current Station : {status['current_station']}\n"
                    f"Next Station : {status['next_station']}\n"
                    f"Delay : {status['delay']} min"
                )

                print(f"[NEW] {alias}")
                send_message(message)

            elif has_changed(previous_state[train], current_state[train]):

                message = (
                    f"🚆 {alias}\n\n"
                    f"Train Number : {status['train']}\n"
                    f"Current Station : {status['current_station']}\n"
                    f"Next Station : {status['next_station']}\n"
                    f"Delay : {status['delay']} min"
                )

                print(f"[UPDATED] {alias}")
                send_message(message)

            else:

                print(f"[NO CHANGE] {alias}")
                send_message(f"✅ {alias} - No change")

        except Exception as e:

            print(f"{alias}: {e}")

    save_state(current_state)


if __name__ == "__main__":
    main()