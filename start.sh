#!/bin/bash
set -e

# =========================
# Setup directories
# =========================
mkdir -p /home/dockuser/.vnc /home/dockuser/chrome-profile
chmod 700 /home/dockuser/.vnc

# Create xstartup script for VNC
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
google-chrome-stable "https://pocketoption.com/en/login/" \
  --new-window \
  --no-sandbox \
  --disable-dev-shm-usage \
  --disable-gpu \
  --start-maximized \
  --remote-debugging-port=9222 \
  --user-data-dir=/home/dockuser/chrome-profile &

# Wait for Chrome to fully start
sleep 20

# =========================
# Run Selenium auto-login test
# =========================
echo "[🧪] Running Selenium auto-login test..."
python3 /home/dockuser/test_selenium.py
SELENIUM_EXIT=$?

if [ $SELENIUM_EXIT -ne 0 ]; then
  echo "[❌] Selenium test / auto-login failed! Stopping container..."
  exit 1
else
  echo "[✅] Selenium test passed! Continuing startup..."
fi

# =========================
# Start core.py (trade execution logic)
# =========================
echo "Starting trading core..."
python3 /home/dockuser/core.py &

# =========================
# Start Telegram listener with real callbacks
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
