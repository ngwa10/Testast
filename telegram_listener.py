print(">>> [DEBUG] telegram_listener.py is starting <<<")

try:
    from telethon import TelegramClient, events
    print(">>> [DEBUG] telethon imported <<<")
except Exception as e:
    print(f">>> [DEBUG] Failed to import telethon: {e}")
    raise

import re
from datetime import datetime, timedelta
import logging
import traceback
import time

try:
    import core
    print(">>> [DEBUG] core imported <<<")
    import shared
    print(">>> [DEBUG] shared imported <<<")
except Exception as e:
    print(f">>> [DEBUG] Failed to import core/shared: {e}")
    raise

try:
    from core_utils import timezone_convert
    print(">>> [DEBUG] core_utils.timezone_convert imported <<<")
except Exception:
    timezone_convert = None
    print(">>> [DEBUG] core_utils.timezone_convert NOT FOUND <<<")

api_id = 29630724
api_hash = "8e12421a95fd722246e0c0b194fd3e0c"
bot_token = "8477806088:AAGEXpIAwN5tNQM0hsCGqP-otpLJjPJLmWA"
TARGET_CHAT_ID = -1003033183667

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("telegram_listener")

print(">>> [DEBUG] Logging configured <<<")

def log_info(msg):
    logger.info(msg)

def log_error(msg):
    logger.error(msg)

def parse_signal(message_text: str):
    print(f">>> [DEBUG] parse_signal called <<<")
    # ... (your actual parsing code here)
    return None  # for now, just a stub

def start_telegram_listener():
    print(">>> [DEBUG] start_telegram_listener called <<<")
    client = TelegramClient('bot_session', api_id, api_hash)
    print(">>> [DEBUG] TelegramClient initialized <<<")

    @client.on(events.NewMessage(chats=TARGET_CHAT_ID))
    async def handler(event):
        try:
            print(">>> [DEBUG] handler triggered <<<")
            text = event.message.message or ""
            print(f">>> [DEBUG] Received message: {text} <<<")
            if text.startswith("/start") or text.startswith("/stop"):
                print(f">>> [DEBUG] Detected command: {text} <<<")
            else:
                parsed = parse_signal(text)
                print(f">>> [DEBUG] Parsed signal: {parsed} <<<")
        except Exception as e:
            print(f">>> [DEBUG] Exception in handler: {e} <<<")
            print(traceback.format_exc())

    try:
        print(">>> [DEBUG] About to connect to Telegram... <<<")
        client.start(bot_token=bot_token)
        print(">>> [DEBUG] Connected to Telegram. Listening for messages... <<<")
        client.run_until_disconnected()
    except Exception as e:
        print(f">>> [DEBUG] Exception in listener: {e} <<<")
        print(traceback.format_exc())

if __name__ == "__main__":
    print(">>> [DEBUG] __main__ section <<<")
    start_telegram_listener()
