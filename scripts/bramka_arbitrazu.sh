#!/usr/bin/env bash
# Bramka lokalna arbitrażu model ↔ reguły (Z19/Z21): z MODEL_ARBITRAZ=1 model ma nie zmienić żadnego pola
# na treningu, K1 i K3 (reguły są tam poprawne), a dwa przebiegi pod rząd mają dać identyczny wynik.
set -uo pipefail
cd "$(dirname "$0")/.."
T=$(mktemp -d -t o2j-bramka)
trap 'rm -rf "$T"' EXIT
export PYTHONPATH=src OCR=0
PY=${PYTHON:-.venv/bin/python}
for zb in "trening:data/raw/uzp/dane" "K1:tests/kontrolny/input" "K3:tests/kontrolny3/input"; do
  nazwa=${zb%%:*}; kat=${zb#*:}
  for przebieg in 1 2; do
    MODEL_ARBITRAZ=1 "$PY" -m odwolania2json --input "$kat" --output "$T/$nazwa-$przebieg" --audit "$T/a-$nazwa-$przebieg" >/dev/null 2>&1
  done
  zmiany=$(grep -rho '"model#dokument"' "$T/a-$nazwa-1" | wc -l | tr -d ' ')
  roznice=$(diff -r "$T/$nazwa-1" "$T/$nazwa-2" | grep -c '^[<>]' || true)
  echo "$nazwa: pola zmienione przez model: $zmiany, różnice między przebiegami: $roznice"
  [ "$zmiany" -eq 0 ] || grep -rh -A2 '"model#dokument"' "$T/a-$nazwa-1" | grep -E '"pole"|"wartosc"' | head -6
done
exit 0
