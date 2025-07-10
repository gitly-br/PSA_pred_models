#!/bin/bash
set -a
source /etc/cron.env
set +a

cd /backend/floodcast
exec python -m floodcast.main
