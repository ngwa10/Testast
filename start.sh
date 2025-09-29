#!/bin/bash
set -e

# =========================
# Setup directories
# =========================
mkdir -p /home/dockuser/.vnc /home/dockuser/chrome-profile
chmod 700 /home/dockuser/.vnc

# Create xstartup script
cat > /home/dockuser/.vnc/xstartup << 'EOF'
#!/bin/bash
export XKL_XMODMAP_DISABLE=1
exec startxfce4
EOF
chmod +x /home/dockuser/.vnc/xstartup

# =========================
# Start VNC server
# =========================
echo "Starting VNC server..."
vncserver :1 -geometry 1280x800 -depth 24 -SecurityTypes None

# =========================
# Start noVNC
# =========================
echo "Starting noVNC..."
cd /opt/noVNC
/opt/noVNC/utils/websockify/run 6080 localhost:5901 --web /opt/noVNC &

# Give the desktop some time to start
sleep 5

# =========================
# Start Chrome with remote debugging
# =========================
echo "Starting Chrome..."
export DISPLAY=:1
google-chrome-stable "https://pocketoption.com/login" \
  --new-window \
  --no-sandbox \
  --disable-dev-shm-usage \
  --disable-gpu \
  --start-maximized \
  --remote-debugging-port=9222 \
  --user-data-dir=/home/dockuser/chrome-profile &

# Wait longer to ensure Chrome is fully ready
sleep 20

# =========================
# we will run a feature here that will automatically fill my password and Gmail in the pocket option login screen after chrome has launch and loaded

# =========================
# Start core.py (trade execution logic)
# =========================
echo "Starting trading core..."
python3 /home/dockuser/core.py &

# =========================
# Run Telegram listener with real callbacks
# =========================
echo "Starting Telegram listener..."
python3 - << 'PYTHON_EOF' &
import sys
sys.path.insert(0, '/home/dockuser')

from telegram_listener import start_telegram_listener
from telegram_callbacks import signal_callback, command_callback

start_telegram_listener(signal_callback, command_callback)
PYTHON_EOF

# =========================
# Keep the container running
# =========================
echo "✅ All services started. Container ready!"
tail -f /dev/null
