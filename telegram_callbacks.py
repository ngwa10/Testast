import logging
from datetime import datetime, timedelta
import pytz

from core import trade_manager  # 👈 Import the TradeManager instance from core.py

# --------------------------
# Signal Callback
# --------------------------
async def signal_callback(signal: dict, raw_message=None):
    """
    Called when a trading signal is parsed from Telegram.
    Automatically forwards it to the trading core with timezone handling.

    Signal example:
    {
        "currency_pair": "EUR/USD",
        "direction": "BUY",
        "entry_time": "14:30",
        "timeframe": "M1",
        "martingale_times": ["14:31", "14:32"],
        "source": "Cameroon"  # or UTC-4 / OTC-3
    }
    """
    msg_source = signal.get("source", "OTC-3")

    # --------------------------
    # Determine timezone
    # --------------------------
    if msg_source == "UTC-4":
        tz = pytz.timezone("America/New_York")
    elif msg_source == "Cameroon":
        tz = pytz.timezone("Africa/Douala")
    else:
        tz = pytz.timezone("UTC-3")  # Default OTC-3

    fmt = "%H:%M"
    entry_time_str = signal["entry_time"]
    now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)

    try:
        entry_dt_local = tz.localize(datetime.strptime(entry_time_str, fmt))
        entry_dt_utc = entry_dt_local.astimezone(pytz.UTC)
        delta_sec = (entry_dt_utc - now_utc).total_seconds()
    except Exception as e:
        logging.error(f"[❌] Invalid entry_time format '{entry_time_str}': {e}")
        return

    # --------------------------
    # Validate timing
    # --------------------------
    if delta_sec < 0:
        logging.info(f"[⏹️] Signal entry time {entry_time_str} already passed. Ignored.")
        return
    elif delta_sec > 10*60:
        logging.info(f"[⚠️] Signal entry time {entry_time_str} too far in the future (>10min). Ignored.")
        return

    logging.info(f"[📩] Signal received for {signal['currency_pair']} ({signal['direction']}) at {entry_time_str} {msg_source} — scheduling trade 🔥")

    # --------------------------
    # Forward to TradeManager
    # --------------------------
    try:
        trade_manager.handle_signal(signal)
        logging.info("[🤖] Signal forwarded to TradeManager for execution.")
    except Exception as e:
        logging.error(f"[❌] Failed to forward signal to TradeManager: {e}")


# --------------------------
# Command Callback
# --------------------------
async def command_callback(cmd: str):
    """
    Handles /start and /stop commands.
    """
    logging.info(f"[💻] Command received: {cmd}")

    try:
        trade_manager.handle_command(cmd)
    except Exception as e:
        logging.error(f"[❌] Failed to process command in TradeManager: {e}")

    if cmd.startswith("/start"):
        logging.info("[✅] Start command received — trading enabled.")
    elif cmd.startswith("/stop"):
        logging.info("[🛑] Stop command received — trading disabled.")
    
