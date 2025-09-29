"""
Telegram integration: Listener and signal parser with detailed logging.
Logs connection, message receipt, parsing steps, and errors.
Credentials are still hardcoded for private project (for demo purposes).
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
channel_env = "-1003033183667"  # Numeric ID or @channelname

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
channel_entity = None

async def resolve_channel():
    """Resolve the Telegram channel/entity before starting listener."""
    global channel_entity
    try:
        if channel_env.startswith("-100") or channel_env.lstrip("-").isdigit():
            channel_entity = await client.get_entity(int(channel_env))
        else:
            channel_entity = await client.get_entity(channel_env)
        logging.info(f"[✅] Resolved channel: {getattr(channel_entity, 'title', channel_entity.id)}")
    except Exception as e:
        logging.error(f"[❌] Failed to resolve Telegram channel '{channel_env}': {e}")
        raise

# =========================
# Signal Parser
# =========================
def parse_signal(message_text):
    """
    Parses trading signals from a Telegram message text.
    Returns a dictionary with:
    currency_pair, direction, entry_time, timeframe, martingale_times
    """
    logging.info("[🔍] Parsing message for trading signal...")
    result = {
        "currency_pair": None,
        "direction": None,
        "entry_time": None,
        "timeframe": None,
        "martingale_times": []
    }

    try:
        # Currency pair
        pair_match = re.search(r'(?:Pair:|CURRENCY PAIR:|🇺🇸|📊)\s*([\w\/\-]+)', message_text)
        if pair_match:
            result['currency_pair'] = pair_match.group(1).strip()
            logging.info(f"[💱] Currency pair detected: {result['currency_pair']}")

        # Direction
        direction_match = re.search(r'(BUY|SELL|CALL|PUT|🔼|🟥|🟩)', message_text, re.IGNORECASE)
        if direction_match:
            direction = direction_match.group(1).upper()
            if direction in ['CALL', 'BUY', '🟩', '🔼']:
                result['direction'] = 'BUY'
            else:
                result['direction'] = 'SELL'
            logging.info(f"[⬆️⬇️] Direction detected: {result['direction']}")

        # Entry time
        entry_time_match = re.search(r'(?:Entry Time:|Entry at|TIME \(UTC-03:00\):)\s*(\d{2}:\d{2}(?::\d{2})?)', message_text)
        if entry_time_match:
            result['entry_time'] = entry_time_match.group(1)
            logging.info(f"[⏰] Entry time detected: {result['entry_time']}")

        # Timeframe
        timeframe_match = re.search(r'Expiration:?\s*(M1|M5|1 Minute|5 Minute)', message_text)
        if timeframe_match:
            tf = timeframe_match.group(1)
            result['timeframe'] = 'M1' if tf in ['M1', '1 Minute'] else 'M5'
            logging.info(f"[⏱️] Timeframe detected: {result['timeframe']}")

        # Martingale times
        martingale_matches = re.findall(r'(?:Level \d+|level(?: at)?|PROTECTION).*?\s*(\d{2}:\d{2})', message_text)
        result['martingale_times'] = martingale_matches
        if martingale_matches:
            logging.info(f"[🔁] Martingale times detected: {result['martingale_times']}")

        # Default Anna signals martingale logic (2 levels)
        if "anna signals" in message_text.lower() and not result['martingale_times'] and result['entry_time']:
            fmt = "%H:%M:%S" if len(result['entry_time']) == 8 else "%H:%M"
            entry_dt = datetime.strptime(result['entry_time'], fmt)
            interval = 1 if result['timeframe'] == "M1" else 5
            result['martingale_times'] = [
                (entry_dt + timedelta(minutes=interval * i)).strftime(fmt)
                for i in range(1, 3)
            ]
            logging.info(f"[🔁] Default Anna martingale times applied: {result['martingale_times']}")
    except Exception as e:
        logging.error(f"[❌] Error parsing signal: {e}")

    return result

# =========================
# Telegram Listener
# =========================
def start_telegram_listener(signal_callback, command_callback):
    """Start the Telegram listener for signals and commands."""
    logging.info("[🔌] Starting Telegram listener...")

    @client.on(events.NewMessage())
    async def handler(event):
        try:
            target_id = getattr(channel_entity, 'id', None)
            if event.chat_id != target_id:
                return

            text = event.message.message
            logging.info(f"[📩] New message received: {text}")

            if text.startswith("/start") or text.startswith("/stop"):
                logging.info(f"[💻] Command detected: {text}")
                await command_callback(text)
            else:
                signal = parse_signal(text)
                if signal['currency_pair'] and signal['entry_time']:
                    logging.info(f"[⚡] Parsed signal ready: {signal}")
                    await signal_callback(signal)
                else:
                    logging.warning("[⚠️] Message did not contain a valid signal.")
        except Exception as e:
            logging.error(f"[❌] Error handling message: {e}")

    try:
        logging.info("[⚙️] Connecting to Telegram...")
        client.start(bot_token=bot_token)
        logging.info("[✅] Connected to Telegram. Resolving channel...")
        client.loop.run_until_complete(resolve_channel())
        logging.info("[✅] Listening for messages...")
        client.run_until_disconnected()
    except Exception as e:
        logging.error(f"[❌] Telegram listener failed: {e}")
