# Use a lightweight Python base image
FROM python:3.11-bullseye

# Define build arguments and environment variables
ARG ENVIRONMENT
ENV NODE_ENV=${ENVIRONMENT}

ENV MONGO_GITLY_CONNECTION_STRING=mongodb+srv://reader:3GLmsYqBpZfD2o0C@settings-and-secrets.hruknje.mongodb.net/?retryWrites=true&w=majority

# Install build dependencies and remove unnecessary packages after installation
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc wget cron \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better layer caching
COPY requirements.txt .
# Install Python dependencies efficiently
RUN pip install --no-cache-dir -r requirements.txt

# Copy only necessary files (avoid unnecessary build context)
COPY deployment /deployment
COPY source /source
COPY keys /keys

# Set permissions for scripts
RUN chmod +x /deployment/github_pull.sh \
    && echo "*/1 * * * * /bin/bash /deployment/github_pull.sh" > /var/spool/cron/crontabs/root

WORKDIR /source

# Define volumes (optional, useful for development)
VOLUME /source

# Expose necessary ports
EXPOSE 8000 6457

# Default command
CMD ["python", "/source/run.py", "--env", "$NODE_ENV"]

