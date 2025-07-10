FROM python:3.11-bullseye

# Set environment variables
ARG ENVIRONMENT
ENV NODE_ENV=${ENVIRONMENT}
ENV MONGO_GITLY_CONNECTION_STRING=mongodb+srv://reader:3GLmsYqBpZfD2o0C@settings-and-secrets.hruknje.mongodb.net/?retryWrites=true&w=majority

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc wget cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /backend

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create the env file for cron
RUN echo "MONGO_URI=${MONGO_URI}" >> /etc/cron.env && \
    echo "OPENWEATHER_API_KEY=${OPENWEATHER_API_KEY}" >> /etc/cron.env && \
    echo "NODE_ENV=${NODE_ENV}" >> /etc/cron.env

# Setup cron jobs
COPY crontab /etc/cron.d/crontab
RUN chmod 0644 /etc/cron.d/crontab

# Ensure log file exists
RUN touch /var/log/cron.log

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy application code
COPY floodcast /backend/floodcast
COPY harvest /backend/harvest
COPY sentry /backend/sentry

RUN chmod +x /backend/harvest/run_cron.sh
RUN chmod +x /backend/floodcast/run_cron.sh

# Copy dotenv
COPY .env /backend/harvest/.env
COPY .env /backend/floodcast/.env

# Copy floodcast cookies
RUN mkdir -p /root/.cache/gdown
COPY floodcast/cookies.txt /root/.cache/gdown/cookies.txt

# Expose all necessary ports
EXPOSE 8000 6457 27017

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]

