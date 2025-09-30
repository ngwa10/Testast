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
    fmt = "%H:%M"
    try:
        entry_dt = datetime.strptime(entry_time_str, fmt)
        if source_tz_str.lower() in ["utc-4", "cameroon"]:
            src_offset = -4 if source_tz_str.lower() == "utc-4" else 1  # Cameroon UTC+1
        else:
            src_offset = -3  # Default UTC-3

        entry_dt = entry_dt.replace(tzinfo=pytz.FixedOffset(src_offset * 60))
        jakarta_tz = pytz.timezone("Asia/Jakarta")
        entry_dt_jakarta = entry_dt.astimezone(jakarta_tz)
        return entry_dt_jakarta.strftime(fmt)
    except Exception as e:
        logger.warning(f"[⚠️] Failed timezone conversion: {e}")
        return entry_time_str

# --------------------------
# Random interactive log message
# --------------------------
def get_random_log_message(log_messages):
    if not log_messages:
        return ""
    msg = random.choice(log_messages)
    return f"[🤖] {msg}"
    
