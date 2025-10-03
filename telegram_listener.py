"""
Telegram Listener with integrated signal & command handling.
Directly communicates with core.py TradeManager.
"""

from telethon import TelegramClient, events
import re
from datetime import datetime, timedelta
import logging
import shared  # singleton holding TradeManager

# =========================
# HARD-CODED CREDENTIALS
# =========================
api_id = 29630724
api_hash = "8e12421a95fd722246e0c0b194fd3e0c"
bot_token = "8477806088:AAGEXpIAwN5tNQM0hsCGqP-otpLJjPJLmWA"
TARGET_CHAT_ID = -1003033183667  # Numeric channel ID

# =========================
# Logging Setup
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("telegram_listener")


# =========================
# Helper log functions
# =========================
def log_info(msg):
    logger.info(msg)
    for handler in logger.handlers:
        handler.flush()


def log_error(msg):
    logger.error(msg)
    for handler in logger.handlers:
        handler.flush()


# =========================
# Signal Parser
# =========================
def parse_signal(message_text):
    """
    Extracts currency pair, direction, entry time, timeframe, martingale times.
    Returns dict ready for TradeManager or None if invalid.
    """
    result = {
        "currency_pair": None,
        "direction": None,
        "entry_time": None,
        "timeframe": None,
        "martingale_times": [],
        "source": "OTC-3"
    }

    try:
        if not re.search(r'(BUY|SELL|CALL|PUT|🔼|🟥|🟩|🔽|✅ ANNA SIGNALS ✅|_OTC)', message_text, re.IGNORECASE):
            return None

        is_anna_signal = "anna signals" in message_text.lower()
        clean_text = re.sub(r'[^\x00-\x7F]+', ' ', message_text)

        # Currency Pair
        pair_match = re.search(r'([A-Z]{3}/[A-Z]{3})(?:[\s_\-]?OTC)?', clean_text, re.IGNORECASE)
        if pair_match:
            result['currency_pair'] = pair_match.group(0).strip()

        # Direction
        direction_match = re.search(r'(BUY|SELL|CALL|PUT|🔼|🟥|🟩|🔽|⏺ BUY|⏺ SELL)', message_text, re.IGNORECASE)
        if direction_match:
            direction = direction_match.group(1).upper()
            if direction in ['CALL','BUY','🟩','🔼','⏺ BUY']:
                result['direction'] = 'BUY'
            elif direction in ['PUT','SELL','🔽','🟥','⏺ SELL']:
                result['direction'] = 'SELL'

        # Entry Time
        entry_time_match = re.search(r'(?:Entry Time:|Entry at|TIME \(UTC.*\):|⏺ Entry at)\s*(\d{2}:\d{2})', message_text)
        if entry_time_match:
            entry_time_str = entry_time_match.group(1)
            source = "OTC-3"
            if "💥 GET THIS SIGNAL HERE!" in message_text:
                source = "UTC-4"
            elif "💥 TRADE WITH DESMOND!" in message_text:
                source = "Cameroon"
            result['source'] = source

            # Convert to datetime
            hour, minute = map(int, entry_time_str.split(":"))
            entry_dt = datetime.utcnow().replace(hour=hour, minute=minute, second=0, microsecond=0)
            result['entry_time'] = entry_dt

        # Timeframe
        timeframe_match = re.search(r'Expiration:?\s*(M1|M5|1 Minute|5 Minute|5M|1M|5-minute)', message_text, re.IGNORECASE)
        if timeframe_match:
            tf = timeframe_match.group(1).lower()
            result['timeframe'] = 'M1' if '1' in tf else 'M5'
        if not result['timeframe']:
            result['timeframe'] = 'M1' if is_anna_signal else 'M5'

        # Martingale times
        martingale_matches = re.findall(
            r'(?:Level \d+|level(?: at)?|PROTECTION|level At|level|ª PROTECTION)\D*[:\-\—>]*\s*(\d{2}:\d{2})',
            message_text, re.IGNORECASE
        )
        for t in martingale_matches:
            hour, minute = map(int, t.split(":"))
            mg_dt = datetime.utcnow().replace(hour=hour, minute=minute, second=0, microsecond=0)
            result['martingale_times'].append(mg_dt)

        # Default Anna martingale if none
        if is_anna_signal and not result['martingale_times'] and result['entry_time']:
            interval = timedelta(minutes=1)
            first_mg = result['entry_time'] + interval
            second_mg = first_mg + interval
            result['martingale_times'] = [first_mg, second_mg]
            log_info(f"[🔁] Default Anna martingale times applied: {[t.strftime('%H:%M') for t in result['martingale_times']]}")

        if not result['currency_pair'] or not result['entry_time'] or not result['direction']:
            return None

        return result

    except Exception as e:
        log_error(f"[❌] Error parsing signal: {e}")
        return None


# =========================
# Telegram Listener
# =========================
def start_telegram_listener():
    log_info("[🔌] Starting Telegram listener...")
    client = TelegramClient('bot_session', api_id, api_hash)

    @client.on(events.NewMessage(chats=TARGET_CHAT_ID))
    async def handler(event):
        try:
            text = event.message.message

            # Commands
            if text.startswith("/start") or text.startswith("/stop"):
                log_info(f"[💻] Command detected: {text}")
                if shared.trade_manager:
                    shared.trade_manager.handle_command(text)
                return

            # Signals
            signal = parse_signal(text)
            if signal:
                received_time = datetime.utcnow().strftime("%H:%M:%S")
                log_info(f"[⚡] Parsed signal at {received_time}: {signal}")
                if shared.trade_manager:
                    shared.trade_manager.handle_signal(signal)
            else:
                log_info("[ℹ️] Message ignored (not a valid signal).")

        except Exception as e:
            log_error(f"[❌] Error handling message: {e}")

    try:
        log_info("[⚙️] Connecting to Telegram...")
        client.start(bot_token=bot_token)
        log_info("[✅] Connected to Telegram. Listening for messages...")
        client.run_until_disconnected()
    except Exception as e:
        log_error(f"[❌] Telegram listener failed: {e}")


# =========================
# Entry Point
# =========================
if __name__ == "__main__":
    log_info("[🚀] Telegram listener script started.")
    start_telegram_listener()
    
