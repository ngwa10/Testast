l# telegram_listener.py
import logging
import re
from datetime import datetime, timedelta
from telethon import TelegramClient, events

from core import trade_manager  # Import TradeManager instance
from core_utils import timezone_convert  # Timezone conversion helper

# =========================
# HARD-CODED TELEGRAM CREDENTIALS
# =========================
api_id = 29630724
api_hash = "8e12421a95fd722246e0c0b194fd3e0c"
bot_token = "8477806088:AAGEXpIAwN5tNQM0hsCGqP-otpLJjPJLmWA"
TARGET_CHAT_ID = -1003033183667  # Channel ID

# =========================
# Logging Setup
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

def log_info(msg):
    logger.info(msg)
    for h in logger.handlers: h.flush()

def log_error(msg):
    logger.error(msg)
    for h in logger.handlers: h.flush()

# =========================
# Signal Callback
# =========================
async def signal_callback(signal: dict, raw_message=None):
    """
    Forward parsed trading signal to TradeManager with timezone conversion.
    Signal format example:
    {
        "currency_pair": "EUR/USD",
        "direction": "BUY",
        "entry_time": "14:30" or datetime,
        "timeframe": "M1",
        "martingale_times": ["14:31", "14:32"],
        "source": "Cameroon"  # or "UTC-4" / "OTC-3"
    }
    """
    source_tz = signal.get("source", "OTC-3")
    entry_time_val = signal.get("entry_time")
    entry_dt = timezone_convert(entry_time_val, source_tz)
    if not entry_dt:
        log_info(f"[⚠️] Signal entry time {entry_time_val} already passed. Ignoring.")
        return
    signal['entry_time'] = entry_dt

    # Convert martingale times
    mg_fixed = []
    for t in signal.get("martingale_times", []):
        t_conv = timezone_convert(t, source_tz)
        if t_conv:
            mg_fixed.append(t_conv)
    signal['martingale_times'] = mg_fixed

    try:
        trade_manager.handle_signal(signal)
        log_info(f"[🤖] Signal forwarded for {signal['currency_pair']} ({signal['direction']}) at {entry_dt.strftime('%H:%M')}")
    except Exception as e:
        log_error(f"[❌] Failed to forward signal to TradeManager: {e}")

# =========================
# Command Callback
# =========================
async def command_callback(cmd: str):
    log_info(f"[💻] Command received: {cmd}")
    try:
        trade_manager.handle_command(cmd)
    except Exception as e:
        log_error(f"[❌] Failed to process command: {e}")

# =========================
# Signal Parser
# =========================
def parse_signal(message_text):
    """
    Parses Telegram messages into signal dict.
    Supports Anna, OTC, and generic formats.
    """
    result = {
        "currency_pair": None,
        "direction": None,
        "entry_time": None,
        "timeframe": "M1",
        "martingale_times": [],
        "source": "OTC-3"
    }

    # Detect currency pair
    pair_match = re.search(r'([A-Z]{3}/[A-Z]{3})', message_text)
    if pair_match:
        result['currency_pair'] = pair_match.group(0)

    # Detect direction
    if re.search(r'(BUY|CALL|🟩|🔼)', message_text, re.IGNORECASE):
        result['direction'] = 'BUY'
    elif re.search(r'(SELL|PUT|🟥|🔽)', message_text, re.IGNORECASE):
        result['direction'] = 'SELL'

    # Detect entry time
    entry_match = re.search(r'(\d{2}:\d{2})', message_text)
    if entry_match:
        result['entry_time'] = entry_match.group(1)

    # Default martingale (1 min intervals)
    if result['entry_time']:
        fmt = "%H:%M"
        dt = datetime.strptime(result['entry_time'], fmt)
        result['martingale_times'] = [(dt + timedelta(minutes=1)).strftime("%H:%M"),
                                      (dt + timedelta(minutes=2)).strftime("%H:%M")]

    if not all([result['currency_pair'], result['direction'], result['entry_time']]):
        return None
    return result

# =========================
# Telegram Listener
# =========================
client = TelegramClient('bot_session', api_id, api_hash)

def start_telegram_listener(signal_cb, cmd_cb):
    log_info("[🔌] Starting Telegram listener...")

    @client.on(events.NewMessage(chats=TARGET_CHAT_ID))
    async def handler(event):
        text = event.message.message
        if text.startswith("/start") or text.startswith("/stop"):
            await cmd_cb(text)
            return
        signal = parse_signal(text)
        if signal:
            await signal_cb(signal)
        else:
            log_info("[ℹ️] Message ignored (not a valid signal).")

    try:
        client.start(bot_token=bot_token)
        log_info("[✅] Connected to Telegram. Listening for messages...")
        client.run_until_disconnected()
    except Exception as e:
        log_error(f"[❌] Telegram listener failed: {e}")
        
