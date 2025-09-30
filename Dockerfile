FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:1 \
    VNC_RESOLUTION=1280x800 \
    NO_VNC_HOME=/opt/noVNC

# Install minimal packages first
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl wget ca-certificates gnupg2 \
    python3 python3-pip git \
    && rm -rf /var/lib/apt/lists/*

# Install Chrome (separate step to avoid timeout)
RUN curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

RUN apt-get update && apt-get install -y --no-install-recommends \
    google-chrome-stable \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install ChromeDriver (auto-match installed Chrome version)
RUN CHROME_VERSION=$(google-chrome --version | sed 's/[^0-9.]//g' | cut -d. -f1) \
    && LATEST_URL=$(curl -s "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROME_VERSION}") \
    && wget -O /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/${LATEST_URL}/linux64/chromedriver-linux64.zip" \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm -rf /tmp/chromedriver.zip /usr/local/bin/chromedriver-linux64

# Install VNC and desktop (minimal XFCE)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tigervnc-standalone-server \
    xfce4-session xfce4-panel \
    xfce4-terminal \
    dbus-x11 \
    procps dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Install noVNC
RUN git clone --depth 1 --branch v1.4.0 https://github.com/novnc/noVNC.git ${NO_VNC_HOME} \
    && git clone --depth 1 https://github.com/novnc/websockify.git ${NO_VNC_HOME}/utils/websockify \
    && chmod +x ${NO_VNC_HOME}/utils/websockify/run

# Create user
RUN useradd -m -s /bin/bash -u 1000 dockuser \
    && mkdir -p /home/dockuser/.vnc /home/dockuser/chrome-profile \
    && chown -R dockuser:dockuser /home/dockuser

# ✅ Install required Python packages
RUN pip3 install --no-cache-dir pytz
RUN pip3 install --no-cache-dir selenium telethon

# 🧰 Install pyautogui + X11 deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-tk python3-dev scrot xclip xsel \
    && pip3 install --no-cache-dir pyautogui pillow

# Copy start script
COPY start.sh /usr/local/bin/start.sh
RUN dos2unix /usr/local/bin/start.sh && chmod +x /usr/local/bin/start.sh

# Copy Selenium test script
COPY test_selenium.py /home/dockuser/test_selenium.py
RUN chown dockuser:dockuser /home/dockuser/test_selenium.py

# Copy core logic
COPY core.py /home/dockuser/core.py
RUN chown dockuser:dockuser /home/dockuser/core.py

# Copy Telegram scripts
COPY telegram_listener.py /home/dockuser/telegram_listener.py
COPY telegram_callbacks.py /home/dockuser/telegram_callbacks.py
RUN chown dockuser:dockuser /home/dockuser/telegram_listener.py /home/dockuser/telegram_callbacks.py

EXPOSE 5901 6080

USER dockuser
WORKDIR /home/dockuser

ENTRYPOINT ["/usr/local/bin/start.sh"]
