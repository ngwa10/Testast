#!/bin/bash
set -e
set -x   # 👈 debugging output

# -------------------------
# Environment
# -------------------------
export DISPLAY=:1
export NO_VNC_HOME=/opt/noVNC
export VNC_RESOLUTION=${VNC_RESOLUTION:-1280x1000}

echo "[🛠️] Preparing environment..."

# -------------------------
# Start VNC server
# -------------------------
echo "[📡] Starting VNC server..."
vncserver :1 -geometry ${VNC_RESOLUTION} -depth 24 -SecurityTypes None
echo "[✅] VNC server started on :1 (${VNC_RESOLUTION})"

# -------------------------
# Start noVNC
# -------------------------
${NO_VNC_HOME}/utils/novnc_proxy --vnc localhost:5901 --listen 6080 &
echo "[✅] noVNC started on port 6080"

# -------------------------
# Start PulseAudio with monitor sink (for audio detection)
# -------------------------
echo "[🔊] Starting PulseAudio..."
pulseaudio --start

# Create a null sink to capture audio from apps
SINK_NAME="VNCOutput"
pactl load-module module-null-sink sink_name=$SINK_NAME sink_properties=device.description=$SINK_NAME

# List the monitor source for debugging
echo "[ℹ️] Available PulseAudio sources:"
pactl list short sources

echo "[✅] Monitor audio device ready. Use '${SINK_NAME}.monitor' in win_loss.py for recording."

# -------------------------
# Wait for display and audio to be ready
# -------------------------
sleep 5

# -------------------------
# Start Chrome launcher
# -------------------------
python3 -u launcher.py &
echo "[ℹ️] Chrome launcher started in background"

# -------------------------
# Start Telegram listener
# -------------------------
python3 -u telegram_listener.py &
echo "[ℹ️] Telegram listener started in background"

# -------------------------
# Start core bot (with restart loop)
# -------------------------
while true; do
    echo "[ℹ️] Starting core bot..."
    python3 -u core.py
    exit_code=$?
    if [ $exit_code -ne 0 ]; then
        echo "[⚠️] Core bot exited with code $exit_code. Restarting in 5 seconds..."
        sleep 5
    else
        echo "[✅] Core bot finished normally. Keeping container alive..."
        sleep 10   # short delay before restarting core bot
    fi
done
