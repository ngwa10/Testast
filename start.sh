#!/bin/bash
echo "[INFO] Starting virtual display (Xvfb)..."
Xvfb :1 -screen 0 1280x800x24 &

# wait a moment to ensure Xvfb is ready
sleep 2

export DISPLAY=:1
echo "[INFO] DISPLAY set to :1"

# run your debug script
echo "[INFO] Starting debug_core.py..."
python3 debug_core.py
