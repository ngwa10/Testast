FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:1 \
    VNC_RESOLUTION=1280x800 \
    NO_VNC_HOME=/opt/noVNC

# -------------------------
# Install system packages
# -------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates gnupg2 software-properties-common \
    python3 python3-pip git unzip \
    xfce4 xfce4-terminal dbus dbus-x11 procps dos2unix \
    python3-tk python3-dev scrot xclip xsel \
    xvfb x11-utils tigervnc-standalone-server pulseaudio alsa-utils \
    ffmpeg \
    libsm6 libxext6 libxrender-dev libglib2.0-0 \
    tesseract-ocr tesseract-ocr-eng \
    && apt-get clean && rm -rf /var/lib/apt/lists/*


# -------------------------
# Install Google Chrome
# -------------------------
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update && apt-get install -y --no-install-recommends google-chrome-stable \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# -------------------------
# Install ChromeDriver
# -------------------------
RUN CHROME_VERSION=$(google-chrome --version | sed 's/[^0-9.]//g' | cut -d. -f1) \
    && LATEST_URL=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_VERSION}") \
    && wget -O /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/${LATEST_URL}/linux64/chromedriver-linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver.zip /usr/local/bin/chromedriver-linux64

# -------------------------
# Install Python dependencies
# -------------------------
RUN pip3 install --no-cache-dir \
    pytz selenium telethon numpy python-dotenv pyautogui pillow sounddevice opencv-python pytesseract

# -------------------------
# Install noVNC
# -------------------------
RUN git clone --depth 1 --branch v1.4.0 https://github.com/novnc/noVNC.git ${NO_VNC_HOME} \
    && git clone --depth 1 https://github.com/novnc/websockify.git ${NO_VNC_HOME}/utils/websockify \
    && chmod +x ${NO_VNC_HOME}/utils/websockify/run

# -------------------------
# Create non-root user
# -------------------------
RUN useradd -m -s /bin/bash -u 1000 dockuser \
    && mkdir -p /home/dockuser/.vnc /home/dockuser/chrome-profile

# -------------------------
# Configure VNC xstartup for XFCE
# -------------------------
RUN echo '#!/bin/bash\nxrdb $HOME/.Xresources\nstartxfce4 &' > /home/dockuser/.vnc/xstartup \
    && chmod +x /home/dockuser/.vnc/xstartup

# -------------------------
# Copy project files
# -------------------------
COPY . /home/dockuser/

# ✅ Fix: run dos2unix + chmod before switching to non-root user
RUN find /home/dockuser -type f -name "*.sh" -exec dos2unix {} \; && chmod +x /home/dockuser/*.sh

# -------------------------
# Switch to non-root user
# -------------------------
USER dockuser
WORKDIR /home/dockuser

# -------------------------
# Expose VNC and noVNC ports
# -------------------------
EXPOSE 5901 8080

# -------------------------
# Entrypoint
# -------------------------
ENTRYPOINT ["/home/dockuser/start.sh"]
