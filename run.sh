#!/usr/bin/env bash
# Uruchomienie jednym skryptem: ./run.sh  (input/ -> output/), ./run.sh --web (prototyp w przeglądarce)
# Plik .env czyta sam program (odporny na BOM, CRLF, spacje wokół „=”), więc powłoka go nie wciąga.
set -euo pipefail
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
[ -x .venv/bin/python ] && PY=.venv/bin/python
[ -z "${TESSDATA_PREFIX:-}" ] && [ -s .cache/tessdata/pol.traineddata ] && export TESSDATA_PREFIX="$PWD/.cache/tessdata"
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
if [ "${1:-}" = "--web" ]; then shift; exec "$PY" -m odwolania2json.web "$@"; fi
exec "$PY" -m odwolania2json --input ./input --output ./output "$@"
