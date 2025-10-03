# telegram_listener_callback.py
import logging
import time
from datetime import datetime
import shared  # core.py TradeManager singleton

# --------------------------
# Logging
# --------------------------
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger("telegram_listener_callback")

# --------------------------
# Callback for signals
# --------------------------
def telegram_signal_callback(signal: dict, max_wait_sec: int = 10):
    """
    Called by your Telegram listener whenever a trading signal arrives.
    Waits until TradeManager is ready (up to max_wait_sec) before processing.
    """
    waited = 0
    while shared.trade_manager is None and waited < max_wait_sec:
        logger.info("[⏳] Waiting for TradeManager to initialize...")
        time.sleep(0.5)
        waited += 0.5

    if shared.trade_manager is None:
        logger.warning("[⚠️] TradeManager not ready after waiting; signal ignored.")
        return

    try:
        shared.trade_manager.handle_signal(signal)
        logger.info(f"[🤖] Signal forwarded to TradeManager: {signal.get('currency_pair')} at {signal.get('entry_time')}")
    except Exception as e:
        logger.error(f"[❌] Failed to process signal: {e}")


# --------------------------
# Callback for commands
# --------------------------
def telegram_command_callback(cmd: str, max_wait_sec: int = 10):
    """
    Handles /start and /stop commands, waits for TradeManager if needed.
    """
    waited = 0
    while shared.trade_manager is None and waited < max_wait_sec:
        logger.info("[⏳] Waiting for TradeManager to initialize for command...")
        time.sleep(0.5)
        waited += 0.5

    if shared.trade_manager is None:
        logger.warning("[⚠️] TradeManager not ready after waiting; command ignored.")
        return

    try:
        shared.trade_manager.handle_command(cmd)
        logger.info(f"[🤖] Command processed: {cmd}")
    except Exception as e:
        logger.error(f"[❌] Failed to process command: {e}")


# --------------------------
# Example signal parser (replace with your real parser)
# --------------------------
def parse_signal_from_message(message) -> dict:
    return {
        "currency_pair": "AUD/CHF",
        "direction": "BUY",
        "entry_time": datetime.now(),
        "timeframe": "M5",
        "martingale_times": [],
        "source": "Cameroon"
    }


# --------------------------
# Example listener hook
# --------------------------
def on_telegram_message(message):
    if message.text.startswith("/start") or message.text.startswith("/stop"):
        telegram_command_callback(message.text)
    else:
        signal = parse_signal_from_message(message)
        telegram_signal_callback(signal)
        
