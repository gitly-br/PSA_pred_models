FROM python:3.11-slim

# Set environment variables
ARG ENVIRONMENT
ENV NODE_ENV=${NODE_ENV}
ENV MONGO_URI=${MONGO_URI}
ENV OPENWEATHER_API_KEY=${OPENWEATHER_API_KEY}
ENV MONGO_GITLY_CONNECTION_STRING=mongodb+srv://reader:3GLmsYqBpZfD2o0C@settings-and-secrets.hruknje.mongodb.net/?retryWrites=true&w=majority

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc wget cron \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /backend

# Setup floodcast
COPY floodcast /backend/floodcast
RUN pip install --no-cache-dir ./floodcast

# Setup harvest
COPY harvest /backend/harvest
RUN pip install --no-cache-dir ./harvest

# Setup sentry
COPY sentry /backend/sentry
RUN pip install --no-cache-dir -r sentry/requirements.txt

# Ensure log file exists
RUN touch /var/log/cron.log

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Copy floodcast cookies
RUN mkdir -p /root/.cache/gdown
COPY floodcast/cookies.txt /root/.cache/gdown/cookies.txt

# Expose all necessary ports
EXPOSE 8000 6457 27017

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]

