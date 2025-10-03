import logging
from datetime import datetime
import asyncio
import pytz
import shared  # dynamic singleton reference

# --------------------------
# Config
# --------------------------
TRADE_MANAGER_WAIT_SECONDS = 10
RETRY_INTERVAL_SECONDS = 0.1

# --------------------------
# Helper: async wait for TradeManager
# --------------------------
async def wait_for_trade_manager(timeout=TRADE_MANAGER_WAIT_SECONDS):
    elapsed = 0.0
    while shared.trade_manager is None and elapsed < timeout:
        await asyncio.sleep(RETRY_INTERVAL_SECONDS)
        elapsed += RETRY_INTERVAL_SECONDS
    return shared.trade_manager is not None

# --------------------------
# Signal Callback
# --------------------------
async def signal_callback(signal: dict, raw_message=None):
    """Forward parsed Telegram signal to TradeManager safely."""

    ready = await wait_for_trade_manager()
    if not ready:
        logging.error("[❌] TradeManager not ready after waiting; signal ignored.")
        return

    msg_source = signal.get("source", "OTC-3")

    # --------------------------
    # Determine timezone
    # --------------------------
    if msg_source == "UTC-4":
        tz = pytz.timezone("America/New_York")
    elif msg_source == "Cameroon":
        tz = pytz.timezone("Africa/Douala")
    else:
        tz = pytz.timezone("UTC-3")  # default OTC-3

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
            entry_dt_local = tz.localize(
                datetime.combine(datetime.now(tz).date(), datetime.strptime(entry_time_val, fmt).time())
            )
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

    logging.info(f"[📩] Signal received for {signal['currency_pair']} ({signal['direction']}) at {entry_dt_local.strftime('%H:%M')} {msg_source} — scheduling trade 🔥")

    # --------------------------
    # Convert martingale times
    # --------------------------
    mg_times_fixed = []
    for t in signal.get("martingale_times", []):
        try:
            if isinstance(t, datetime):
                mg_times_fixed.append(t.astimezone(tz))
            elif isinstance(t, str):
                mg_times_fixed.append(
                    tz.localize(datetime.combine(datetime.now(tz).date(), datetime.strptime(t, "%H:%M").time()))
                )
        except Exception as e:
            logging.warning(f"[⚠️] Invalid martingale time '{t}': {e}")
    signal['martingale_times'] = mg_times_fixed
    signal['entry_time'] = entry_dt_local

    # --------------------------
    # Forward to TradeManager
    # --------------------------
    try:
        shared.trade_manager.handle_signal(signal)
        logging.info("[🤖] Signal forwarded to TradeManager for execution.")
    except Exception as e:
        logging.error(f"[❌] Failed to forward signal to TradeManager: {e}")


# --------------------------
# Command Callback
# --------------------------
async def command_callback(cmd: str):
    """Handle /start and /stop commands asynchronously."""

    ready = await wait_for_trade_manager()
    if not ready:
        logging.error("[❌] TradeManager not ready after waiting; command ignored.")
        return

    logging.info(f"[💻] Command received: {cmd}")

    try:
        shared.trade_manager.handle_command(cmd)
    except Exception as e:
        logging.error(f"[❌] Failed to process command in TradeManager: {e}")

    if cmd.startswith("/start"):
        logging.info("[✅] Start command received — trading enabled.")
    elif cmd.startswith("/stop"):
        logging.info("[🛑] Stop command received — trading disabled.")
            
