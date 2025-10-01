"""
Utility functions for core.py
- Timezone conversion: converts signal times to UTC for internal scheduling
- Interactive logging messages
"""

from datetime import datetime, timedelta
import pytz
import random
import logging

logger = logging.getLogger(__name__)

# --------------------------
# Convert sender timezone to UTC for scheduling
# --------------------------
def timezone_convert(entry_time_str, source_tz_str):
    """
    Converts a time string (HH:MM) from the sender timezone to UTC.
    Handles:
    - IANA timezone names
    - Fixed UTC offsets (UTC-3, UTC+2, etc.)
    - Cameroon signals (UTC+1)
    - OTC-X signals (e.g., OTC-3 -> UTC-3)
    Returns a datetime object in UTC, or None if the signal has already passed.
    """
    fmt = "%H:%M"
    try:
        entry_time = datetime.strptime(entry_time_str, fmt).time()
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

        # Current time in source timezone
        now_src = datetime.now(pytz.utc).astimezone(src_tz)

        # Combine today's date with entry_time
        entry_dt = datetime.combine(now_src.date(), entry_time)
        entry_dt = src_tz.localize(entry_dt) if entry_dt.tzinfo is None else entry_dt

        # If entry already passed, ignore signal
        if entry_dt < now_src:
            return None

        # Convert to UTC for internal scheduling
        entry_utc = entry_dt.astimezone(pytz.UTC)
        return entry_utc

    except Exception as e:
        logger.warning(f"[⚠️] Failed timezone conversion for '{entry_time_str}' ({source_tz_str}): {e}")
        return None

# --------------------------
# Random interactive log message
# --------------------------
def get_random_log_message(log_messages):
    if not log_messages:
        return ""
    msg = random.choice(log_messages)
    return f"[🤖] {msg}"
                
