"""
Utility functions for core.py
- Timezone conversion
- Interactive logging messages
"""

from datetime import datetime, timedelta
import pytz
import random
import logging

logger = logging.getLogger(__name__)

# --------------------------
# Convert sender timezone to Jakarta time
# --------------------------
def timezone_convert(entry_time_str, source_tz_str):
    """
    Converts a time string (HH:MM) from the sender timezone to Jakarta timezone (UTC+7).
    Validates the input format and ensures hours 0-23, minutes 0-59.
    Works with standard IANA timezone names or simple UTC offsets like 'UTC-3', 'UTC+2'.
    """
    fmt = "%H:%M"
    try:
        # Parse time
        entry_dt = datetime.strptime(entry_time_str, fmt)

        # Validate hours and minutes
        if not (0 <= entry_dt.hour <= 23 and 0 <= entry_dt.minute <= 59):
            raise ValueError(f"Invalid time: {entry_time_str}")

        # Determine source timezone
        tz_lower = source_tz_str.lower()
        if tz_lower == "utc-4":
            src_tz = pytz.FixedOffset(-4 * 60)
        elif tz_lower == "utc-3":
            src_tz = pytz.FixedOffset(-3 * 60)
        elif tz_lower == "cameroon":
            src_tz = pytz.timezone("Africa/Douala")  # UTC+1
        else:
            # Attempt to treat as IANA timezone
            try:
                src_tz = pytz.timezone(source_tz_str)
            except Exception:
                src_tz = pytz.UTC  # fallback UTC

        # Assign a date (today) and localize
        today = datetime.now(pytz.utc).date()
        entry_dt = entry_dt.replace(year=today.year, month=today.month, day=today.day)
        entry_dt = src_tz.localize(entry_dt) if not entry_dt.tzinfo else entry_dt

        # Convert to Jakarta
        jakarta_tz = pytz.timezone("Asia/Jakarta")
        entry_jkt = entry_dt.astimezone(jakarta_tz)

        return entry_jkt.strftime(fmt)

    except Exception as e:
        logger.warning(f"[⚠️] Failed timezone conversion for '{entry_time_str}' ({source_tz_str}): {e}")
        return None  # return None if invalid

# --------------------------
# Random interactive log message
# --------------------------
def get_random_log_message(log_messages):
    if not log_messages:
        return ""
    msg = random.choice(log_messages)
    return f"[🤖] {msg}"
        
