#!/usr/bin/env bash
# Pomiar F1 (ścisły) na treningu UZP i zbiorze kontrolnym; same reguły, chyba że MODEL_TRYB ustawiony.
set -euo pipefail
cd "$(dirname "$0")/.."
T=$(mktemp -d -t o2j-mierz)
trap 'rm -rf "$T"' EXIT
export PYTHONPATH=src OCR=0
PY=${PYTHON:-.venv/bin/python}
"$PY" -m odwolania2json --input data/raw/uzp/dane --output "$T/tr" --audit "$T/atr" >/dev/null 2>&1
"$PY" -m odwolania2json --input tests/kontrolny/input --output "$T/k" --audit "$T/ak" 2>&1 | grep -E "nie dopasowano|->|^Podsumowanie" | sed 's/^/  /' > "$T/log"
echo "trening:   $("$PY" -m odwolania2json.eval --pred "$T/tr" --scisle 2>/dev/null | head -1 || true)"
if [ -d tests/kontrolny3/input ]; then
  "$PY" -m odwolania2json --input tests/kontrolny3/input --output "$T/k3" --audit "$T/ak3" >/dev/null 2>&1
  K3="$("$PY" -m odwolania2json.eval --gold tests/kontrolny3/oczekiwane --pred "$T/k3" --scisle 2>/dev/null | head -1 || true)"
fi
echo "kontrolny: $("$PY" -m odwolania2json.eval --gold tests/kontrolny/oczekiwane --pred "$T/k" --scisle 2>/dev/null | head -1 || true)"
[ -n "${K3:-}" ] && echo "K3 pełn.:  $K3"
grep -h "^  Podsumowanie" "$T/log" | sed 's/^  Podsumowanie: /model:     /' || true
[ "${1:-}" = "-v" ] && cat "$T/log" && "$PY" -m odwolania2json.eval --gold tests/kontrolny/oczekiwane --pred "$T/k" --scisle | sed -n '3,12p'
exit 0
