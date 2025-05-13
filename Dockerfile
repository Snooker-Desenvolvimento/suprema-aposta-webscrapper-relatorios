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

COPY gcp-key.json .
COPY .env .

# Set proper permissions for the key file
RUN chmod 400 gcp-key.json && \
  chmod 600 .env

# Install Python dependencies
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt 

# Copy the scraper script and make it executable
COPY scraper.py cronjob ./
RUN chmod +x scraper.py

# Add crontab file
RUN crontab cronjob

CMD ["cron", "-f"]