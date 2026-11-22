#!/usr/bin/env bash
# Instalacja na VM UZP (Ubuntu 24.04, Docker + Compose v2). Uruchom jako root/sudo. Idempotentny.
# REPO=<adres repozytorium> ./instaluj.sh    (domyślnie publiczne repo zgłoszenia)
set -euo pipefail
REPO=${REPO:-https://github.com/yx-aesthete/odwolania2json.git}
SOL=${SOLUTION_DIR:-/opt/solution}
APP=$SOL/app
mkdir -p "$SOL/input" "$SOL/output" "$SOL/audit"
if [ -d "$APP/.git" ]; then git -C "$APP" pull --ff-only; else git clone "$REPO" "$APP"; fi
# katalog aplikacji: w repo zgłoszenia to korzeń, w monorepo projekty/06-odwolania2json
if [ -d "$APP/projekty/06-odwolania2json" ]; then KAT="$APP/projekty/06-odwolania2json"; else KAT="$APP"; fi
COMPOSE="$KAT/deploy/vm/docker-compose.yml"
systemctl enable --now docker >/dev/null 2>&1 || true      # komenda ma działać po sudo reboot
SOLUTION_DIR=$SOL docker compose -f "$COMPOSE" build         # obraz i zależności pobrane teraz, nie w czasie oceny
sed -e "s#/opt/solution/app/deploy/vm/docker-compose.yml#$COMPOSE#" -e "s#cd /opt/solution #cd $SOL #" \
  "$KAT/deploy/vm/RUN.md" > "$SOL/RUN.md"
[ -f "$SOL/.env" ] || { cp "$KAT/.env.example" "$SOL/.env"; echo "Wpisz LLM_API_KEY w $SOL/.env"; }
chmod 600 "$SOL/.env"
# test: przykładowa sprawa z repo, potem sprzątanie
TEST=$SOL/.test-instalacji   # pod katalogiem rozwiązania: ścieżka widoczna dla demona Dockera
rm -rf "$TEST"
mkdir -p "$TEST/input/test" && cp "$KAT"/tests/kontrolny/input/case06/*.pdf "$TEST/input/test/" 2>/dev/null || true
cp "$SOL/.env" "$TEST/.env"
SOLUTION_DIR=$TEST docker compose -f "$COMPOSE" run --rm odwolania2json | tail -3
echo "Wyniki testu: $(find "$TEST/output" -name '*.json' | wc -l) plików JSON"
rm -rf "$TEST"
echo "Gotowe. Komenda oceny: zob. $SOL/RUN.md"
