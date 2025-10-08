"""
core_utils.py — Timezone conversion and logging helpers
"""

from datetime import datetime, timedelta
import pytz
import logging
import random

logger = logging.getLogger(__name__)

# --------------------------
# Convert sender timezone to UTC or signal's tz for scheduling
# Handles:
# - Strings "HH:MM"
# - datetime.datetime (naive or tz-aware)
# - Cameroon, UTC offsets, OTC-X
# --------------------------
def timezone_convert(entry_time_val, source_tz_str):
    """
    Converts entry_time_val from sender timezone to a timezone-aware datetime.
    Returns datetime in signal's timezone or None if the signal has already passed.
    Accepts:
    - entry_time_val: str ("HH:MM") or datetime.datetime
    - source_tz_str: timezone string like "Cameroon", "UTC-4", "OTC-3"
    """
    try:
        tz_lower = source_tz_str.lower().strip()
        # Determine source timezone
        if tz_lower.startswith("utc"):
            sign = 1 if "+" in tz_lower else -1
            try:
                hours = int(tz_lower.split("utc")[1].replace("+", "").replace("-", ""))
                src_tz = pytz.FixedOffset(sign * hours * 60)
            except Exception:
                src_tz = pytz.UTC
                logger.warning(f"[⚠️] Could not parse UTC offset from '{source_tz_str}', defaulting UTC")
        elif tz_lower == "cameroon":
            src_tz = pytz.timezone("Africa/Douala")  # UTC+1
        elif tz_lower.startswith("otc-"):
            try:
                offset_hours = int(tz_lower.split("-")[1])
                src_tz = pytz.FixedOffset(-offset_hours * 60)  # OTC-3 -> UTC-3
            except Exception:
                src_tz = pytz.UTC
                logger.warning(f"[⚠️] Could not parse OTC offset from '{source_tz_str}', defaulting UTC")
        else:
            try:
                src_tz = pytz.timezone(source_tz_str)
            except Exception:
                src_tz = pytz.UTC
                logger.warning(f"[⚠️] Unrecognized timezone '{source_tz_str}', defaulting UTC")

        now_src = datetime.now(pytz.utc).astimezone(src_tz)

        # Handle datetime input
        if isinstance(entry_time_val, datetime):
            if entry_time_val.tzinfo is None:
                entry_dt = src_tz.localize(entry_time_val)
            else:
                entry_dt = entry_time_val.astimezone(src_tz)
        # Handle string input
        elif isinstance(entry_time_val, str):
            fmt = "%H:%M"
            entry_time = datetime.strptime(entry_time_val, fmt).time()
            entry_dt = datetime.combine(now_src.date(), entry_time)
            entry_dt = src_tz.localize(entry_dt) if entry_dt.tzinfo is None else entry_dt
        else:
            logger.warning(f"[⚠️] Invalid entry_time type: {type(entry_time_val)}")
            return None

        # Ignore past signals
        if entry_dt < now_src:
            return None

        return entry_dt

    except Exception as e:
        logger.warning(f"[⚠️] Failed timezone conversion for '{entry_time_val}' ({source_tz_str}): {e}")
        return None

# --------------------------
# Random interactive log message
# --------------------------
def get_random_log_message(log_messages):
    if not log_messages:
        return ""
    msg = random.choice(log_messages)
    return f"[🤖] {msg}"
                            
