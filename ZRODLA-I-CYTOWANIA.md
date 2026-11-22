# Źródła, cytowania i licencje

Wymóg HackNation (FAQ, pyt. 11): wcześniej ukończone lub zewnętrzne zasoby, narzędzia i repozytoria trzeba rzetelnie wymienić. Kod aplikacji napisano od zera podczas hackathonu.

## Biblioteki w działającym rozwiązaniu

| Co | Skąd | Licencja | Do czego użyte |
|---|---|---|---|
| pypdf 7.1.1 | https://github.com/py-pdf/pypdf | BSD-3-Clause | tekst z PDF |
| PyYAML 6.0.4 | https://github.com/yaml/pyyaml | MIT | konfiguracja klas dokumentów |
| RapidFuzz 3.14.6 | https://github.com/rapidfuzz/RapidFuzz | MIT | podobieństwo napisów w ewaluatorze (próg 0,8 wg UZP) i sprawdzanie odpowiedzi modelu w tekście |
| pypdfium2 5.15.2 (PDFium) | https://github.com/pypdfium2-team/pypdfium2 | Apache-2.0 / BSD-3-Clause | zapasowy odczyt tekstu stron, renderowanie skanu do OCR |
| Pillow 13.0.0 | https://github.com/python-pillow/Pillow | MIT-CMU (HPND) | obraz strony przed OCR |
| Tesseract OCR + model `pol` (tessdata_fast) | https://github.com/tesseract-ocr/tesseract | Apache-2.0 | zapasowy OCR stron bez warstwy tekstowej (opcjonalny; w obrazie Dockera) |
| FastAPI 0.165.0 | https://github.com/fastapi/fastapi | MIT | prototyp WWW |
| Uvicorn 0.54.0 | https://github.com/encode/uvicorn | BSD-3-Clause | serwer prototypu |
| python-multipart 0.0.34 | https://github.com/Kludex/python-multipart | Apache-2.0 | wgrywanie plików |
| pytest 9.2.0, httpx 0.28.1 | https://github.com/pytest-dev/pytest, https://github.com/encode/httpx | MIT, BSD-3-Clause | testy |

## Modele / API w działającym rozwiązaniu

- **Gemma 4 26B-A4B Instruct** (`google/gemma-4-26B-A4B-it`, https://hf.co/google/gemma-4-26B-A4B-it), Google, licencja Apache-2.0, otwarte wagi — model domyślny (ekstrakcja oraz OCR stron bez warstwy tekstowej — wejście obrazowe), wywoływany przez Scaleway Generative APIs (Scaleway SAS, Francja, region Paryż).
- Qwen3.8-27B (`Qwen/Qwen3.8-27B`, https://hf.co/Qwen/Qwen3.8-27B), Alibaba Cloud / Qwen, Apache-2.0 — model zapasowy.
- W porównaniu (bez użycia w produkcie): qwen3.6-35b-a3b, mistral-small-3.2-24b-instruct-2506, gpt-oss-120b, qwen3-235b-a22b-instruct-2507, qwen3.5-397b-a17b (wszystkie Apache-2.0) przez Scaleway; Qwen2.5-7B-Instruct (Apache-2.0) przez Ollama (MIT) lokalnie do testów adaptera.

## Dane

- Dane treningowe, wzorce JSON i szablon aplikacji: repozytorium Urzędu Zamówień Publicznych https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026 (`dane/`, `oczekiwane-json/`, `szablon-aplikacja/`). Nie są kopiowane do repo; `scripts/pobierz_dane.sh` pobiera je lokalnie.
- Definicja F1 (TP/FP/FN/TN, próg podobieństwa 0,8 dla długich napisów): komunikat organizatora na Discordzie HackNation, 21.11.2026.

## Narzędzia użyte do wytwarzania kodu

- Asystent programisty oparty na modelu językowym, pod nadzorem autora (pisanie i przegląd kodu, testów i dokumentacji). Nie jest częścią działającego rozwiązania.
