#!/bin/sh
set -eu
project=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
python_bin=${ADB_STUDIO_PYTHON:-python3}
"$python_bin" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else "Se requiere Python 3.12 o posterior")'
"$python_bin" -m venv "$project/.venv"
"$project/.venv/bin/python" -m pip install "$project"
"$project/.venv/bin/python" -m studio --check
if [ "${1:-}" != "--no-desktop" ]; then
    "$project/.venv/bin/python" "$project/scripts/desktop.py" "$project"
fi
printf '\nInicia la aplicación con %s/scripts/start.sh\n' "$project"
