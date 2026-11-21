# Źródła, cytowania i licencje

Wymóg HackNation (FAQ, pyt. 11): wcześniej ukończone lub zewnętrzne zasoby, narzędzia i repozytoria trzeba rzetelnie wymienić. Kod aplikacji napisano od zera podczas hackathonu.

## Biblioteki w działającym rozwiązaniu

| Co | Skąd | Licencja | Do czego użyte |
|---|---|---|---|
| pypdf 7.1.1 | https://github.com/py-pdf/pypdf | BSD-3-Clause | tekst z PDF |
| PyYAML 6.0.4 | https://github.com/yaml/pyyaml | MIT | konfiguracja klas dokumentów |
| RapidFuzz 3.14.6 | https://github.com/rapidfuzz/RapidFuzz | MIT | podobieństwo napisów w ewaluatorze (próg 0,8 wg UZP) |
| FastAPI 0.165.0 | https://github.com/fastapi/fastapi | MIT | prototyp WWW |
| Uvicorn 0.54.0 | https://github.com/encode/uvicorn | BSD-3-Clause | serwer prototypu |
| python-multipart 0.0.34 | https://github.com/Kludex/python-multipart | Apache-2.0 | wgrywanie plików |
| pytest 9.2.0, httpx 0.28.1 | https://github.com/pytest-dev/pytest, https://github.com/encode/httpx | MIT, BSD-3-Clause | testy |

## Modele / API w działającym rozwiązaniu

- Obecna wersja działa na samych regułach z plików YAML, bez modelu językowego. Warstwa modelu otwartego (open-weights, przez API zgodne z OpenAI, dostawca z UE/EOG) jest w przygotowaniu i zostanie tu opisana z nazwą i licencją modelu.

## Dane

- Dane treningowe, wzorce JSON i szablon aplikacji: repozytorium Urzędu Zamówień Publicznych https://github.com/Urzad-Zamowien-Publicznych/hacknation-2026 (`dane/`, `oczekiwane-json/`, `szablon-aplikacja/`). Nie są kopiowane do repo; `scripts/pobierz_dane.sh` pobiera je lokalnie.
- Definicja F1 (TP/FP/FN/TN, próg podobieństwa 0,8 dla długich napisów): komunikat organizatora na Discordzie HackNation, 21.11.2026.

## Narzędzia użyte do wytwarzania kodu

- Przy tworzeniu korzystano ze standardowych narzędzi programistycznych (edytor kodu, system kontroli wersji, narzędzia wspomagające pisanie i testowanie kodu). Cały kod został przejrzany i przetestowany przez autora.
- Tesseract OCR (Apache-2.0) z modelem `pol` z tessdata_fast — użyty ręcznie do odczytania zeskanowanego przykładu UZP podczas testów odporności (w produkcie na razie nie).
