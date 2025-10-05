import sys
import time
import traceback
from telethon import TelegramClient, events

# --- Imports for direct core interaction ---
import core
import shared  # shared.trade_manager will be initialized by core

api_id = 29630724
api_hash = "8e12421a95fd722246e0c0b194fd3e0c"
bot_token = "YOUR_BOT_TOKEN"
TARGET_CHAT_ID = -1003033183667

def wait_for_trademanager_ready(max_wait_sec=10):
    waited = 0
    while getattr(shared, "trade_manager", None) is None and waited < max_wait_sec:
        print("[⏳] Waiting for TradeManager to initialize...")
        time.sleep(0.5)
        waited += 0.5
    return getattr(shared, "trade_manager", None) is not None

def parse_signal(message_text: str):
    # ... your full parse_signal logic ...
    return None  # stub for now

def start_telegram_listener():
    print("[🚀] Telegram listener script started.")
    client = TelegramClient('bot_session', api_id, api_hash)

    @client.on(events.NewMessage(chats=TARGET_CHAT_ID))
    async def handler(event):
        try:
            text = event.message.message or ""
            if text.startswith("/start") or text.startswith("/stop"):
                print(f"[💻] Command detected: {text}")
                if wait_for_trademanager_ready():
                    core.handle_command(text)
                    print(f"[🤖] Command sent to core: {text}")
                else:
                    print("[⚠️] TradeManager not ready for command.")
                return

            parsed = parse_signal(text)
            if parsed:
                print(f"[⚡] Parsed signal: {parsed}")
                if wait_for_trademanager_ready():
                    core.signal_callback(parsed)
                    print("[🤖] Signal sent to core.signal_callback")
                else:
                    print("[⚠️] TradeManager not ready for signal.")
            else:
                print("[ℹ️] Message ignored (not a valid signal).")
        except Exception as e:
            print(f"[❌] Handler error: {e}")
            traceback.print_exc()

    try:
        print("[⚙️] Connecting to Telegram...")
        client.start(bot_token=bot_token)
        print("[✅] Connected to Telegram. Listening for messages...")
        client.run_until_disconnected()
    except Exception as e:
        print(f"[❌] Telegram listener failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    start_telegram_listener()
