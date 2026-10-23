#!/bin/sh
set -e
mkdir -p /app/data/cms /app/data/uploads /app/data/memory /app/data/logs /app/data/dev
if [ ! -f /app/data/cms/site.json ]; then
  cp /app/seed/cms/site.json /app/data/cms/site.json
  echo "seeded default CMS site.json"
fi
exec "$@"
