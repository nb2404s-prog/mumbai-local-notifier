import json
import os

STATE_FILE = "state.json"


def load_state():
    if not os.path.exists(STATE_FILE):
        return {}

    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=4)


def has_changed(old, new):
    return (
        old.get("current_station") != new.get("current_station")
        or old.get("status") != new.get("status")
        or old.get("delay") != new.get("delay")
    )