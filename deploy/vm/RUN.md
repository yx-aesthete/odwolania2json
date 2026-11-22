# Uruchomienie oceny (Odwołania2json, zadanie 06 UZP)

Jedna komenda, z katalogu `/opt/solution` (nie pyta o nic, sama się kończy):

```bash
cd /opt/solution && docker compose -f /opt/solution/app/deploy/vm/docker-compose.yml run --rm odwolania2json
```

- **Wejście:** `/opt/solution/input` — pliki PDF płasko (`input/*.pdf`) albo w podkatalogach spraw (`input/caseN/*.pdf`).
- **Wynik:** `/opt/solution/output` — dla każdego PDF plik JSON o tej samej nazwie i w tym samym podkatalogu. Dokument spoza trzech typów (odwołanie, pełnomocnictwo, potwierdzenie przelewu) dostaje `{}`. Pliki mają właściciela root (kontener).
- **Audyt** (cytat i strona źródła każdego pola): `/opt/solution/audit`.
- **Czas:** pliki przetwarzane równolegle; budżet przebiegu 35 min (`MAKS_CZAS_S=2100`), po nim reszta samymi regułami, a pliki wynikowe i tak powstają.
- **Po czym poznać, że model działał:** ostatnia linia logu `Podsumowanie: model …: N wywołań, 0 błędów, 0 dokumentów bez modelu; OCR: … stron`.

## Usługi zewnętrzne

- **Scaleway Generative APIs** (Francja, region Paryż, API zgodne z OpenAI, `https://api.scaleway.ai/v1`, port 443). Klucz w `/opt/solution/.env` (`LLM_API_KEY`).
- Modele z otwartymi wagami (Apache-2.0): **Gemma 4 26B-A4B** (`gemma-4-26b-a4b-it`) — ekstrakcja i klasyfikacja przy niskiej pewności; **Mistral Small 3.2 24B** (`mistral-small-3.2-24b-instruct-2506`) — OCR stron bez warstwy tekstowej (zapas: Gemma).
- **Bez klucza albo bez sieci:** działają same reguły (PDF z warstwą tekstową normalnie; skany bez OCR dostają `{}`), w logu `MODEL WYŁĄCZONY: …` albo „brak (same reguły)”. Program kończy się normalnie.
