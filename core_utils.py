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
    """
    fmt = "%H:%M"
    try:
        # Parse time
        entry_dt = datetime.strptime(entry_time_str, fmt)

        # Validate hours and minutes
        if not (0 <= entry_dt.hour <= 23 and 0 <= entry_dt.minute <= 59):
            raise ValueError(f"Invalid time: {entry_time_str}")

        # Determine source offset
        tz_lower = source_tz_str.lower()
        if tz_lower == "utc-4":
            src_offset = -4
        elif tz_lower == "cameroon":
            src_offset = 1  # UTC+1
        else:
            src_offset = -3  # default UTC-3

        # Assign fixed offset timezone
        entry_dt = entry_dt.replace(tzinfo=pytz.FixedOffset(src_offset * 60))

        # Convert to Jakarta time
        jakarta_tz = pytz.timezone("Asia/Jakarta")
        entry_dt_jakarta = entry_dt.astimezone(jakarta_tz)

        return entry_dt_jakarta.strftime(fmt)

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
    
