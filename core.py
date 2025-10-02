# core.py
import threading
import logging
import time
import random
import pytz
from datetime import datetime, timedelta
import re
import pyautogui
from telethon import TelegramClient, events

# =========================
# Logging Setup
# =========================
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# =========================
# HARD-CODED TELEGRAM CREDENTIALS
# =========================
api_id = 29630724
api_hash = "8e12421a95fd722246e0c0b194fd3e0c"
bot_token = "8477806088:AAGEXpIAwN5tNQM0hsCGqP-otpLJjPJLmWA"
TARGET_CHAT_ID = -1003033183667

client = TelegramClient('bot_session', api_id, api_hash)

# =========================
# Random log messages
# =========================
try:
    with open("logs.json", "r", encoding="utf-8") as f:
        LOG_MESSAGES = json.load(f)
except Exception:
    LOG_MESSAGES = [
        "Precision is warming up. Desmond is watching.",
        "Desmond's bot is on duty — targets locked.",
    ]

def random_log():
    return random.choice(LOG_MESSAGES) if LOG_MESSAGES else ""

# =========================
# Timezone conversion helper
# =========================
def timezone_convert(entry_time_val, source_tz_str):
    try:
        tz_lower = source_tz_str.lower().strip()
        if tz_lower.startswith("utc"):
            sign = 1 if "+" in tz_lower else -1
            hours = int(tz_lower.split("utc")[1].replace("+", "").replace("-", ""))
            src_tz = pytz.FixedOffset(sign * hours * 60)
        elif tz_lower == "cameroon":
            src_tz = pytz.timezone("Africa/Douala")
        elif tz_lower.startswith("otc-"):
            offset_hours = int(tz_lower.split("-")[1])
            src_tz = pytz.FixedOffset(-offset_hours * 60)
        else:
            try:
                src_tz = pytz.timezone(source_tz_str)
            except:
                src_tz = pytz.UTC
        now_src = datetime.now(pytz.utc).astimezone(src_tz)

        if isinstance(entry_time_val, datetime):
            entry_dt = entry_time_val.astimezone(src_tz) if entry_time_val.tzinfo else src_tz.localize(entry_time_val)
        elif isinstance(entry_time_val, str):
            fmt = "%H:%M"
            entry_time = datetime.strptime(entry_time_val, fmt).time()
            entry_dt = datetime.combine(now_src.date(), entry_time)
            entry_dt = src_tz.localize(entry_dt)
        else:
            return None

        if entry_dt < now_src:
            return None
        return entry_dt
    except Exception as e:
        logger.warning(f"[⚠️] Failed timezone conversion for '{entry_time_val}' ({source_tz_str}): {e}")
        return None

# =========================
# TradeManager Class
# =========================
class TradeManager:
    def __init__(self, base_amount=1.0, max_martingale=3, hotkey_mode=True):
        self.base_amount = base_amount
        self.max_martingale = max_martingale
        self.trading_active = True
        self.pending_trades = []
        self.pending_lock = threading.Lock()
        self.increase_counts = {}
        self.hotkey_mode = hotkey_mode

        pyautogui.FAILSAFE = False

        # Placeholder for Selenium integration
        self.selenium = None
        logger.info(f"TradeManager initialized | base_amount: {base_amount}, max_martingale: {max_martingale}, hotkey_mode={hotkey_mode}")

    # -----------------
    # Command Handling
    # -----------------
    def handle_command(self, cmd: str):
        cmd = cmd.strip().lower()
        if cmd.startswith("/start"):
            self.trading_active = True
            logger.info("[🚀] Trading started.")
        elif cmd.startswith("/stop"):
            self.trading_active = False
            logger.info("[⏹️] Trading stopped.")
        elif cmd.startswith("/status"):
            logger.info("[ℹ️] Trading status: ACTIVE" if self.trading_active else "[ℹ️] Trading status: PAUSED")
        else:
            logger.info(f"[ℹ️] Unknown command: {cmd}")

    # -----------------
    # Schedule Trade
    # -----------------
    def schedule_trade(self, entry_dt, signal, martingale_level):
        delay = (entry_dt - datetime.now(entry_dt.tzinfo)).total_seconds()
        if delay <= 0:
            logger.info(f"[⏹️] Signal entry time {entry_dt.strftime('%H:%M')} passed. Skipping trade.")
            return
        threading.Timer(delay, self.execute_trade, args=(entry_dt, signal, martingale_level)).start()

    # -----------------
    # Handle Signal
    # -----------------
    def handle_signal(self, signal: dict):
        if not self.trading_active:
            logger.info("[⏸️] Trading paused. Ignoring signal.")
            return

        logger.info(f"[📡] Received signal: {signal} | {random_log()}")
        source_tz = signal.get("source", "UTC-3")
        entry_dt = timezone_convert(signal.get('entry_time'), source_tz)
        if not entry_dt:
            logger.warning(f"[⚠️] Invalid or passed entry_time: {signal.get('entry_time')}. Skipping signal.")
            return
        signal['entry_time'] = entry_dt

        # Convert martingale times
        mg_times_fixed = []
        for t in signal.get("martingale_times", []):
            t_conv = timezone_convert(t, source_tz)
            if t_conv:
                mg_times_fixed.append(t_conv)
        signal['martingale_times'] = mg_times_fixed

        # Schedule base trade
        self.schedule_trade(entry_dt, signal, 0)

        # Schedule martingale trades
        for i, mg in enumerate(signal['martingale_times']):
            level = i + 1
            if level > self.max_martingale:
                logger.warning(f"[⚠️] Martingale level {level} exceeds max {self.max_martingale}. Skipping.")
                break
            self.schedule_trade(mg, signal, level)

    # -----------------
    # Execute Trade (dummy hotkeys for demo)
    # -----------------
    def execute_trade(self, entry_dt, signal, martingale_level):
        currency = signal['currency_pair']
        direction = signal.get('direction', 'BUY')
        trade_id = f"{currency}_{entry_dt.strftime('%H%M')}_{martingale_level}_{int(time.time()*1000)}"
        logger.info(f"[🎯] Executing trade {trade_id} — {direction} level {martingale_level} | {random_log()}")

# =========================
# Instantiate TradeManager
# =========================
trade_manager = TradeManager()

# =========================
# Telegram Listener
# =========================
async def signal_callback(signal: dict, raw_message=None):
    try:
        trade_manager.handle_signal(signal)
        logger.info("[🤖] Signal forwarded to TradeManager for execution.")
    except Exception as e:
        logger.error(f"[❌] Failed to forward signal: {e}")

async def command_callback(cmd: str):
    trade_manager.handle_command(cmd)
    logger.info(f"[💻] Command processed: {cmd}")

def parse_signal(message_text):
    result = {
        "currency_pair": None,
        "direction": None,
        "entry_time": None,
        "timeframe": "M1",
        "martingale_times": [],
        "source": "OTC-3"
    }

    # Detect currency and direction
    pair_match = re.search(r'([A-Z]{3}/[A-Z]{3})', message_text)
    if pair_match:
        result['currency_pair'] = pair_match.group(0)
    if re.search(r'(BUY|CALL|🟩|🔼)', message_text, re.IGNORECASE):
        result['direction'] = 'BUY'
    elif re.search(r'(SELL|PUT|🟥|🔽)', message_text, re.IGNORECASE):
        result['direction'] = 'SELL'

    # Entry time
    entry_match = re.search(r'(\d{2}:\d{2})', message_text)
    if entry_match:
        result['entry_time'] = entry_match.group(1)

    # Default martingale
    if result['entry_time']:
        fmt = "%H:%M"
        dt = datetime.strptime(result['entry_time'], fmt)
        result['martingale_times'] = [ (dt + timedelta(minutes=1)).strftime("%H:%M"), (dt + timedelta(minutes=2)).strftime("%H:%M")]

    if not result['currency_pair'] or not result['direction'] or not result['entry_time']:
        return None
    return result

def start_telegram_listener(signal_cb, cmd_cb):
    logger.info("[🔌] Starting Telegram listener...")

    @client.on(events.NewMessage(chats=TARGET_CHAT_ID))
    async def handler(event):
        text = event.message.message
        if text.startswith("/start") or text.startswith("/stop"):
            await cmd_cb(text)
            return
        signal = parse_signal(text)
        if signal:
            await signal_cb(signal)

    client.start(bot_token=bot_token)
    client.run_until_disconnected()

# =========================
# Run Telegram listener in a separate thread
# =========================
listener_thread = threading.Thread(target=lambda: start_telegram_listener(signal_callback, command_callback), daemon=True)
listener_thread.start()
logger.info("[ℹ️] Telegram listener thread started.")

# =========================
# Keep bot alive
# =========================
logger.info("[ℹ️] Core bot running and ready for signals.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    logger.info("[ℹ️] Bot shutting down.")
            
