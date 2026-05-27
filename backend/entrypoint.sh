#!/bin/bash

# Create crontab with current environment variables
cat > /etc/cron.d/crontab << EOF
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MONGO_URI=${MONGO_URI}
OPENWEATHER_API_KEY=${OPENWEATHER_API_KEY}
DEFESA_CIVIL_API_ID=${DEFESA_CIVIL_API_ID}
DEFESA_CIVIL_SISTEMA_ID=${DEFESA_CIVIL_SISTEMA_ID}

*/30 * * * * root psa-harvest >> /var/log/cron.log 2>&1
5,35 0 * * * root psa-floodcast >> /var/log/cron.log 2>&1
0 3,4,5,6,9,12,15 * * * root psa-floodcast >> /var/log/cron.log 2>&1
EOF

chmod 0644 /etc/cron.d/crontab

# Kill any existing cron processes and clean up PID file
pkill cron || true
rm -f /var/run/crond.pid

# Start cron and tail its log
cron && tail -f /var/log/cron.log &

# Run the Sentry app
cd /backend/sentry/source
exec python run.py --env "$NODE_ENV"
