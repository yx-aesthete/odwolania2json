# Jak dodać nową klasę dokumentu (bez zmiany kodu)

Każda klasa dokumentu to jeden plik `config/klasy/<nazwa>.yaml`. Aplikacja przy starcie wczytuje wszystkie pliki z tego katalogu (i z katalogów klas dodatkowych, jeśli je włączono). Kod nie zna nazw klas ani pól.

Gotowy przykład: `config/klasy-demo/przystapienie.yaml` (zgłoszenie przystąpienia do postępowania odwoławczego). Test `tests/test_nowa_klasa.py` pokazuje, że po skopiowaniu tego pliku do `config/klasy/` aplikacja rozpoznaje nowy typ i zwraca jego JSON.

## Klasa w 15 liniach bez regexów

Nowy typ dokumentu można opisać samymi słowami. Przykład: `config/klasy-demo/odpowiedz_na_odwolanie.yaml` (odpowiedź zamawiającego na odwołanie) ma 15 linii treści: nazwę, opis, frazy tytułu i treści w `rozpoznanie` (zwykły tekst, np. `tytul: [odpowiedź na odwołanie]`) oraz `pola` z opisem każdego pola (`sygnatura: sygnatura akt sprawy przed KIO`). Pole może mieć `typ` (`tekst`, `osoba`, `cyfry`, `data`, `kwota`) albo listę `wybor`. Struktura JSON wyniku jest taka jak drzewo `pola`. Aplikacja zamienia frazy na wzorce (dowolne odstępy, litery z ogonkami i bez), pyta model jeden raz o cały dokument, podając opisy pól, i przyjmuje tylko wartości, które naprawdę są w tekście: tekst z podobieństwem co najmniej 0,85, cyfry dokładnie, osoby po rdzeniach członów, daty i kwoty w zapisie z dokumentu, a wartości z `wybor` tylko z listy. Wartość odrzuconą przez walidator zastępuje null. Każde przyjęte pole ma w audycie cytat. Bez modelu klasa nadal rozpoznaje dokument i zwraca strukturę z wartościami null. Kodu nie zmienia się wcale: ta sama aplikacja obsługuje klasy z wyrażeniami regularnymi (`wynik`) i klasy opisowe (`pola`).

Klasy demo są poza zestawem używanym w ocenie i domyślnie wyłączone, więc trzy klasy UZP i dokumenty obce (`{}`) działają bez zmian. Włączenie jednym z trzech sposobów: `--klasy-dodatkowe config/klasy-demo`, zmienna `KLASY_DODATKOWE=config/klasy-demo` albo `klasy_dodatkowe: [config/klasy-demo]` w `config/aplikacja.yaml`. Trzy przykładowe PDF-y z fikcyjnymi danymi i referencje JSON są w `tests/demo_odpowiedz/`:

```bash
python -m odwolania2json --klasy-dodatkowe config/klasy-demo --input tests/demo_odpowiedz/input --output /tmp/demo
python -m odwolania2json.eval --gold tests/demo_odpowiedz/oczekiwane --pred /tmp/demo --scisle
```

## Krok po kroku

1. Skopiuj najbliższą istniejącą klasę, np. `cp config/klasy/przelew.yaml config/klasy/nowa.yaml`.
2. Zmień `nazwa` i `opis`.
3. W `rozpoznanie` wpisz sygnały i ich wagi:
   - `tytul`: wzorce tytułu, sprawdzane na krótkich liniach tytułowych bez spacji i WIELKIMI literami (np. `'PE[ŁL]NOMOCNICTWO': 5` złapie też „P e ł n o m o c n i c t w o”);
   - `slowa`: wyrażenia z treści (pierwsze 10 000 znaków; rozstrzelone litery są scalane);
   - `ujemne` i `tytul_ujemne`: sygnały, że to inny dokument (np. „ODPOWIEDŹ NA ODWOŁANIE”), odejmowane od sumy;
   - `prog`: suma, od której klasa jest pewna.
   Dokument dostaje klasę o najwyższej sumie, jeśli przekracza `prog`. Poniżej progu wygrywa klasa z wyraźną przewagą nad drugą (`config/aplikacja.yaml`, `klasyfikacja.przewaga`), a gdy przewagi nie ma, rozstrzyga model (jeśli włączony). Bez sygnałów dokument jest obcy. Punkty i trafienia każdej klasy są w pliku audytu.
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
| `llm` | pytanie do modelu językowego jako ostatnia metoda pola (tylko gdy reguły nic nie dały); odpowiedź musi stać w tekście dokumentu | `llm: 'Przepisz dosłownie tytuł przelewu …'` |
| `w` | gdzie szukać: nazwa sekcji albo lista sekcji próbowanych po kolei | `w: [pierwsza_czynnosc, zdanie_czynnosci]` |

**Siatka modelu** (metoda `llm` z `siatka: true`, zawsze ostatnia na liście metod pola): model jest pytany tylko wtedy, gdy żadna reguła pola nie dała wartości, a wartość z reguły nigdy nie jest nadpisywana. Klucze metody:
- `kandydaci: '<wzorzec>'`: odpowiedź musi być równa (po normalizatorach pola) jednemu z trafień wzorca w tekście; wartością pola jest zapis z dokumentu (data, kwota, rachunek);
- `sprawdz: doslownie`: odpowiedź musi stać w tekście znak w znak (różnice tylko w odstępach i wielkości liter), bez dopasowania przybliżonego (tytuł przelewu);
- `z_slownika: <słownik>` + `zwroc: id | opis`: pytanie zamknięte, lista „id – opis” jest dopisywana do pytania, odpowiedź to numer pozycji, jej opis albo „numer – opis”; wszystko inne daje brak (powód odwołania).

Odpowiedź BRAK, spoza dokumentu albo spoza listy = null. Dziś siatkę mają: przelew (`data_operacji`, `kwota`, `tytul`, `na_rachunek`; `z_rachunku` i `numer_transakcji` bez pytania) i odwołanie (`czynnosc_powod_id`, `czynnosc_opis`, `czynnosc_dzien`). Wyłączenie całej siatki jedną linijką: `siatka_modelu: false` w `config/aplikacja.yaml` albo zmienna `SIATKA_MODELU=0` (metody zostają w YAML, są pomijane; wynik jak przed ich dodaniem).

**Sekcje** (`sekcje:`) to fragmenty tekstu: `od` (wzorzec początku), `do` (lista wzorców końca), `max_znakow`, `wiele: true` (wszystkie wystąpienia), `globalna: true` (zawsze w całym dokumencie), `z_naglowkiem: true` (z dopasowanym początkiem).

**Listy** (`lista:` + `element:`): elementy z sekcji (`w`), z trafień wyrażenia (`regex`), z podziału (`rozdziel`), z filtrem `wymagaj`, deduplikacją po polu `klucz`, parowaniem z i-tą sekcją (`indeks: true`, np. podpisy i-tego mocodawcy) i `tylko_gdy_wiele` (pole wypełniane tylko, gdy elementów jest więcej niż jeden). Gdy ta sama lista bywa zapisana w różnych układach, `lista.warianty` podaje kilka sposobów jej znalezienia (każdy wariant ma własne `w`, `regex`, `flagi`, `indeks`…; klucze spoza wariantu są wspólne): wygrywa pierwszy wariant, który daje elementy, np. podpisujący najpierw z klauzuli „reprezentowana przez: …” w opisie mocodawcy, a dopiero potem z bloku podpisów.

**Wskazanie zdaniem w treści** (`wskazanie:` na poziomie klasy): lista `{lista, pole_nazwy, pole, regex z grupą v, wartosc, inaczej}`; gdy lista ma ≥2 elementy, a nazwa z trafienia pasuje początkiem do dokładnie jednego elementu, ten dostaje `wartosc` (domyślnie 1), pozostałe `inaczej` (0). Np. zamawiający prowadzący postępowanie wskazany zdaniem w uzasadnieniu.

**Normalizatory** (`normalizuj:`): `data_iso`, `kwota`, `cyfry`, `rachunek`, `bzp`, `ted`, `email`, `jedna_linia`, `bez_cudzyslowow`, `bez_kropki`, `bez_tytulu_zawodowego`, `calkowita`, `forma_prawna` (forma prawna przekręcona przez OCR: „Sp. z 0.0.” → „Sp. z o.o.”, „spółkaakcyjna” → „spółka akcyjna”).

**Czyszczenie tekstu** (`oczysc:`): wzorce usuwane przed ekstrakcją, np. stopki „Strona 1 z 3”.

## Przejrzystość

Dla każdej wartości aplikacja zapisuje w `audit/<sprawa>/<plik>.json`: pole, wartość, użytą regułę (np. `regex#0`), cytat z dokumentu i numer strony. Te same informacje widać w prototypie WWW obok każdego pola.


## Zasada: dowód pozytywny (Z37)

Dokument dostaje klasę tylko wtedy, gdy ma minimalny zestaw cech tej klasy; domyślnie jest `{}`. Zestaw podaje się w `rozpoznanie.wymagane` jako listę grup, a każda grupa to lista alternatyw (wystarczy jedno trafienie w grupie, ale trafić muszą wszystkie grupy). Bez kompletu klasa odpada: nie wygrywa punktami ani przy remisie, a model przy niskiej pewności nie może jej przywrócić. Przykład z `przelew.yaml`: kwota + data operacji + rachunek 26 cyfr + etykieta operacji (tytuł, odbiorca, nadawca…). Odporność na szum OCR: `wymagane_min: N` (wystarczy N grup), `wymagane_z_tytulem: {wzorzec, min}` (przy tytule klasy w strefie tytułu wystarczy mniej grup) i `wymagane_wyklucz_bez_kompletu` (wzorce, które blokują klasę, gdy brakuje choć jednej grupy, np. faktura albo „do zapłaty” dla przelewu). Sygnały ujemne (`ujemne`, `tytul_ujemne`) zostają jako dodatkowy hamulec, nie główny mechanizm. Wymienione w zleceniach typy pism obcych (odpis KRS, broszura, SWZ…) to przykłady: zestaw ma opisywać cechy klasy, a nie listę wyjątków.
