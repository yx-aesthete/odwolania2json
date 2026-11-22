#!/usr/bin/env bash
# K5 (przypadki brzegowe, zadania/06-odwolania2json/kontrolny5-brzegowe) jak u UZP: .env, model, OCR.
# Użycie: scripts/mierz_k5.sh [--szczegoly]   (wynik w $K5_OUT, domyślnie katalog tymczasowy)
set -u
cd "$(dirname "$0")/.."
K=../../zadania/06-odwolania2json/kontrolny5-brzegowe
O=${K5_OUT:-$(mktemp -d)}; mkdir -p "$O"
PYTHONPATH=src .venv/bin/python -m odwolania2json --input $K/input --output $O/out --audit $O/audit > $O/log.txt 2>&1
PYTHONPATH=src .venv/bin/python -m odwolania2json.eval --gold $K/oczekiwane --pred $O/out --scisle 2>/dev/null \
  | if [ "${1:-}" = "--szczegoly" ]; then cat; else sed -n '1,9p'; fi
