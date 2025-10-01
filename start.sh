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
echo "🚀 Starting VNC server..."
vncserver :1 -geometry 1280x800 -depth 24 -SecurityTypes None

# =========================
# Start noVNC
# =========================
echo "🌐 Starting noVNC..."
cd /opt/noVNC
/opt/noVNC/utils/websockify/run 6080 localhost:5901 --web /opt/noVNC &

# Give desktop some time to start
sleep 5

# =========================
# Start Telegram listener (background OK)
# =========================
echo "📨 Starting Telegram listener..."
python3 - << 'PYTHON_EOF' &
import sys
sys.path.insert(0, '/home/dockuser')

from telegram_listener import start_telegram_listener
from telegram_callbacks import signal_callback, command_callback

start_telegram_listener(signal_callback, command_callback)
PYTHON_EOF

# =========================
# Start core.py in foreground (IMPORTANT)
# =========================
echo "🤖 Starting trading core in foreground..."
exec python3 -u /home/dockuser/core.py
