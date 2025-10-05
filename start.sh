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
# Start VNC (background for possible GUI, not core)
# -------------------------
echo "[ℹ️] Starting VNC server..."
vncserver :1 -geometry 1280x800 -depth 24 -SecurityTypes None
echo "[✅] VNC server started on :1"

# -------------------------
# Start core.py in background
# -------------------------
echo "[ℹ️] Starting core.py..."
export DISPLAY=:1
python3 -u /home/dockuser/core.py &
CORE_PID=$!
echo "[✅] core.py started with PID $CORE_PID"

# -------------------------
# Start Telegram listener in foreground
# -------------------------
echo "[ℹ️] Starting Telegram listener..."
export DISPLAY=:1
exec python3 -u /home/dockuser/telegram_listener.py
