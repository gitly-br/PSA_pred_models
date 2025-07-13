#!/bin/bash

# Create crontab with current environment variables
cat > /etc/cron.d/crontab << EOF
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
MONGO_URI=${MONGO_URI}
OPENWEATHER_API_KEY=${OPENWEATHER_API_KEY}

*/1 * * * * root psa-harvest >> /var/log/cron.log 2>&1
*/1 * * * * root psa-floodcast >> /var/log/cron.log 2>&1
EOF

chmod 0644 /etc/cron.d/crontab

# Start cron and tail its log
cron && tail -f /var/log/cron.log &

# Run the Sentry app
cd /backend/sentry/source
exec python run.py --env "$NODE_ENV"
