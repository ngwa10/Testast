#!/bin/bash
set -e

# -------------------------
# Setup display for headless GUI
# -------------------------
echo "[🖥️] Starting Xvfb for headless GUI..."
export DISPLAY=:1
Xvfb :1 -screen 0 1280x800x24 &

# -------------------------
# Setup directories
# -------------------------
mkdir -p /home/dockuser/.vnc /home/dockuser/chrome-profile
chmod 700 /home/dockuser/.vnc

# Create xstartup script for VNC
cat > /home/dockuser/.vnc/xstartup << 'EOF'
#!/bin/bash
export XKL_XMODMAP_DISABLE=1
exec startxfce4
EOF
chmod +x /home/dockuser/.vnc/xstartup

# -------------------------
# Start VNC server
# -------------------------
echo "[🖥️] Starting VNC server..."
vncserver :1 -geometry 1280x800 -depth 24 -SecurityTypes None || echo "[❌] VNC failed"

# -------------------------
# Start noVNC
# -------------------------
echo "[🌐] Starting noVNC..."
cd /opt/noVNC
/opt/noVNC/utils/websockify/run 6080 localhost:5901 --web /opt/noVNC &

# Give desktop some time to start
sleep 5

# -------------------------
# Start core.py
# -------------------------
echo "[🤖] Starting core.py..."
python3 /home/dockuser/core.py 2>&1 | tee /home/dockuser/core.log &

# -------------------------
# Start Telegram listener
# -------------------------
echo "[💬] Starting Telegram listener..."
python3 /home/dockuser/telegram_listener.py 2>&1 | tee /home/dockuser/telegram.log &

# -------------------------
# Keep container alive
# -------------------------
echo "[✅] All services started. Container ready!"
tail -f /dev/null
