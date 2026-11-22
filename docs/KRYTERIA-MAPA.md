# Mapa: kryterium → dowód

Kryteria z regulaminu i README zadania UZP. Każdy dowód da się sprawdzić w repo w ≤ 3 minuty.

## Etap 1 (preselekcja)

| Kryterium | Waga | Co pokazujemy | Gdzie juror to zobaczy | Stan |
|---|---|---|---|---|
| F1 na ukrytym zbiorze testowym (≥ 10 realnych spraw) | 100% | Ekstrakcja regułami z YAML + model gemma-4-26b-a4b-it; pomiar F1 wg definicji UZP (TP/FP/FN, 5 pól długich ≥ 80%) | Zbiór ukryty testera (U3, bez wglądu w reguły): **0,92**; przypadki brzegowe K5: **1,000** (przed poprawkami 0,870); K4: 0,998; skany UZP (30 dok., OCR po API): 0,984 na sprawach strojonych / **0,970** na nieoglądanych; trening UZP: 1,000 (reguły strojone na tym zbiorze, więc to nie jest miara uogólnienia) — `docs/WYNIKI.md`, `docs/STAN.md`, `scripts/mierz.sh` | ☑ zbiory niezależne; test UZP nieznany |

## Etap 2 (finał)

| Kryterium | Waga | Co pokazujemy | Gdzie juror to zobaczy | Stan |
|---|---|---|---|---|
| F1 | 50% | jak wyżej (0,92 na ukrytym zbiorze testera, 0,970 na nieoglądanych skanach UZP) | `docs/WYNIKI.md` | ☑ zbiór niezależny; test nieznany |
| Moc modelu (im mniejszy, tym więcej) | 1–20 pkt | Reguły robią całość pól na danych UZP; model językowy jest opcjonalny i woła się tylko dla pól oznaczonych `llm:` w YAML. Bez modelu aplikacja działa w pełni | `README.md` („Jak to działa”), `src/odwolania2json/llm.py`, przełącznik `--bez-llm` | ☑ Gemma 4 26B-A4B (26 mld, MoE) do ekstrakcji, wybrana z 7; Mistral Small 3.2 24B do OCR skanów (najwyższe F1) |
| Nowe klasy bez przebudowy | 1–20 pkt | Klasa = jeden plik YAML (słowa kluczowe z wagami, sekcje, reguły pól). Czwarta klasa (zgłoszenie przystąpienia) dodana bez zmiany kodu | `config/klasy/*.yaml`, `config/klasy-demo/przystapienie.yaml`, `docs/NOWA-KLASA.md`, test `tests/test_nowa_klasa.py` | ☑ |
| Inne funkcje (np. GUI) | 1–10 pkt | Strona WWW: wgranie PDF, rozpoznany typ, JSON, cytat ze źródła i strona przy każdym polu; audyt każdej wartości w `./audit/`; OCR skanów | `./run.sh --web`, `docs/podglad-rozpoznana.png`, `docs/podglad-obcy.png`, `audit/<sprawa>/<plik>.json` | ☑ |

## Wymagania techniczne (README UZP)

| Wymaganie | Dowód | Stan |
|---|---|---|
| Tylko open source, model otwarty | `requirements.txt` (wersje przypięte), `ZRODLA-I-CYTOWANIA.md` | ☑ |
| Bez GPU, 16 GB RAM, LLM tylko po API z UE/EOG | Reguły + Tesseract na CPU; LLM przez `LLM_BASE_URL`/`LLM_MODEL` z `.env` | ☑ |
| Foldery `input/` i `output/` w katalogu głównym, wynik o tej samej nazwie | `input/`, `output/`, `run.sh`, test `tests/test_e2e.py` | ☑ |
| Dokument spoza klas → plik `.json` z `{}` | `negatywny przyklad.pdf` w teście e2e | ☑ |
| CLI / skrypt startowy | `run.sh`, `start.bat`, `run.bat`, `python -m odwolania2json` (każdy czyta `.env`) | ☑ |
| Prototyp: wgranie i odczyt wyniku | `./run.sh --web` | ☑ |
| Docker Compose | `docker-compose.yml`: `docker compose run --rm odwolania2json`, `docker compose up web` | ☑ |
| Dokumentacja: architektura, dodawanie klasy, użyty LLM | `README.md` (sekcja „Model językowy”), `docs/NOWA-KLASA.md`, `docs/WYNIKI.md` | ☑ |
| Transparentność ekstrakcji | cytat, strona i reguła przy każdym polu (`audit/`, GUI) | ☑ |

Zasada: każde kryterium ma dowód widoczny w ≤ 3 minuty czytania zgłoszenia.
