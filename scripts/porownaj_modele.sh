#!/usr/bin/env bash
# Porównanie wariantów modelu (Z5): same reguły vs modele po API (adres i klucz z .env).
# Użycie: scripts/porownaj_modele.sh [model ...]   (domyślnie lista z Z5, od najmniejszego)
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
MODELE=("$@")
[ ${#MODELE[@]} -eq 0 ] && MODELE=(qwen3.6-35b-a3b gemma-4-26b-a4b-it mistral-small-3.2-24b-instruct-2506 gpt-oss-120b qwen3.5-397b-a17b)
echo "| Wariant | trening F1 | kontrolny F1 | czas | wywołania modelu |"
echo "|---|---|---|---|---|"
wiersz() {  # $1 nazwa, reszta: zmienne środowiska
  local nazwa=$1; shift
  local s=$(date +%s) out
  out=$(env "$@" scripts/mierz.sh 2>&1)
  local tr=$(echo "$out" | sed -n 's/^trening:.*ścisły: \([0-9.]*\).*/\1/p')
  local k=$(echo "$out" | sed -n 's/^kontrolny:.*ścisły: \([0-9.]*\).*/\1/p')
  local w=$(echo "$out" | sed -n 's/^model:.*: \(.*\)/\1/p')
  echo "| $nazwa | $tr | $k | $(( $(date +%s)-s )) s | ${w:-—} |"
}
wiersz "same reguły" MODEL_TRYB=brak
for m in "${MODELE[@]}"; do
  wiersz "reguły + $m (API)" MODEL_TRYB=api LLM_MODEL="$m"
done
