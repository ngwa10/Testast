#!/bin/bash
set -e

# -------------------------
# Environment variables
# -------------------------
# Pick a free DISPLAY if not set
if [ -z "$DISPLAY" ]; then
    for i in {1..99}; do
        if ! xdpyinfo -display :$i >/dev/null 2>&1; then
            export DISPLAY=:$i
            break
        fi
    done
fi

export VNC_RESOLUTION=${VNC_RESOLUTION:-1024x600}
export NO_VNC_HOME=${NO_VNC_HOME:-/opt/noVNC}

echo "[ℹ️] Starting container with DISPLAY=$DISPLAY and RESOLUTION=$VNC_RESOLUTION"

# -------------------------
# Start D-Bus (optional)
# -------------------------
if [ ! -S /run/dbus/system_bus_socket ]; then
    echo "[ℹ️] Starting dbus..."
    mkdir -p /var/run/dbus
    dbus-daemon --system --fork
fi

# -------------------------
# Start virtual display (Xvfb)
# -------------------------
echo "[ℹ️] Starting Xvfb..."
Xvfb $DISPLAY -screen 0 ${VNC_RESOLUTION}x24 &
XVFB_PID=$!
sleep 5
echo "[✅] Xvfb started (PID: $XVFB_PID)"

# -------------------------
# Start noVNC web interface
# -------------------------
if [ -d "$NO_VNC_HOME" ]; then
    echo "[ℹ️] Starting noVNC web interface..."
    ${NO_VNC_HOME}/utils/novnc_proxy --vnc localhost:5901 --listen 0.0.0.0:6080 &
    NOVNC_PID=$!
    echo "[✅] noVNC started on port 6080 (PID: $NOVNC_PID)"
fi

# -------------------------
# Start TigerVNC server
# -------------------------
echo "[ℹ️] Starting TigerVNC server..."
vncserver $DISPLAY -geometry ${VNC_RESOLUTION} -depth 24 &
VNC_PID=$!
sleep 5
echo "[✅] VNC server started (PID: $VNC_PID)"

# -------------------------
# Launch Google Chrome
# -------------------------
echo "[ℹ️] Launching Chrome browser..."
google-chrome-stable \
    --no-sandbox \
    --disable-setuid-sandbox \
    --disable-gpu \
    --disable-dev-shm-usage \
    --disable-software-rasterizer \
    --disable-extensions \
    --disable-background-networking \
    --disable-sync \
    --disable-component-update \
    --disable-client-side-phishing-detection \
    --single-process \
    --no-first-run \
    --no-default-browser-check \
    --user-data-dir=/home/dockuser/chrome-profile \
    --start-maximized \
    http://pocketoption.com/en/login/ &
CHROME_PID=$!

sleep 20
echo "[✅] Chrome launched (PID: $CHROME_PID)"

# -------------------------
# Start Python background services
# -------------------------
echo "[ℹ️] Starting Python services..."
python3 -u telegram_listener.py >> /home/dockuser/telegram.log 2>&1 &
TL_PID=$!
sleep 5
python3 -u screen_logic.py >> /home/dockuser/screen_logic.log 2>&1 &
SL_PID=$!
sleep 5
echo "[✅] Python background services started."

# -------------------------
# Run core bot with automatic restart
# -------------------------
while true; do
    echo "[ℹ️] Starting core bot..."
    python3 -u core.py >> /home/dockuser/core.log 2>&1
    EXIT_CODE=$?
    if [ $EXIT_CODE -ne 0 ]; then
        echo "[⚠️] Core bot crashed with exit code $EXIT_CODE. Restarting in 5s..."
        sleep 5
    else
        echo "[ℹ️] Core bot finished normally. Exiting loop."
        break
    fi
done

# -------------------------
# Cleanup on exit
# -------------------------
echo "[ℹ️] Stopping processes..."
kill $CHROME_PID || true
kill $TL_PID || true
kill $SL_PID || true
kill $VNC_PID || true
kill $XVFB_PID || true
[ -n "$NOVNC_PID" ] && kill $NOVNC_PID || true
echo "[✅] All processes stopped. Container exiting."
