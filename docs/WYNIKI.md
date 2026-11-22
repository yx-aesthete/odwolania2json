# Wyniki F1 (60 spraw treningowych UZP, same reguły, bez modelu)

Pomiar: `PYTHONPATH=src python -m odwolania2json.eval --pred <output> --scisle --md docs/WYNIKI.md`.
Uwaga: reguły pisane na tych samych 60 sprawach — to wynik na zbiorze uczącym, nie prognoza dla testu.

## Porównanie modeli i wyniki końcowe (wersja zamrożona cb86e0d, 22.11)

### Nazwy zbiorów (te same w README, WYNIKI, pitchu i na slajdach)

| Nazwa | Co to jest |
|---|---|
| **niezależny A, styl UZP** | zbiór z linii „Dowód” w README, przygotowany bez wglądu w reguły |
| **niezależny B, 100 PDF, styl UZP** | nowy zbiór do porównania modeli |
| **niezależny C, ze skanami, 88 PDF** | w tym 28 skanów |
| **pisma kancelarii** | pisma w stylu kancelarii, inny układ niż dane UZP |
| **nietypowe układy** | dokumenty bez etykiet i w nietypowym układzie |
| **skany UZP nieoglądane** | skany UZP, których nie oglądaliśmy przy strojeniu |
| **kontrolny z pełnomocnictwami** | zbiór kontrolny skupiony na pełnomocnictwach |
| **trening UZP** | 60 spraw treningowych UZP, na nich powstały reguły |

### Główne liczby (z modelem) i co, jeśli model ekstrakcji nie działa

Pomiar testera: OCR modelem działa, model ekstrakcji wyłączony, dwa przebiegi z identycznym wynikiem.

| Zbiór | z modelem | bez modelu ekstrakcji | różnica |
|---|---|---|---|
| niezależny A, styl UZP | 0,997 | 0,991 | −0,006 |
| pisma kancelarii | 0,978 | 0,900 | −0,078 |
| nietypowe układy | 0,922 | 0,695 | −0,227 |
| skany UZP nieoglądane | 0,988 | 0,964 | −0,024 |

Program dalej oddaje wynik dla każdego pliku. Na dokumentach w stylu UZP strata jest mała, a najwięcej model daje na nietypowych układach.

Czas: 150 PDF w 4,5–5,5 min; przy serwerze spowolnionym o 20 s na zapytanie 19 min, przy limitach dostawcy (429) 21 min (limit UZP 45 min). Zawsze wszystkie pliki.

### Porównanie modeli ekstrakcji

Pomiar porównawczy u dostawcy testowego (nie w zgłoszeniu; zgłoszenie idzie przez dostawcę z UE), 21/22.11, kod `b1e0630`, jeden przebieg. OCR w każdym wariancie ten sam (Mistral Small 3.2 24B), zmienia się tylko model ekstrakcji. F1 ściśle według definicji UZP, pole po polu. „—” = nie mierzono. To osobny przebieg, więc liczby różnią się o tysięczne od głównych.

| Zbiór | same reguły | Gemma 26B | Mistral 24B | Qwen 3.5 9B | Ministral 3 14B | Ministral 3 8B | Ministral 3 3B |
|---|---|---|---|---|---|---|---|
| niezależny B, 100 PDF, styl UZP | 0,960 | **0,970** | 0,969 | 0,966 | 0,962 | 0,963 | 0,963 |
| niezależny C, ze skanami, 88 PDF | — | 0,967 | — | **0,969** | 0,963 | 0,967 | 0,959 |
| pisma kancelarii | 0,900 | **0,959** | 0,955 | 0,957 | — | — | 0,931 |
| nietypowe układy | 0,695 | 0,878 | **0,880** | 0,872 | — | — | 0,876 |
| kontrolny z pełnomocnictwami | — | **1,000** | 0,995 | 0,987 | — | — | 0,987 |
| trening UZP | **1,000** | **1,000** | 0,9995 | 0,998 | — | — | 0,992 |

### Co z tego wynika

1. **Większość pracy robią reguły z plików YAML.** Bez modelu: 0,991 na zbiorze niezależny A, 0,960 na zbiorze niezależny B (100 PDF) i 1,000 na treningu UZP. Model dokłada ok. 0,01 w dokumentach w stylu UZP i od 0,08 do 0,23 w pismach kancelarii i nietypowych układach.
2. **Działa nawet z bardzo małym modelem.** Model 3 mld parametrów trzyma od 0,88 do 0,99 (na nietypowych układach 0,88, tyle co Gemma). Qwen 9B jest średnio ok. 0,005 F1 za Gemmą.
3. **Małe modele tracą głównie na pełnomocnictwach:** nazwa i typ mocodawcy oraz osoby podpisujące.
4. **Model zmienia się jedną linią w `.env`** (`LLM_MODEL`), bez zmian w kodzie. UZP może sam uruchomić mniejszy wariant.
5. **Gemma daje najwyższe albo prawie najwyższe F1 w każdym zbiorze**, dlatego ją zgłaszamy.


## Podsumowanie (same reguły, F1 ścisły wg definicji UZP)

| Zbiór | F1 | Uwagi |
|---|---|---|
| 60 spraw treningowych UZP + 16 dokumentów obcych | 1,0000 | reguły pisane na tych danych |
| zbiór kontrolny: 12 spraw w innych układach, 38 dokumentów (`tests/kontrolny/`) | 0,9949 | na starcie 0,8683; poprawki ogólne, nie pod konkretną sprawę |
| 57 zaburzeń tekstu treningowego (`scripts/kontrolny.py`, `docs/KONTROLNY.md`) | najgorsze 0,987 | inne etykiety, formaty dat, kwot, identyfikatorów, złamane linie |

Pomiar jedną komendą: `scripts/mierz.sh` (trening + kontrolny).

## Skany (dane UZP `dane/skany`, dokumenty bez warstwy tekstowej)

10 spraw w układzie prawdziwych pism (odwołania 4–7 stron, pełnomocnictwa, wydruki bankowe), tylko obraz. Bez OCR każdy dokument daje `{}` (F1 = 0). Strojone na sprawach 0001–0007; 0008–0010 mierzone niezależnie.

| Wariant (sprawy 0001–0007) | Odwołania | Pełnomocnictwa | Potwierdzenia |
|---|---|---|---|
| Tesseract (pol) + reguły sprzed dostrojenia | 0,713 | 0,683 | 0,744 |
| OCR modelem Gemma 4 26B-A4B + reguły sprzed dostrojenia | 0,825 | 0,736 | 0,787 |
| OCR modelem Gemma + reguły dostrojone (pełny przebieg, 391 s / 21 dok.) | 0,960 | 0,964 | 0,914* |
| OCR modelem Gemma + reguły dostrojone (ten sam tekst OCR, wersja końcowa) | 0,956 | 0,964 | 0,959 |
| OCR modelem Mistral Small 3.2 + reguły dostrojone | 0,980 | 0,955 | 0,959 |
| czyste transkrypcje (górna granica reguł) | 1,000 | 0,982 | 1,000 |

\* przed ostatnią poprawką wydruków bankowych.

### Pełny przebieg na wszystkich 30 skanach (wersja z 21.11, ok. 18:20; ekstrakcja Gemma, różne modele OCR)

Sprawy 0001–0007 posłużyły do strojenia reguł; 0008–0010 nie były oglądane (miara przenoszenia na nowe sprawy).

| Model OCR | 0001–0007 | 0008–0010 (nietknięte) | czas 30 dok. |
|---|---|---|---|
| **Mistral Small 3.2 24B** | **0,984** | **0,940** | 452 s |
| Gemma 4 26B-A4B | 0,972 | 0,907 | 193 s |
| lightonocr 0,8B → zapas Mistral | 0,968 | 0,886 | 277 s |

Po Z29 (pełnomocnictwo: podpisujący z klauzuli reprezentacji, pełnomocnicy z wyliczenia; 21.11, ok. 19:30):

| Model OCR | 0001–0007 | 0008–0010 (nietknięte) | pełnomocnictwa 0008–0010 |
|---|---|---|---|
| **Mistral Small 3.2 24B** | **0,984** | **0,965** | 0,955 (było 0,850) |
| Gemma 4 26B-A4B | 0,972 | 0,940 | 0,930 (było 0,757) |

## Przypadki brzegowe K5 — przed i po (Z31, 21.11)

Zbiór niezależnego autora: 11 spraw, 22 dokumenty, każdy sprawdza 1–2 pułapki (`zadania/06-odwolania2json/kontrolny5-brzegowe/`). Pomiar jak u UZP (`scripts/mierz_k5.sh`: OCR Mistral Small, ekstrakcja Gemma), tryb ścisły.

| | Ogółem | Odwołanie | Pełnomocnictwo | Przelew |
|---|---|---|---|---|
| przed (dev/06 21.11 ok. 19:30) | 0,870 | 0,898 | 0,750 | 0,714 |
| **po** | **1,000** | **1,000** | **1,000** | **1,000** |

Co zmieniło wynik (reguły ogólne, bez wartości z K5; każda z testem na innych danych):

| Pułapka | Rozwiązanie |
|---|---|
| polskie znaki rozbite w warstwie tekstowej („a˛”, „S´”), ligatury „ﬁ” | NFKC i sklejanie liter; strona z rozbitymi znakami także przez OCR (litera „ł” rysowana kreską nie ma znaku w tekście) |
| skan do góry nogami | strona 1 z OCR bez nagłówka → próba po obrocie o 180° |
| wydruk kolumnowy z banku (etykiety pod sobą, wartości niżej, rachunki łamane) | reguły kolumnowe; data operacji przed datą zlecenia |
| czynność w „Zarzut nr 1”, inna niż w tytule pisma | zwięzły zarzut „naruszenia art. … przez …” wskazuje czynność |
| nazwiska w celowniku i bierniku z obocznością (Gołębia, Dęba, Kozła) | odmiana ę→ą i wyjątki w `config/odmiana.yaml` |
| KRS bez zer, REGON i e-mail złamane między liniami, NIP z „PL” | normalizatory `krs`, `regon`, `email` |
| reprezentacja przez organ (prezes, komplementariusz) | to nie pełnomocnik: `przez-pelnomocnika` = 0 |
| lider konsorcjum wymieniony jako drugi, „w imieniu X oraz Y” | sekcja lidera z numerem pozycji i dopiskiem |
| data przy podpisie na końcu pisma, data słownie w nagłówku | data tylko z nagłówka; liczebniki porządkowe |
| nazwa z adresem w tej samej linii, „pod firmą X” | koniec nazwy na „, ul. …”; nazwa firmy przedsiębiorcy |

Ostatnie dwa przypadki: nazwy złamane w układzie dwukolumnowym (case10) i prowadzący postępowanie wskazany tylko zdaniem w uzasadnieniu (klocek `wskazanie`, case7). Na samych regułach, bez modelu i bez OCR, K5 ma 0,910. Bez regresji: trening, K1, K3 1,000; K4 0,998; 57 zaburzeń; 30 skanów UZP 0,984 / 0,970.

## Zasady oceny (UZP, Discord 21.11)

- Pola porównywane z progiem podobieństwa 80%: `Odwolujacy[].pelnomocnik.nazwa`, `przelew_bankowy.tytul`, `Odwolujacy[].nazwa`, `Zamawiajacy[].nazwa`, `ZamowieniePubliczne.tytul` (`config/ewaluacja.yaml`). Wszystkie inne dokładnie, także `czynnosc_opis` i `mocodawca[].data.nazwa`.
- Listy dopasowywane po treści (kolejność nie gra roli).
- Dokument obcy: plik `<nazwa>.json` z zawartością `{}`; po stronie referencji `{}` i plik 0 B liczą się tak samo.

Opisy `czynnosc_opis` (wpisywane dosłownie): słownik `oczekiwane-json/czynnosc_powod_id_dict.md` vs referencje w `dane/`:

| Kod | Słownik UZP | `dane/` | Wpisujemy |
|---|---|---|---|
| 6 | Odpowiedzi/wyjaśnienia do SWZ | Odpowiedzi i wyjaśnienia do SWZ (5×) | jak w `dane/` |
| 11 | „Opis przedmiotu zamówienia (OPZ) ” (spacja na końcu) | Opis przedmiotu zamówienia (OPZ) (5×) | jak w `dane/` |
| 12 | Projektowane postanowienia umowy | brak w `dane/` | jak w słowniku |
| 1–5, 7–10 | identycznie | identycznie | — |

## Warianty modelu (Z5)

Model uzupełnia tylko pola, których reguły nie wyciągnęły, i wskazuje blok strony, gdy brak etykiety. Na treningu i zbiorze kontrolnym reguły robią prawie wszystko (model wołany 2–3 razy), więc modele porównujemy na **teście kotwicy z modelu** (zestaw sztuczny, nie prognoza dla UZP — odwołania UZP mają etykiety stron): 72 odwołania (60 treningowych + 12 kontrolnych) z usuniętymi etykietami stron („Odwołujący:”, „Zamawiający:” i synonimy) — `scripts/trudny.py`. Wszystkie modele przez Scaleway Generative APIs (UE), `reasoning_effort: none` (gpt-oss: `low`), temperatura 0.

| Wariant | Licencja | Parametry (aktywne) | Trening | Kontrolny | Test kotwicy |
|---|---|---|---|---|---|
| same reguły | — | — | 1,0000 | 0,9949 | 0,7397 |
| **reguły + gemma-4-26b-a4b-it** (wybrany) | Apache-2.0 | 26 mld (MoE) | 1,0000 | 0,9974 | **0,9498** |
| reguły + qwen3.8-27b | Apache-2.0 | 27 mld | 1,0000 | 0,9974 | 0,9589 |
| reguły + qwen3.6-35b-a3b | Apache-2.0 | 35 mld (3 mld) | 1,0000 | 0,9974 | 0,9134 |
| reguły + mistral-small-3.2-24b-instruct-2506 | Apache-2.0 | 24 mld | 1,0000 | 0,9961 | 0,9090 |
| reguły + gpt-oss-120b | Apache-2.0 | 117 mld (5 mld) | 1,0000 | 0,9974 | 0,9019 |
| reguły + qwen3-235b-a22b-instruct-2507 | Apache-2.0 | 235 mld (22 mld) | 1,0000 | 0,9974 | 0,9110 |
| reguły + qwen3.5-397b-a17b | Apache-2.0 | 397 mld (17 mld) | 1,0000 | 0,9974 | 0,9198 |

Wiersze Gemmy i Qwen3.8 po ostatniej poprawce reguł (etykieta zamawiającego nie łapie zdań z treści); pozostałe modele zmierzone wersję wcześniej (−0,005 do −0,01).

Pomiar na niewidzianym zbiorze testowym (wykonany niezależnie): same reguły 0,649 → z Gemmą 0,776 (dokumenty w stylu UZP 0,853 w obu wariantach — model nie szkodzi; dokumenty w innym stylu 0,476 → 0,721); Gemma i Qwen3.8 dały tam identyczny wynik.

OCR: Mistral Small 3.2 24B (najwyższe F1 na skanach), zapas Gemma; ekstrakcja: Gemma 4 26B-A4B (decyzja Michała po rozmowie z mentorem UZP: F1 najważniejsze).

Reguła wyboru: najwyższe F1, a gdy mniejszy model traci mniej niż 0,01 do lepszego, bierzemy mniejszy. Gemma 4 26B-A4B (26 mld) traci 0,009 do Qwen3.8-27B (27 mld) i jest najmniejsza z porównywanych bez straty jakości, więc jest modelem domyślnym; Qwen3.8-27B jest zapasowy (`LLM_MODEL` w `.env`). Większe modele nie dają zysku. Bez klucza API aplikacja działa na samych regułach.

Lokalny serwer (Ollama, qwen2.5:7b, komputer bez GPU) służył tylko do testów adaptera: za słaby na wskazanie bloku strony.

Tryb ścisły; drugi tryb F1 = 1.0000

**F1 ogółem: 1.0000** (TP 2032, FP 0, FN 0, TN 284)

| Typ | F1 | TP | FP | FN |
|---|---|---|---|---|
| odwolanie | 1.0000 | 1214 | 0 | 0 |
| pelnomocnictwo | 1.0000 | 458 | 0 | 0 |
| przelew | 1.0000 | 360 | 0 | 0 |

| Pole | F1 | TP | FP | FN | TN |
|---|---|---|---|---|---|
| `odwolanie:OdwolanieKIO.czynnosc_dzien` | 1.000 | 60 | 0 | 0 | 0 |
| `odwolanie:OdwolanieKIO.czynnosc_opis` | 1.000 | 60 | 0 | 0 | 0 |
| `odwolanie:OdwolanieKIO.czynnosc_powod_id` | 1.000 | 60 | 0 | 0 | 0 |
| `odwolanie:OdwolanieKIO.data` | 1.000 | 45 | 0 | 0 | 15 |
| `odwolanie:OdwolanieKIO.miejscowosc` | 1.000 | 45 | 0 | 0 | 15 |
| `odwolanie:Odwolujacy[].krs` | 1.000 | 56 | 0 | 0 | 4 |
| `odwolanie:Odwolujacy[].nazwa` | 1.000 | 60 | 0 | 0 | 0 |
| `odwolanie:Odwolujacy[].nip` | 1.000 | 60 | 0 | 0 | 0 |
| `odwolanie:Odwolujacy[].pelnomocnik.imie_nazwisko` | 1.000 | 60 | 0 | 0 | 0 |
| `odwolanie:Odwolujacy[].pelnomocnik.mail` | 1.000 | 60 | 0 | 0 | 0 |
| `odwolanie:Odwolujacy[].pelnomocnik.nazwa` | 1.000 | 60 | 0 | 0 | 0 |
| `odwolanie:Odwolujacy[].przez-pelnomocnika` | 1.000 | 60 | 0 | 0 | 0 |
| `odwolanie:Odwolujacy[].regon` | 1.000 | 60 | 0 | 0 | 0 |
| `odwolanie:Zamawiajacy[].krs` | 1.000 | 58 | 0 | 0 | 5 |
| `odwolanie:Zamawiajacy[].nazwa` | 1.000 | 63 | 0 | 0 | 0 |
| `odwolanie:Zamawiajacy[].nip` | 1.000 | 63 | 0 | 0 | 0 |
| `odwolanie:Zamawiajacy[].prowadzacy_postepowanie` | 1.000 | 6 | 0 | 0 | 57 |
| `odwolanie:Zamawiajacy[].regon` | 1.000 | 63 | 0 | 0 | 0 |
| `odwolanie:ZamowieniePubliczne.numer_bzp` | 1.000 | 48 | 0 | 0 | 12 |
| `odwolanie:ZamowieniePubliczne.numer_postepowania` | 1.000 | 60 | 0 | 0 | 0 |
| `odwolanie:ZamowieniePubliczne.numer_ted` | 1.000 | 47 | 0 | 0 | 13 |
| `odwolanie:ZamowieniePubliczne.tytul` | 1.000 | 60 | 0 | 0 | 0 |
| `pelnomocnictwo:mocodawca[].data.imie_nazwisko` | 1.000 | 4 | 0 | 0 | 62 |
| `pelnomocnictwo:mocodawca[].data.krs` | 1.000 | 62 | 0 | 0 | 4 |
| `pelnomocnictwo:mocodawca[].data.nazwa` | 1.000 | 66 | 0 | 0 | 0 |
| `pelnomocnictwo:mocodawca[].data.nip` | 1.000 | 66 | 0 | 0 | 0 |
| `pelnomocnictwo:mocodawca[].data.typ` | 1.000 | 66 | 0 | 0 | 0 |
| `pelnomocnictwo:mocodawca[].podpisujacy[].imie_nazwisko` | 1.000 | 95 | 0 | 0 | 0 |
| `pelnomocnictwo:pelnomocnicy[].imie_nazwisko` | 1.000 | 98 | 0 | 0 | 0 |
| `pelnomocnictwo:pelnomocnicy[].pesel` | 1.000 | 1 | 0 | 0 | 97 |
| `przelew:przelew_bankowy.data_operacji` | 1.000 | 60 | 0 | 0 | 0 |
| `przelew:przelew_bankowy.kwota` | 1.000 | 60 | 0 | 0 | 0 |
| `przelew:przelew_bankowy.na_rachunek` | 1.000 | 60 | 0 | 0 | 0 |
| `przelew:przelew_bankowy.numer_transakcji` | 1.000 | 60 | 0 | 0 | 0 |
| `przelew:przelew_bankowy.tytul` | 1.000 | 60 | 0 | 0 | 0 |
| `przelew:przelew_bankowy.z_rachunku` | 1.000 | 60 | 0 | 0 | 0 |
