FROM python:3.9-slim

# Install Chromium and its dependencies
RUN apt-get update && apt-get install -y \
  chromium \
  chromium-driver \
  cron \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create necessary directories and set permissions
RUN mkdir -p /app/data /app/logs && \
  chmod -R 755 /app

# Copy GCP credentials
COPY gcp-key.json /app/gcp-key.json
ENV GOOGLE_APPLICATION_CREDENTIALS=/app/gcp-key.json

# Set proper permissions for the key file
RUN chmod 400 /app/gcp-key.json

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt 

# Copy the scraper script and make it executable
COPY scraper.py cronjob ./
RUN chmod +x scraper.py

# Add crontab file
RUN crontab cronjob

CMD ["cron", "-f"]