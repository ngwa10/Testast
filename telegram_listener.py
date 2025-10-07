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
    Converts entry_time_val from sender timezone to a timezone-aware datetime (UTC).
    - Rejects signals if they are even 1 second in the past.
    - No grace period. Perfect for precision trading (M1/M5 signals).
    """
    try:
        tz_lower = source_tz_str.lower().strip()
        # Resolve source timezone
        if tz_lower.startswith("utc"):
            sign = 1 if "+" in tz_lower else -1
            try:
                hours = int(tz_lower.split("utc")[1].replace("+", "").replace("-", ""))
                src_tz = pytz.FixedOffset(sign * hours * 60)
            except Exception:
                src_tz = pytz.UTC
        elif tz_lower == "cameroon":
            src_tz = pytz.timezone("Africa/Douala")  # UTC+1
        elif tz_lower.startswith("otc-"):
            try:
                offset_hours = int(tz_lower.split("-")[1])
                src_tz = pytz.FixedOffset(-offset_hours * 60)
            except Exception:
                src_tz = pytz.UTC
        else:
            try:
                src_tz = pytz.timezone(source_tz_str)
            except Exception:
                src_tz = pytz.UTC

        # Current time in source timezone
        now_src = datetime.now(pytz.utc).astimezone(src_tz)

        # Parse input into datetime
        if isinstance(entry_time_val, datetime):
            entry_dt = (
                src_tz.localize(entry_time_val)
                if entry_time_val.tzinfo is None
                else entry_time_val.astimezone(src_tz)
            )
        elif isinstance(entry_time_val, str):
            entry_time = datetime.strptime(entry_time_val, "%H:%M").time()
            entry_dt = datetime.combine(now_src.date(), entry_time)
            entry_dt = src_tz.localize(entry_dt)
        else:
            logger.warning(f"[⚠️] Invalid entry_time type: {type(entry_time_val)}")
            return None

        # ❗ STRICT CHECK: Reject if already in the past
        if entry_dt <= now_src:
            logger.info(f"[⏱️] Signal time {entry_dt} has already passed. Rejecting trade.")
            return None

        # ✅ Convert to UTC before returning
        return entry_dt.astimezone(pytz.UTC)

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
            
