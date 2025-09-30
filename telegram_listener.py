"""
Telegram integration: Listener and signal parser with detailed logging.
Supports Anna, Precisiontrike, and OTC signal formats.
Handles multiple timezones and prepares signals for core.py trading.
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
# Signal Parser (Fully Fixed)
# =========================
def parse_signal(message_text):
    result = {
        "currency_pair": None,
        "direction": None,
        "entry_time": None,
        "timeframe": None,
        "martingale_times": []
    }

    try:
        # --------------------------
        # Ignore messages that are not signals
        # --------------------------
        if not re.search(r'(BUY|SELL|CALL|PUT|🔼|🟥|🟩|🔽|✅ ANNA SIGNALS ✅|_OTC)', message_text, re.IGNORECASE):
            return None

        is_anna_signal = "anna signals" in message_text.lower()

        # --------------------------
        # Currency pair - ignore emojis, capture OTC (any format)
        # --------------------------
        clean_text = re.sub(r'[^\x00-\x7F]+', ' ', message_text)  # remove emojis
        pair_match = re.search(
            r'([A-Z]{3}/[A-Z]{3})(?:[\s_\-]?OTC)?',
            clean_text,
            re.IGNORECASE
        )
        if not pair_match:
            pair_match = re.search(r'(?:Pair:|CURRENCY PAIR:|📊)\s*([\w\/\-]+)', clean_text)
        if pair_match:
            result['currency_pair'] = pair_match.group(0).strip()  # include OTC if present

        # --------------------------
        # Direction
        # --------------------------
        direction_match = re.search(r'(BUY|SELL|CALL|PUT|🔼|🟥|🟩|🔽|⏺ BUY|⏺ SELL)', message_text, re.IGNORECASE)
        if direction_match:
            direction = direction_match.group(1).upper()
            # Correct mapping for Anna and dynamic signals
            if direction in ['CALL', 'BUY', '🟩', '🔼', '⏺ BUY']:
                result['direction'] = 'BUY'
            elif direction in ['PUT', 'SELL', '🔽', '🟥', '⏺ SELL']:
                result['direction'] = 'SELL'

        # --------------------------
        # Entry time
        # --------------------------
        entry_time_match = re.search(r'(?:Entry Time:|Entry at|TIME \(UTC.*\):|⏺ Entry at)\s*(\d{2}:\d{2})', message_text)
        if entry_time_match:
            result['entry_time'] = entry_time_match.group(1)

        # --------------------------
        # Timeframe / Expiration
        # --------------------------
        timeframe_match = re.search(r'Expiration:?\s*(M1|M5|1 Minute|5 Minute|5M|1M|5-minute)', message_text, re.IGNORECASE)
        if timeframe_match:
            tf = timeframe_match.group(1).lower()
            result['timeframe'] = 'M1' if '1' in tf else 'M5'
        if not result['timeframe']:
            result['timeframe'] = 'M1' if is_anna_signal else 'M5'

        # --------------------------
        # Martingale times / Protection
        # --------------------------
        martingale_matches = re.findall(
            r'(?:Level \d+|level(?: at)?|PROTECTION|level At|level|ª PROTECTION)\D*[:\-\—>]*\s*(\d{2}:\d{2})',
            message_text, re.IGNORECASE
        )
        result['martingale_times'] = martingale_matches

        # Default Anna martingale if none found
        if is_anna_signal and not result['martingale_times'] and result['entry_time']:
            fmt = "%H:%M:%S" if len(result['entry_time']) == 8 else "%H:%M"
            entry_dt = datetime.strptime(result['entry_time'], fmt)
            interval = 1  # Anna signals always M1
            first_martingale = entry_dt + timedelta(minutes=interval)
            second_martingale = first_martingale + timedelta(minutes=interval)
            result['martingale_times'] = [
                first_martingale.strftime(fmt),
                second_martingale.strftime(fmt)
            ]
            logging.info(f"[🔁] Default Anna martingale times applied: {result['martingale_times']}", flush=True)

        # --------------------------
        # Return None if no valid signal
        # --------------------------
        if not result['currency_pair'] or not result['entry_time'] or not result['direction']:
            return None

        return result

    except Exception as e:
        logging.error(f"[❌] Error parsing signal: {e}", flush=True)
        return None

# =========================
# Telegram Listener
# =========================
def start_telegram_listener(signal_callback, command_callback):
    logging.info("[🔌] Starting Telegram listener...", flush=True)

    @client.on(events.NewMessage(chats=TARGET_CHAT_ID))
    async def handler(event):
        try:
            text = event.message.message

            # --------------------------
            # Commands
            # --------------------------
            if text.startswith("/start") or text.startswith("/stop"):
                logging.info(f"[💻] Command detected: {text}", flush=True)
                await command_callback(text)
                return

            # --------------------------
            # Parse signals
            # --------------------------
            signal = parse_signal(text)
            if signal:
                received_time = datetime.utcnow().strftime("%H:%M:%S")
                logging.info(f"[⚡] Parsed signal at {received_time}: {signal}", flush=True)
                await signal_callback(signal, raw_message=text)
            else:
                logging.info("[ℹ️] Message ignored (not a valid signal).", flush=True)

        except Exception as e:
            logging.error(f"[❌] Error handling message: {e}", flush=True)

    try:
        logging.info("[⚙️] Connecting to Telegram...", flush=True)
        client.start(bot_token=bot_token)
        logging.info("[✅] Connected to Telegram. Listening for messages...", flush=True)
        client.run_until_disconnected()
    except Exception as e:
        logging.error(f"[❌] Telegram listener failed: {e}", flush=True)
            
