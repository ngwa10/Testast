#!/bin/bash
# start.sh — temporary debug version

# start virtual display for pyautogui / Selenium
Xvfb :1 -screen 0 1280x800x24 &
export DISPLAY=:1

# run the debug Python script
python3 debug_core.py
