# Jak dodać nową klasę dokumentu (bez zmiany kodu)

Każda klasa dokumentu to jeden plik `config/klasy/<nazwa>.yaml`. Aplikacja przy starcie wczytuje wszystkie pliki z tego katalogu. Kod nie zna nazw klas ani pól.

Gotowy przykład: `config/klasy-demo/przystapienie.yaml` (zgłoszenie przystąpienia do postępowania odwoławczego). Test `tests/test_nowa_klasa.py` pokazuje, że po skopiowaniu tego pliku do `config/klasy/` aplikacja rozpoznaje nowy typ i zwraca jego JSON.

## Krok po kroku

1. Skopiuj najbliższą istniejącą klasę, np. `cp config/klasy/przelew.yaml config/klasy/nowa.yaml`.
2. Zmień `nazwa` i `opis`.
3. W `rozpoznanie.slowa` wpisz wyrażenia charakterystyczne dla dokumentu i ich wagi. Dokument dostaje klasę o najwyższej sumie wag, jeśli przekracza ona `prog`. Gdy żadna klasa nie przekracza progu, wynikiem jest pusty plik JSON (dokument spoza klas).
4. W `wynik` opisz strukturę JSON. Każde pole końcowe ma listę `metody` (pierwsza, która da wartość, wygrywa) i opcjonalne `normalizuj` oraz `typ`.
5. Uruchom `./run.sh` na katalogu z przykładowymi PDF i obejrzyj wynik w `output/` oraz cytaty w `audit/`, albo wgraj pliki w `./run.sh --web`.
6. Jeśli masz referencyjne JSON-y, zmierz jakość: `python -m odwolania2json.eval --gold <katalog> --pred output`.

## Klocki dostępne w YAML

| Klocek | Do czego | Przykład |
|---|---|---|
| `regex` | wyrażenie regularne; wartość to grupa `v` albo pierwsza grupa; `ktory: 2` = drugie trafienie | `regex: 'KRS[:\s]*(?P<v>\d{10})'` |
| `etykieta` | wartość po etykiecie w tej samej linii (`Kwota: 200 zł`, `KWOTA ..... 200`) albo w następnej | `etykieta: ['kwota(?:\s+operacji)?']` |
| `calosc` | cały tekst sekcji | `calosc: true` + `w: tytul` |
| `slownik` | wybór pozycji ze słownika klasy po wzorcach (najwcześniejsze trafienie wygrywa); `zwroc: id` albo `opis` | powód odwołania 1–11 |
| `jesli` / `to` / `inaczej` | wartość stała zależna od tego, czy wzorzec występuje | `typ: osoba_fizyczna / osoba_prawna` |
| `stala` | wartość stała | `stala: 1` |
| `llm` | pytanie do modelu językowego dla pól, których reguły nie wyciągną (w przygotowaniu) | `llm: 'Podaj imię i nazwisko w mianowniku'` |
| `w` | gdzie szukać: nazwa sekcji albo lista sekcji próbowanych po kolei | `w: [pierwsza_czynnosc, zdanie_czynnosci]` |

**Sekcje** (`sekcje:`) to fragmenty tekstu: `od` (wzorzec początku), `do` (lista wzorców końca), `max_znakow`, `wiele: true` (wszystkie wystąpienia), `globalna: true` (zawsze w całym dokumencie), `z_naglowkiem: true` (z dopasowanym początkiem).

**Listy** (`lista:` + `element:`): elementy z sekcji (`w`), z trafień wyrażenia (`regex`), z podziału (`rozdziel`), z filtrem `wymagaj`, deduplikacją po polu `klucz`, parowaniem z i-tą sekcją (`indeks: true`, np. podpisy i-tego mocodawcy) i `tylko_gdy_wiele` (pole wypełniane tylko, gdy elementów jest więcej niż jeden).

**Normalizatory** (`normalizuj:`): `data_iso`, `kwota`, `cyfry`, `rachunek`, `bzp`, `ted`, `email`, `jedna_linia`, `bez_cudzyslowow`, `bez_kropki`, `bez_tytulu_zawodowego`, `calkowita`.

**Czyszczenie tekstu** (`oczysc:`): wzorce usuwane przed ekstrakcją, np. stopki „Strona 1 z 3”.

## Przejrzystość

Dla każdej wartości aplikacja zapisuje w `audit/<sprawa>/<plik>.json`: pole, wartość, użytą regułę (np. `regex#0`), cytat z dokumentu i numer strony. Te same informacje widać w prototypie WWW obok każdego pola.
