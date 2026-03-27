FROM python:3.11-slim

# System dependencies for Remotion (Chromium), ffmpeg, ffprobe
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    curl \
    # Chromium/headless Chrome dependencies required by Remotion
    libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libxshmfence1 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    fonts-liberation \
    fonts-noto-color-emoji \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js 20 for Remotion
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Node dependencies for Remotion
COPY remotion/package*.json remotion/
RUN cd remotion && npm ci --omit=dev

# Copy application code
COPY . .

# Create output directories and seed intelligence files (so bind mounts have valid defaults)
RUN mkdir -p outputs/logs outputs/images remotion/public/music \
    && echo '{}' > channel_insights.json \
    && echo '{}' > lessons_learned.json

# Expose dashboard port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Ensure intelligence files are valid JSON on startup
# Handles: first deploy (no file), Docker directory-mount (not a file), empty/corrupt file
# Then run scheduler (which starts the web server + scheduled jobs)
CMD ["sh", "-c", "\
  for f in channel_insights.json lessons_learned.json; do \
    if [ -d \"$f\" ]; then rm -rf \"$f\"; fi; \
    if [ ! -f \"$f\" ] || [ ! -s \"$f\" ]; then echo '{}' > \"$f\"; fi; \
  done && \
  exec python3 scheduler.py --daemon"]
