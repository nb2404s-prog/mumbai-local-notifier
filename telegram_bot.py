import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def send_message(message):

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    response = requests.post(url, json=payload)

    response.raise_for_status()

    return response.json()


if __name__ == "__main__":

    send_message("✅ Mumbai Local Notifier is connected successfully!")

    print("Telegram test message sent.")