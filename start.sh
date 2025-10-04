#!/bin/bash
set -e

# -------------------------
# Environment
# -------------------------
export DISPLAY=:1
export NO_VNC_HOME=/opt/noVNC
export VNC_RESOLUTION=${VNC_RESOLUTION:-1280x800}

# -------------------------
# Start DBus
# -------------------------
eval $(dbus-launch --sh-syntax)
echo "[ℹ️] DBus session started"

# -------------------------
# Start VNC server
# -------------------------
echo "[ℹ️] Starting VNC server..."
vncserver $DISPLAY -geometry ${VNC_RESOLUTION} -depth 24 -SecurityTypes None
echo "[✅] VNC server started on $DISPLAY with resolution ${VNC_RESOLUTION}"

# -------------------------
# Start Telegram listener (background, logs captured)
# -------------------------
echo "[ℹ️] Starting Telegram listener..."
python3 -u telegram_listener.py 2>&1 | tee /dev/stdout &
echo "[✅] Telegram listener started"

# -------------------------
# Start core bot in loop (background, logs captured)
# -------------------------
echo "[ℹ️] Starting core bot loop..."
(
while true; do
    echo "[ℹ️] Starting core bot..."
    python3 -u core.py 2>&1 | tee /dev/stdout || true
    echo "[⚠️] Core bot exited unexpectedly. Restarting in 5 seconds..."
    sleep 5
done
) &
echo "[✅] Core bot loop started"

# -------------------------
# Start noVNC in foreground (logs captured)
# -------------------------
echo "[ℹ️] Starting noVNC proxy in foreground..."
exec ${NO_VNC_HOME}/utils/novnc_proxy --vnc localhost:5901 --listen 8080
