#!/usr/bin/env bash
# Pobiera model języka polskiego dla Tesseracta (tessdata_fast, Apache-2.0) do .cache/tessdata.
# Potrzebny tylko dla skanów (stron bez warstwy tekstowej). Sam Tesseract: brew install tesseract / apt install tesseract-ocr.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p .cache/tessdata
for L in pol; do
  [ -s ".cache/tessdata/$L.traineddata" ] && continue
  curl -fsSL -o ".cache/tessdata/$L.traineddata" "https://github.com/tesseract-ocr/tessdata_fast/raw/main/$L.traineddata"
done
echo "OCR: modele w .cache/tessdata ($(ls .cache/tessdata | tr '\n' ' '))"
