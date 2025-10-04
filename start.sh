#!/bin/bash
set -e

# -------------------------
# Setup
# -------------------------
mkdir -p /home/dockuser/.vnc /home/dockuser/chrome-profile
chmod 700 /home/dockuser/.vnc

# Create xstartup
cat > /home/dockuser/.vnc/xstartup << 'EOF'
#!/bin/bash
export XKL_XMODMAP_DISABLE=1
exec startxfce4
EOF
chmod +x /home/dockuser/.vnc/xstartup

# -------------------------
# Start VNC
# -------------------------
echo "[ℹ️] Starting VNC server..."
vncserver :1 -geometry 1280x800 -depth 24 -SecurityTypes None
echo "[✅] VNC server started on :1"

# -------------------------
# Start noVNC
# -------------------------
echo "[ℹ️] Starting noVNC proxy..."
cd /opt/noVNC
/opt/noVNC/utils/websockify/run 6080 localhost:5901 --web /opt/noVNC &
echo "[✅] noVNC started on port 6080"

# -------------------------
# Wait a few seconds for desktop
# -------------------------
sleep 5

# -------------------------
# Start Chrome in background
# -------------------------
echo "[ℹ️] Starting Chrome..."
export DISPLAY=:1
google-chrome-stable --no-sandbox --disable-dev-shm-usage --disable-gpu \
  --user-data-dir=/home/dockuser/chrome-profile \
  --start-maximized "https://pocketoption.com/login" &
echo "[✅] Chrome started"

# -------------------------
# Start Telegram listener in foreground
# -------------------------
echo "[ℹ️] Starting Telegram listener..."
export DISPLAY=:1
exec python3 -u /home/dockuser/telegram_listener.py
