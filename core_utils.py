"""
Core utility functions for Pocket Option Trading Bot.
- Handles timezone conversion
- Loads humanized vibe logs from logs.json
- Provides random firing intervals for keystrokes
"""

import json
import random
from datetime import datetime
import pytz
import os

# =========================
# Load logs.json
# =========================
LOGS_FILE = os.path.join(os.path.dirname(__file__), "logs.json")

try:
    with open(LOGS_FILE, "r", encoding="utf-8") as f:
        LOG_MESSAGES = json.load(f)
except Exception:
    LOG_MESSAGES = [
        "Desmond got this one! A trade is about to begin. 🔥",
        "Precision is firing trades at maximum efficiency! 💥",
        "Trust the process, martingale in action! 💪",
        "Desmond’s bot is unstoppable, another stroke fired! ⚡",
        "How do you feel watching Desmond earn massively? 😎",
        "This is the best trading bot in the world. Precision mode ON! 🚀"
    ]

# =========================
# Timezone Conversion
# =========================
TIMEZONE_MAP = {
    "UTC-4": -4,
    "Cameroon": 1,   # Cameroon UTC+1
    "UTC-3": -3,
    "Jakarta": 7
}

def convert_signal_time(entry_time_str: str, signal_source: str) -> datetime:
    """
    Converts signal entry time from its source timezone to Jakarta timezone.
    entry_time_str: 'HH:MM'
    signal_source: 'UTC-4', 'Cameroon', or 'OTC-3'
    """
    fmt = "%H:%M"
    now = datetime.now()
    try:
        entry_dt = datetime.strptime(entry_time_str, fmt)
        entry_dt = entry_dt.replace(
            year=now.year, month=now.month, day=now.day
        )

        # Determine source offset
        if signal_source == "Cameroon":
            source_offset = TIMEZONE_MAP["Cameroon"]
        elif signal_source == "UTC-4":
            source_offset = TIMEZONE_MAP["UTC-4"]
        else:  # OTC-3 or unknown
            source_offset = TIMEZONE_MAP["UTC-3"]

        jakarta_offset = TIMEZONE_MAP["Jakarta"]
        delta_hours = jakarta_offset - source_offset
        entry_dt_jakarta = entry_dt + timedelta(hours=delta_hours)
        return entry_dt_jakarta
    except Exception:
        return datetime.now()  # fallback

# =========================
# Random firing interval
# =========================
def random_fire_interval():
    return random.randint(5, 9)  # seconds

# =========================
# Vibe log message
# =========================
def get_vibe_log():
    return random.choice(LOG_MESSAGES)
  
