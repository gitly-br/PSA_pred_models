#!/bin/bash

export MONGO_URI=${MONGO_URI}
export OPENWEATHER_API_KEY=${OPENWEATHER_API_KEY}
# Dump runtime env vars to a file cron can source
printenv | grep -v "no_proxy" > /etc/cron.env

# Start cron and tail its log
cron && tail -f /var/log/cron.log &

# Run the Sentry app
cd /backend/sentry/source
exec python run.py --env "$NODE_ENV"
