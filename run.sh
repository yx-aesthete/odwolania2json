#!/usr/bin/env bash
# Uruchomienie jednym skryptem: ./run.sh  (input/ -> output/), ./run.sh --web (prototyp w przeglądarce)
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
[ -x .venv/bin/python ] && PY=.venv/bin/python
[ -f .env ] && set -a && . ./.env && set +a
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
if [ "${1:-}" = "--web" ]; then shift; exec "$PY" -m odwolania2json.web "$@"; fi
exec "$PY" -m odwolania2json --input ./input --output ./output "$@"
