#!/bin/sh
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
if [ ! -x "$project/.venv/bin/python" ]; then
    printf '%s\n' 'Ejecuta scripts/install.sh primero.' >&2
    exit 1
fi
exec "$project/.venv/bin/python" -m studio "$@"
