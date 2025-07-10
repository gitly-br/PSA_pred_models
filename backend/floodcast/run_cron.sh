#!/bin/bash
set -a
source /etc/cron.env
set +a

cd /backend/harvest
exec python -m harvest.main
