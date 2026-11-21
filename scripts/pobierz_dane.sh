#!/usr/bin/env bash
# Pobiera dane treningowe UZP do data/raw/uzp (poza repo, .gitignore).
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -d data/raw/uzp/.git ]; then
  git -C data/raw/uzp pull -q --ff-only
else
  mkdir -p data/raw
  git clone -q --depth 1 https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026 data/raw/uzp
fi
echo "Dane: data/raw/uzp/dane ($(ls data/raw/uzp/dane | wc -l | tr -d ' ') spraw)"
