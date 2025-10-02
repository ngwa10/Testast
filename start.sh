#!/bin/bash
echo "[INFO] Starting virtual display (Xvfb)..."
Xvfb :1 -screen 0 1280x800x24 -ac &

sleep 2

export DISPLAY=:1
export XAUTHORITY=/home/dockuser/.Xauthority
touch /home/dockuser/.Xauthority

echo "[INFO] DISPLAY set to :1"
echo "[INFO] Starting debug_core.py..."
python3 debug_core.py
