#!/bin/sh

set -eu

python /app/docker/wait_for_db.py
python manage.py migrate --noinput

seed_demo=$(printf "%s" "${SEED_DEMO:-false}" | tr "[:upper:]" "[:lower:]")
case "${seed_demo}" in
    1|true|yes|on)
        python manage.py seed_demo
        ;;
esac

exec "$@"
