import logging
from datetime import datetime
import pytz
import shared  # ✅ Always get the singleton from shared at runtime

# --------------------------
# Helper to get the singleton safely
# --------------------------
def get_trade_manager():
    if shared.trade_manager is None:
        logging.error("[❌] TradeManager not initialized yet in shared!")
        return None
    return shared.trade_manager

# --------------------------
# Signal Callback
# --------------------------
async def signal_callback(signal: dict, raw_message=None):
    """
    Called when a trading signal is parsed from Telegram.
    Automatically forwards it to the trading core with timezone handling.
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

    now_utc = datetime.utcnow().replace(tzinfo=pytz.UTC)

    # --------------------------
    # Handle entry_time
    # --------------------------
    entry_time_val = signal.get("entry_time")
    try:
        if isinstance(entry_time_val, datetime):
            entry_dt_local = entry_time_val.astimezone(tz)
        elif isinstance(entry_time_val, str):
            fmt = "%H:%M"
            entry_dt_local = tz.localize(datetime.combine(datetime.now(tz).date(),
                                                          datetime.strptime(entry_time_val, fmt).time()))
        else:
            logging.error(f"[❌] entry_time has invalid type: {type(entry_time_val)}")
            return

        entry_dt_utc = entry_dt_local.astimezone(pytz.UTC)
        delta_sec = (entry_dt_utc - now_utc).total_seconds()
    except Exception as e:
        logging.error(f"[❌] Failed to parse entry_time '{entry_time_val}': {e}")
        return

    # --------------------------
    # Validate timing
    # --------------------------
    if delta_sec < 0:
        logging.info(f"[⏹️] Signal entry time {entry_dt_local.strftime('%H:%M')} already passed. Ignored.")
        return
    elif delta_sec > 10*60:
        logging.info(f"[⚠️] Signal entry time {entry_dt_local.strftime('%H:%M')} too far in the future (>10min). Ignored.")
        return

    logging.info(f"[📩] Signal received for {signal['currency_pair']} ({signal['direction']}) at "
                 f"{entry_dt_local.strftime('%H:%M')} {msg_source} — scheduling trade 🔥")

    # --------------------------
    # Ensure martingale times are datetime objects
    # --------------------------
    mg_times_fixed = []
    for t in signal.get("martingale_times", []):
        try:
            if isinstance(t, datetime):
                mg_times_fixed.append(t.astimezone(tz))
            elif isinstance(t, str):
                mg_times_fixed.append(tz.localize(datetime.combine(datetime.now(tz).date(),
                                                                    datetime.strptime(t, "%H:%M").time())))
        except Exception as e:
            logging.warning(f"[⚠️] Invalid martingale time '{t}': {e}")
    signal['martingale_times'] = mg_times_fixed
    signal['entry_time'] = entry_dt_local

    # --------------------------
    # Forward to TradeManager
    # --------------------------
    tm = get_trade_manager()
    if tm:
        try:
            tm.handle_signal(signal)
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

    tm = get_trade_manager()
    if tm:
        try:
            tm.handle_command(cmd)
        except Exception as e:
            logging.error(f"[❌] Failed to process command in TradeManager: {e}")

    if cmd.startswith("/start"):
        logging.info("[✅] Start command received — trading enabled.")
    elif cmd.startswith("/stop"):
        logging.info("[🛑] Stop command received — trading disabled.")
        
