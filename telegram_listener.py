"""
Telegram integration: Listener and signal parser with detailed logging.
Designed for a private channel using numeric ID.
"""

from telethon import TelegramClient, events
import re
from datetime import datetime, timedelta
import logging

# =========================
# HARD-CODED CREDENTIALS
# =========================
api_id = 29630724
api_hash = "8e12421a95fd722246e0c0b194fd3e0c"
bot_token = "8477806088:AAGEXpIAwN5tNQM0hsCGqP-otpLJjPJLmWA"
TARGET_CHAT_ID = -1003033183667  # Your private channel numeric ID

# =========================
# Logging Setup
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)

# =========================
# Telegram Client Setup
# =========================
client = TelegramClient('bot_session', api_id, api_hash)

# =========================
# Signal Parser
# =========================
def parse_signal(message_text):
    """
    Parses trading signals from a Telegram message text.
    Returns a dictionary with:
    currency_pair, direction, entry_time, timeframe, martingale_times
    """
    result = {
        "currency_pair": None,
        "direction": None,
        "entry_time": None,
        "timeframe": None,
        "martingale_times": []
    }

    try:
        # Ignore messages that clearly are not signals
        if not re.search(r'(BUY|SELL|CALL|PUT|🔼|🟥|🟩|✅ ANNA SIGNALS ✅)', message_text, re.IGNORECASE):
            return None

        # Determine if this is an Anna signal
        is_anna_signal = "anna signals" in message_text.lower()

        # Currency pair - match more flexibly
        pair_match = re.search(
            r'(?:Pair:|CURRENCY PAIR:|📊|🇪🇺|🇺🇸|🇨🇭)?\s*([A-Z]{3}\/[A-Z]{3}(?:\s*OTC)?)',
            message_text
        )
        if not pair_match:
            # Try to match the format: 📊 🇪🇺 EUR/CHF 🇨🇭 OTC
            pair_match = re.search(r'([A-Z]{3}\/[A-Z]{3}(?:\s*OTC)?)', message_text)
        if pair_match:
            result['currency_pair'] = pair_match.group(1).strip()

        # Direction
        direction_match = re.search(r'(BUY|SELL|CALL|PUT|🔼|🟥|🟩)', message_text, re.IGNORECASE)
        if direction_match:
            direction = direction_match.group(1).upper()
            if direction in ['CALL', 'BUY', '🟩', '🔼']:
                result['direction'] = 'BUY'
            else:
                result['direction'] = 'SELL'

        # Entry time
        entry_time_match = re.search(r'(?:Entry Time:|Entry at|TIME \(UTC-03:00\):|⏺ Entry at)\s*(\d{2}:\d{2}(?::\d{2})?)', message_text)
        if entry_time_match:
            result['entry_time'] = entry_time_match.group(1)

        # Timeframe
        timeframe_match = re.search(r'Expiration:?\s*(M1|M5|1 Minute|5 Minute|5M|1M)', message_text)
        if timeframe_match:
            tf = timeframe_match.group(1)
            result['timeframe'] = 'M1' if tf in ['M1', '1 Minute', '1M'] else 'M5'

        # Default timeframe if missing
        if not result['timeframe']:
            if is_anna_signal:
                result['timeframe'] = 'M1'  # Anna signals are always 1 minute
            else:
                result['timeframe'] = 'M5'  # Other signals default to 5 minutes

        # Martingale times from message (if present)
        martingale_matches = re.findall(r'(?:Level \d+|level(?: at)?|PROTECTION|level At).*?\s*(\d{2}:\d{2})', message_text)
        if not martingale_matches:
            # Try to match "1️⃣ level At 10:35" etc
            martingale_matches = re.findall(r'level At (\d{2}:\d{2})', message_text)
        result['martingale_times'] = martingale_matches

        # Default Anna signals martingale logic (2 levels)
        if is_anna_signal and not result['martingale_times'] and result['entry_time']:
            fmt = "%H:%M:%S" if len(result['entry_time']) == 8 else "%H:%M"
            entry_dt = datetime.strptime(result['entry_time'], fmt)
            interval = 1  # Anna signals always M1

            # First martingale at end of first trade, second at end of first martingale
            first_martingale = entry_dt + timedelta(minutes=interval)
            second_martingale = first_martingale + timedelta(minutes=interval)
            result['martingale_times'] = [
                first_martingale.strftime(fmt),
                second_martingale.strftime(fmt)
            ]
            logging.info(f"[🔁] Default Anna martingale times applied: {result['martingale_times']}")

    except Exception as e:
        logging.error(f"[❌] Error parsing signal: {e}")

    # Return None if no valid signal found
    if not result['currency_pair'] or not result['entry_time'] or not result['direction']:
        return None

    return result

# =========================
# Telegram Listener
# =========================
def start_telegram_listener(signal_callback, command_callback):
    logging.info("[🔌] Starting Telegram listener...")

    @client.on(events.NewMessage(chats=TARGET_CHAT_ID))
    async def handler(event):
        try:
            text = event.message.message

            if text.startswith("/start") or text.startswith("/stop"):
                logging.info(f"[💻] Command detected: {text}")
                await command_callback(text)
                return

            signal = parse_signal(text)
            if signal:
                logging.info(f"[⚡] Parsed signal ready: {signal}")
                await signal_callback(signal)
            else:
                logging.info("[ℹ️] Message ignored (not a valid signal).")

        except Exception as e:
            logging.error(f"[❌] Error handling message: {e}")

    try:
        logging.info("[⚙️] Connecting to Telegram...")
        client.start(bot_token=bot_token)
        logging.info("[✅] Connected to Telegram. Listening for messages...")
        client.run_until_disconnected()
    except Exception as e:
        logging.error(f"[❌] Telegram listener failed: {e}")
