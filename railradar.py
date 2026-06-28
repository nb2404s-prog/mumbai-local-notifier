import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("RAILRADAR_API_KEY")
BASE_URL = "https://api.railradar.in/v1"


def get_live_status(train_number):
    url = f"{BASE_URL}/trains/{train_number}/live"

    headers = {
        "Authorization": f"Bearer {API_KEY}"
    }

    response = requests.get(url, headers=headers)
    response.raise_for_status()

    return response.json()


def extract_status(raw):
    data = raw["data"]

    current = data["currentLocation"]
    next_halt = data["nextHalt"]

    current_station_name = current["stationCode"]
    kurla_sequence = None

    for station in data["route"]:
        if station["stationCode"] == current["stationCode"]:
            current_station_name = station["stationName"]

        if station["stationCode"] == "CLA":
            kurla_sequence = station["sequence"]

    stations_to_kurla = None

    if kurla_sequence is not None:
        stations_to_kurla = kurla_sequence - current["sequence"]

    return {
        "train": data["trainNumber"],
        "train_name": data["trainName"],
        "status": data["status"].title(),
        "delay": data["delayMinutes"],
        "current_station": current_station_name,
        "current_sequence": current["sequence"],
        "next_station": next_halt["stationName"],
        "last_updated": data["lastUpdatedAt"],
        "stations_to_kurla": stations_to_kurla
    }


if __name__ == "__main__":
    status = extract_status(get_live_status("98189"))

    print("\n====== LIVE STATUS ======\n")

    print(f"Train            : {status['train']}")
    print(f"Train Name       : {status['train_name']}")
    print(f"Status           : {status['status']}")
    print(f"Delay            : {status['delay']} min")
    print(f"Current Station  : {status['current_station']}")
    print(f"Next Station     : {status['next_station']}")
    print(f"Stations to Kurla: {status['stations_to_kurla']}")
    print(f"Last Updated     : {status['last_updated']}")