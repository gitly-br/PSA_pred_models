FROM python:3.11-slim

# Set environment variables
ARG NODE_ENV
ENV NODE_ENV=${NODE_ENV}
ENV MONGO_GITLY_CONNECTION_STRING=mongodb+srv://reader:3GLmsYqBpZfD2o0C@settings-and-secrets.hruknje.mongodb.net/?retryWrites=true&w=majority

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc wget cron \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency resolution
RUN pip install --no-cache-dir uv

WORKDIR /backend

# Setup floodcast
COPY floodcast /backend/floodcast
RUN uv pip install --system ./floodcast

# Setup harvest
COPY harvest /backend/harvest
RUN uv pip install --system ./harvest

# Setup sentry
COPY sentry /backend/sentry
RUN uv pip install --system -r sentry/requirements.txt

# Ensure log file exists
RUN touch /var/log/cron.log

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose all necessary ports
EXPOSE 8000 6457 27017

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]
