# Zbiór kontrolny: odporność reguł na zaburzenia tekstu

Uruchomienie:

```
PYTHONPATH=src .venv/bin/python scripts/kontrolny.py --md docs/KONTROLNY.md
```

Dokumentów: 184 (60 spraw × 3 pliki). Każde zaburzenie stosowane osobno, na kopii tekstu z PDF; ekstrakcja bez modelu (same reguły z `config/klasy/*.yaml`); F1 w trybie ścisłym (`eval.porownaj`, `--scisle`) wobec niezmienionej referencji UZP, liczone na wszystkich dokumentach (niezmienione wnoszą wynik bazowy).

Kolumny: **zmienione** = dokumenty, w których zaburzenie coś zmieniło; **gorzej** = dokumenty, w których co najmniej jedno pole zepsuło się względem wyniku bez zaburzeń; **naruszone** = dokumenty pominięte, bo po zaburzeniu wartość z referencji zniknęła z tekstu (zaburzenie zmieniłoby znaczenie).

| Zaburzenie | Opis | F1 | zmienione | gorzej | naruszone | Zepsute pola (liczba dokumentów) |
|---|---|---|---|---|---|---|
| **bez zaburzeń** | — | 1.0000 | 0 | 0 | 0 | — |
| `zlamanie_nazwy` | złamanie linii w środku nazwy firmy | 0.9856 | 118 | 30 | 0 | `pelnomocnictwo:mocodawca[].podpisujacy[].imie_nazwisko` (33), `pelnomocnictwo:mocodawca[].data.nazwa` (19), `odwolanie:Zamawiajacy[].nazwa` (6) |
| `nr_referencyjny_znak` | „nr referencyjny sprawy:” -> „znak postępowania:” | 0.9901 | 56 | 40 | 0 | `odwolanie:ZamowieniePubliczne.numer_postepowania` (40) |
| `w_dniu_na_dnia` | „w dniu 20 marca” -> „dnia 20 marca” | 0.9988 | 67 | 5 | 0 | `przelew:przelew_bankowy.data_operacji` (5) |
| `przelew_dwukropek` | „Kwota operacji 50,00” -> „Kwota operacji: 50,00” | 0.9988 | 60 | 5 | 0 | `przelew:przelew_bankowy.numer_transakcji` (5) |
| `strona_inna_forma` | „str. 1/3” w środku strony | 0.9990 | 184 | 4 | 0 | `odwolanie:ZamowieniePubliczne.numer_postepowania` (1), `przelew:przelew_bankowy.numer_transakcji` (1), `przelew:przelew_bankowy.na_rachunek` (1), `przelew:przelew_bankowy.data_operacji` (1) |
| `strona_w_srodku` | „Strona 1 z 3” w środku strony | 0.9993 | 184 | 3 | 0 | `przelew:przelew_bankowy.numer_transakcji` (1), `przelew:przelew_bankowy.na_rachunek` (1), `przelew:przelew_bankowy.data_operacji` (1) |
| `przelew_identyfikator` | „Numer referencyjny/Nr ref.” -> „Identyfikator transakcji” | 0.9993 | 44 | 3 | 0 | `przelew:przelew_bankowy.numer_transakcji` (3) |
| `kwota_waluta_przed` | 200,00 PLN -> PLN 200,00 | 0.9995 | 44 | 2 | 0 | `przelew:przelew_bankowy.kwota` (2) |
| `pel_tytul_biernik` | „ustanawiam pełnomocnikiem r. pr. X” -> „… radcę prawnego X” / „adwokata X” | 0.9995 | 60 | 2 | 0 | `pelnomocnictwo:pelnomocnicy[].imie_nazwisko` (2) |
| `zamiana_blokow` | blok Zamawiającego przed blokiem Odwołującego | 0.9995 | 60 | 2 | 0 | `odwolanie:Zamawiajacy[].krs` (2) |
| `daty_slownie` | 16.06.2025 / 2025-06-16 -> 16 czerwca 2025 r. | 1.0000 | 99 | 0 | 0 | — |
| `daty_kropki` | 16 czerwca 2025 / 2025-06-16 -> 16.06.2025 | 1.0000 | 149 | 0 | 0 | — |
| `daty_iso` | 16.06.2025 / 16 czerwca 2025 -> 2025-06-16 | 1.0000 | 179 | 0 | 0 | — |
| `daty_ukosnik` | dowolna data -> 16/06/2025 | 1.0000 | 184 | 0 | 0 | — |
| `dnia_w_naglowku` | „Łódź, 1 kwietnia 2026” -> „Łódź, dnia 1 kwietnia 2026 r.” | 1.0000 | 51 | 0 | 0 | — |
| `nip_kreski` | NIP 9999284065 -> NIP 999-928-40-65 | 1.0000 | 120 | 0 | 0 | — |
| `nip_nr_po` | „NIP:” -> „NIP nr” | 1.0000 | 110 | 0 | 0 | — |
| `nip_nr_przed` | „NIP:” -> „nr NIP” | 1.0000 | 110 | 0 | 0 | — |
| `nip_numer_identyfikacji` | „NIP:” -> „numer identyfikacji podatkowej (NIP):” | 1.0000 | 110 | 0 | 0 | — |
| `regon_nr` | „REGON:” -> „REGON nr” | 1.0000 | 106 | 0 | 0 | — |
| `krs_pod_numerem` | „KRS:” -> „wpisana do KRS pod numerem” | 1.0000 | 113 | 0 | 0 | — |
| `krs_nr` | „KRS:” -> „nr KRS” | 1.0000 | 113 | 0 | 0 | — |
| `identyfikatory_srednik` | „KRS: X, NIP: Y” -> „KRS – X; NIP – Y” | 1.0000 | 121 | 0 | 0 | — |
| `rachunek_ciag` | PL64 6217 1965 ... -> PL646217... | 1.0000 | 38 | 0 | 0 | — |
| `rachunek_spacje` | PL05470680... -> PL05 4706 80... | 1.0000 | 30 | 0 | 0 | — |
| `rachunek_bez_pl` | PL05 4706 ... -> 05 4706 ... | 1.0000 | 48 | 0 | 0 | — |
| `kwota_pln_na_zl` | 200,00 PLN -> 200,00 zł | 1.0000 | 44 | 0 | 0 | — |
| `kwota_zl_na_pln` | 200,00 zł -> 200,00 PLN | 1.0000 | 35 | 0 | 0 | — |
| `kwota_kropka` | 200,00 -> 200.00 | 1.0000 | 78 | 0 | 0 | — |
| `kwota_bez_groszy` | 200,00 PLN -> 200 PLN | 1.0000 | 69 | 0 | 0 | — |
| `kwota_slownie` | 200,00 PLN -> 200,00 PLN (słownie: dwieście złotych 00/100) | 1.0000 | 44 | 0 | 0 | — |
| `odwolujacy_wykonawca` | „Odwołujący:” -> „Odwołujący (Wykonawca):” | 1.0000 | 60 | 0 | 0 | — |
| `zamawiajacy_myslnik` | „Zamawiający:” -> „Zamawiający – ” | 1.0000 | 57 | 0 | 0 | — |
| `reprezentowany_w_imieniu` | „reprezentowana przez:” -> „w imieniu którego działa:” | 1.0000 | 74 | 0 | 0 | — |
| `reprezentowany_pelnomocnik` | „reprezentowana przez:” -> „działający przez pełnomocnika:” | 1.0000 | 74 | 0 | 0 | — |
| `pn_pod_nazwa` | „pn.” -> „pod nazwą” | 1.0000 | 89 | 0 | 0 | — |
| `pn_pt` | „pn.” -> „pt.” | 1.0000 | 89 | 0 | 0 | — |
| `cudzyslowy_proste` | „…” -> "…" | 1.0000 | 121 | 0 | 0 | — |
| `cudzyslowy_francuskie` | „…” -> «…» | 1.0000 | 121 | 0 | 0 | — |
| `etykiety_wielkie` | „Odwołujący:” -> „ODWOŁUJĄCY:” (też Zamawiający, dotyczy) | 1.0000 | 60 | 0 | 0 | — |
| `bez_naglowka_prezes` | usunięty nagłówek „Prezes KIO, ul. Postępu 17A, …” | 1.0000 | 51 | 0 | 0 | — |
| `puste_linie` | pusta linia po każdej linii | 1.0000 | 184 | 0 | 0 | — |
| `podwojne_spacje` | każda spacja podwojona | 1.0000 | 184 | 0 | 0 | — |
| `przelew_wartosc_pod` | „Wartość 50,00” -> „Wartość\n50,00” | 1.0000 | 21 | 0 | 0 | — |
| `przelew_wartosc_obok` | „Kwota operacji\n200,00” -> „Kwota operacji: 200,00” | 1.0000 | 50 | 0 | 0 | — |
| `przelew_etykiety_wielkie` | „Rachunek odbiorcy” -> „RACHUNEK ODBIORCY” itd. | 1.0000 | 54 | 0 | 0 | — |
| `przelew_nadawca` | „Zleceniodawca/Płatnik” -> „Nadawca”, „Rachunek zleceniodawcy/obciążany” -> „Rachunek nadawcy” | 1.0000 | 45 | 0 | 0 | — |
| `przelew_beneficjent` | „Odbiorca” -> „Beneficjent”, „Rachunek odbiorcy/uznawany” -> „Rachunek beneficjenta” | 1.0000 | 47 | 0 | 0 | — |
| `przelew_nr_rachunku` | „Rachunek odbiorcy” -> „Nr rachunku odbiorcy” (też nadawcy) | 1.0000 | 46 | 0 | 0 | — |
| `przelew_tytulem` | „Tytuł przelewu/Tytuł/Opis” -> „Tytułem” | 1.0000 | 52 | 0 | 0 | — |
| `przelew_kwota_przelewu` | „Kwota/Kwota operacji/Wartość” -> „Kwota przelewu” | 1.0000 | 45 | 0 | 0 | — |
| `przelew_data_ksiegowania` | „Data operacji/transakcji/realizacji” -> „Data księgowania” | 1.0000 | 55 | 0 | 0 | — |
| `przelew_data_zaksiegowania` | „Data operacji/…” -> „Data zaksięgowania” | 1.0000 | 55 | 0 | 0 | — |
| `pel_tytul_pelny` | „r. pr.” -> „radca prawny”, „adw.” -> „adwokat” | 1.0000 | 60 | 0 | 0 | — |
| `pel_tytul_bez_spacji` | „r. pr.” -> „r.pr.” | 1.0000 | 32 | 0 | 0 | — |
| `pel_ustanawia` | „ustanawiam pełnomocnikiem” -> „ustanawia pełnomocnikiem” | 1.0000 | 18 | 0 | 0 | — |
| `pel_udzielam` | „ustanawiam pełnomocnikiem” -> „udziela pełnomocnictwa” | 1.0000 | 17 | 0 | 0 | — |
| `pel_mocodawca_dwukropek` | „Mocodawcą jest X,” -> „Mocodawca: X,” | 1.0000 | 7 | 0 | 0 | — |

## Przykłady (zaburzenia, które coś psują; najgorsze na górze)

### `zlamanie_nazwy` — F1 0.9856, gorzej w 30 dok.

złamanie linii w środku nazwy firmy

- **`pelnomocnictwo:mocodawca[].podpisujacy[].imie_nazwisko`** (33 dok.)
  - `przyklad_05/pelnomocnictwo` `mocodawca[0].podpisujacy[0].imie_nazwisko`: oczekiwane 'Aleksandra Gajewski', bez zaburzenia 'Aleksandra Gajewski', po 'sp. z o.o.'
    - tekst przed: `Za Corvantis Wyposażenie sp. z o.o.`
    - tekst po: `Za Corvantis Wyposażenie ⏎ sp. z o.o.`
  - `przyklad_06/pelnomocnictwo` `mocodawca[0].podpisujacy[0].imie_nazwisko`: oczekiwane 'Bartosz Zajkowski', bez zaburzenia 'Bartosz Zajkowski', po 'sp. z o.o.'
    - tekst przed: `Za Silvatica Technologie sp. z o.o.`
    - tekst po: `Za Silvatica Technologie ⏎ sp. z o.o.`
  - `przyklad_06/pelnomocnictwo` `mocodawca[0].podpisujacy[1].imie_nazwisko`: oczekiwane 'Oliwia Gajewski', bez zaburzenia 'Oliwia Gajewski', po None
    - tekst przed: `Za Silvatica Technologie sp. z o.o.`
    - tekst po: `Za Silvatica Technologie ⏎ sp. z o.o.`
- **`pelnomocnictwo:mocodawca[].data.nazwa`** (19 dok.)
  - `przyklad_02/pelnomocnictwo` `mocodawca[0].data.nazwa`: oczekiwane 'Hartica Serwis S.A.', bez zaburzenia 'Hartica Serwis S.A.', po 'Hartica'
    - tekst przed: `Mocodawca Hartica Serwis S.A.`
    - tekst po: `Mocodawca Hartica ⏎ Serwis S.A.`
  - `przyklad_05/pelnomocnictwo` `mocodawca[0].data.nazwa`: oczekiwane 'Corvantis Wyposażenie sp. z o.o.', bez zaburzenia 'Corvantis Wyposażenie sp. z o.o.', po 'Corvantis Wyposażenie'
    - tekst przed: `Corvantis Wyposażenie sp. z o.o.`
    - tekst po: `Corvantis Wyposażenie ⏎ sp. z o.o.`
  - `przyklad_06/pelnomocnictwo` `mocodawca[0].data.nazwa`: oczekiwane 'Silvatica Technologie sp. z o.o.', bez zaburzenia 'Silvatica Technologie sp. z o.o.', po 'sp. z o.o.'
    - tekst przed: `Silvatica Technologie sp. z o.o. z siedzibą w Bydgoszcz (KRS 9999360925, NIP 9998966348, REGON`
    - tekst po: `Silvatica Technologie ⏎ sp. z o.o. z siedzibą w Bydgoszcz (KRS 9999360925, NIP 9998966348, REGON`
- **`odwolanie:Zamawiajacy[].nazwa`** (6 dok.)
  - `przyklad_42/odwolanie` `Zamawiajacy[0].nazwa`: oczekiwane 'Małopolskie Centrum Logistyki Medycznej sp. z o.o.', bez zaburzenia 'Małopolskie Centrum Logistyki Medycznej sp. z o.o.', po 'Medycznej sp. z o.o.'
    - tekst przed: `Małopolskie Centrum Logistyki Medycznej sp. z o.o.`
    - tekst po: `Małopolskie Centrum Logistyki ⏎ Medycznej sp. z o.o.`
  - `przyklad_42/odwolanie` `Zamawiajacy[1].nazwa`: oczekiwane 'Krakowskie Zakłady Komunalne S.A.', bez zaburzenia 'Krakowskie Zakłady Komunalne S.A.', po 'Komunalne S.A.'
    - tekst przed: `Krakowskie Zakłady Komunalne S.A.`
    - tekst po: `Krakowskie Zakłady ⏎ Komunalne S.A.`
  - `przyklad_51/odwolanie` `Zamawiajacy[0].nazwa`: oczekiwane 'Zarząd Transportu Miejskiego w Modrzewie', bez zaburzenia 'Zarząd Transportu Miejskiego w Modrzewie', po 'Miejskiego w Modrzewie'
    - tekst przed: `Zarząd Transportu Miejskiego w Modrzewie`
    - tekst po: `Zarząd Transportu ⏎ Miejskiego w Modrzewie`

### `nr_referencyjny_znak` — F1 0.9901, gorzej w 40 dok.

„nr referencyjny sprawy:” -> „znak postępowania:”

- **`odwolanie:ZamowieniePubliczne.numer_postepowania`** (40 dok.)
  - `przyklad_01/odwolanie` `ZamowieniePubliczne.numer_postepowania`: oczekiwane 'ZS.791.2026', bez zaburzenia 'ZS.791.2026', po None
    - tekst przed: `wdrożenia” nr referencyjny sprawy: ZS.791.2026, ogłoszenie o zamówieniu nr`
    - tekst po: `wdrożenia” znak postępowania: ZS.791.2026, ogłoszenie o zamówieniu nr`
  - `przyklad_02/odwolanie` `ZamowieniePubliczne.numer_postepowania`: oczekiwane 'ZP.431.2026', bez zaburzenia 'ZP.431.2026', po None
    - tekst przed: `do urządzeń biurowych” nr referencyjny sprawy: ZP.431.2026, numer ogłoszenia TED: 2026/S086-999073`
    - tekst po: `do urządzeń biurowych” znak postępowania: ZP.431.2026, numer ogłoszenia TED: 2026/S086-999073`
  - `przyklad_03/odwolanie` `ZamowieniePubliczne.numer_postepowania`: oczekiwane 'ZP.154.2026', bez zaburzenia 'ZP.154.2026', po None
    - tekst przed: `oprogramowania do obsługi dokumentacji wraz z serwisem wsparcia technicznego” nr referencyjny`
    - tekst po: `oprogramowania do obsługi dokumentacji wraz z serwisem wsparcia technicznego” znak postępowania`

### `w_dniu_na_dnia` — F1 0.9988, gorzej w 5 dok.

„w dniu 20 marca” -> „dnia 20 marca”

- **`przelew:przelew_bankowy.data_operacji`** (5 dok.)
  - `przyklad_05/przelew` `przelew_bankowy.data_operacji`: oczekiwane '2026-10-26', bez zaburzenia '2026-10-26', po None
    - tekst przed: `Bank potwierdza, że w dniu 2026-10-26 z rachunku nr PL66 2111 8080 1009 8828 5708 1733, prowadzonego dla Corvantis`
    - tekst po: `Bank potwierdza, że dnia 2026-10-26 z rachunku nr PL66 2111 8080 1009 8828 5708 1733, prowadzonego dla Corvantis`
  - `przyklad_12/przelew` `przelew_bankowy.data_operacji`: oczekiwane '2026-07-09', bez zaburzenia '2026-07-09', po None
    - tekst przed: `Bank potwierdza, że w dniu 09-07-2026 z rachunku nr 55 0135 9913 9628 4881 0643 5346, prowadzonego dla Wexford Usługi sp. j.,`
    - tekst po: `Bank potwierdza, że dnia 09-07-2026 z rachunku nr 55 0135 9913 9628 4881 0643 5346, prowadzonego dla Wexford Usługi sp. j.,`
  - `przyklad_19/przelew` `przelew_bankowy.data_operacji`: oczekiwane '2026-04-26', bez zaburzenia '2026-04-26', po None
    - tekst przed: `Bank potwierdza, że w dniu 26 kwietnia 2026 z rachunku nr PL97 5520 7608 8416 4658 2056 3693, prowadzonego dla Corvantis`
    - tekst po: `Bank potwierdza, że dnia 26 kwietnia 2026 z rachunku nr PL97 5520 7608 8416 4658 2056 3693, prowadzonego dla Corvantis`

### `przelew_dwukropek` — F1 0.9988, gorzej w 5 dok.

„Kwota operacji 50,00” -> „Kwota operacji: 50,00”

- **`przelew:przelew_bankowy.numer_transakcji`** (5 dok.)
  - `przyklad_05/przelew` `przelew_bankowy.numer_transakcji`: oczekiwane 'CEN2611091860728', bez zaburzenia 'CEN2611091860728', po 'operacji: CEN2611091860728'
    - tekst przed: `Tytuł przelewu: „opłata skarbowa od pełnomocnictwa dla Ignacy Sadowski w postępowaniu przed KIO w przetargu`
    - tekst po: `Tytuł: przelewu: „opłata skarbowa od pełnomocnictwa dla Ignacy Sadowski w postępowaniu przed KIO w przetargu`
  - `przyklad_12/przelew` `przelew_bankowy.numer_transakcji`: oczekiwane 'CEN2607206163458', bez zaburzenia 'CEN2607206163458', po 'operacji: CEN2607206163458'
    - tekst przed: `Tytuł przelewu: „opłata skarbowa od pełnomocnictwa dla Klaudia Dobrowolski w postępowaniu przed KIO w przetargu SWZ.755.2026`
    - tekst po: `Tytuł: przelewu: „opłata skarbowa od pełnomocnictwa dla Klaudia Dobrowolski w postępowaniu przed KIO w przetargu SWZ.755.2026`
  - `przyklad_19/przelew` `przelew_bankowy.numer_transakcji`: oczekiwane 'CEN2605113961811', bez zaburzenia 'CEN2605113961811', po 'operacji: CEN2605113961811'
    - tekst przed: `Tytuł przelewu: „opłata skarbowa od pełnomocnictwa dla Aleksandra Wierzbicki w postępowaniu przed KIO w przetargu`
    - tekst po: `Tytuł: przelewu: „opłata skarbowa od pełnomocnictwa dla Aleksandra Wierzbicki w postępowaniu przed KIO w przetargu`

### `strona_inna_forma` — F1 0.9990, gorzej w 4 dok.

„str. 1/3” w środku strony

- **`odwolanie:ZamowieniePubliczne.numer_postepowania`** (1 dok.)
  - `przyklad_03/odwolanie` `ZamowieniePubliczne.numer_postepowania`: oczekiwane 'ZP.154.2026', bez zaburzenia 'ZP.154.2026', po 'str'
    - tekst przed: ``
    - tekst po: `str. 1/3`
- **`przelew:przelew_bankowy.numer_transakcji`** (1 dok.)
  - `przyklad_04/przelew` `przelew_bankowy.numer_transakcji`: oczekiwane 'CEN2608246932582', bez zaburzenia 'CEN2608246932582', po 'str. 1/3'
    - tekst przed: ``
    - tekst po: `str. 1/3`
- **`przelew:przelew_bankowy.na_rachunek`** (1 dok.)
  - `przyklad_05/przelew` `przelew_bankowy.na_rachunek`: oczekiwane '10386393618709740848534519', bez zaburzenia '10386393618709740848534519', po None
    - tekst przed: ``
    - tekst po: `str. 1/3`
- **`przelew:przelew_bankowy.data_operacji`** (1 dok.)
  - `przyklad_11/przelew` `przelew_bankowy.data_operacji`: oczekiwane '2026-08-03', bez zaburzenia '2026-08-03', po None
    - tekst przed: ``
    - tekst po: `str. 1/3`

### `strona_w_srodku` — F1 0.9993, gorzej w 3 dok.

„Strona 1 z 3” w środku strony

- **`przelew:przelew_bankowy.numer_transakcji`** (1 dok.)
  - `przyklad_04/przelew` `przelew_bankowy.numer_transakcji`: oczekiwane 'CEN2608246932582', bez zaburzenia 'CEN2608246932582', po 'Strona 1 z 3'
    - tekst przed: ``
    - tekst po: `Strona 1 z 3`
- **`przelew:przelew_bankowy.na_rachunek`** (1 dok.)
  - `przyklad_05/przelew` `przelew_bankowy.na_rachunek`: oczekiwane '10386393618709740848534519', bez zaburzenia '10386393618709740848534519', po None
    - tekst przed: ``
    - tekst po: `Strona 1 z 3`
- **`przelew:przelew_bankowy.data_operacji`** (1 dok.)
  - `przyklad_11/przelew` `przelew_bankowy.data_operacji`: oczekiwane '2026-08-03', bez zaburzenia '2026-08-03', po None
    - tekst przed: ``
    - tekst po: `Strona 1 z 3`

### `przelew_identyfikator` — F1 0.9993, gorzej w 3 dok.

„Numer referencyjny/Nr ref.” -> „Identyfikator transakcji”

- **`przelew:przelew_bankowy.numer_transakcji`** (3 dok.)
  - `przyklad_19/przelew` `przelew_bankowy.numer_transakcji`: oczekiwane 'CEN2605113961811', bez zaburzenia 'CEN2605113961811', po 'operacji: CEN2605113961811'
    - tekst przed: `Numer referencyjny operacji: CEN2605113961811.`
    - tekst po: `Identyfikator transakcji operacji: CEN2605113961811.`
  - `przyklad_26/przelew` `przelew_bankowy.numer_transakcji`: oczekiwane 'CEN2606184449569', bez zaburzenia 'CEN2606184449569', po 'operacji: CEN2606184449569'
    - tekst przed: `Nr ref. operacji: CEN2606184449569.`
    - tekst po: `Identyfikator transakcji operacji: CEN2606184449569.`
  - `przyklad_33/przelew` `przelew_bankowy.numer_transakcji`: oczekiwane 'CEN2601247064794', bez zaburzenia 'CEN2601247064794', po 'operacji: CEN2601247064794'
    - tekst przed: `Numer referencyjny operacji: CEN2601247064794.`
    - tekst po: `Identyfikator transakcji operacji: CEN2601247064794.`

### `kwota_waluta_przed` — F1 0.9995, gorzej w 2 dok.

200,00 PLN -> PLN 200,00

- **`przelew:przelew_bankowy.kwota`** (2 dok.)
  - `przyklad_05/przelew` `przelew_bankowy.kwota`: oczekiwane 17.0, bez zaburzenia 17.0, po None
    - tekst przed: `Wyposażenie sp. z o.o., wykonano przelew krajowy w kwocie 17.00 PLN na rachunek nr PL10 3863 9361 8709 7408 4853`
    - tekst po: `Wyposażenie sp. z o.o., wykonano przelew krajowy w kwocie PLN 17.00 na rachunek nr PL10 3863 9361 8709 7408 4853`
  - `przyklad_12/przelew` `przelew_bankowy.kwota`: oczekiwane 200.0, bez zaburzenia 200.0, po None
    - tekst przed: `wykonano przelew krajowy w kwocie 200.00 PLN na rachunek nr 57 4216 7791 0972 9319 0105 0689, prowadzony dla Lunareth Sieci S.A.,`
    - tekst po: `wykonano przelew krajowy w kwocie PLN 200.00 na rachunek nr 57 4216 7791 0972 9319 0105 0689, prowadzony dla Lunareth Sieci S.A.,`

### `pel_tytul_biernik` — F1 0.9995, gorzej w 2 dok.

„ustanawiam pełnomocnikiem r. pr. X” -> „… radcę prawnego X” / „adwokata X”

- **`pelnomocnictwo:pelnomocnicy[].imie_nazwisko`** (2 dok.)
  - `przyklad_44/pelnomocnictwo` `pelnomocnicy[1].imie_nazwisko`: oczekiwane 'Łukasz Sikora', bez zaburzenia 'Łukasz Sikora', po 'Łukasz Sikor'
    - tekst przed: `pełnomocnictwa: adw. Natalia Górecka (nr wpisu na listę: LU/Adw/733), adw. Łukasz Sikora (nr wpisu na`
    - tekst po: `pełnomocnictwa: adwokata Natalia Górecka (nr wpisu na listę: LU/Adw/733), adwokata Łukasz Sikora (nr wpisu na`
  - `przyklad_46/pelnomocnictwo` `pelnomocnicy[1].imie_nazwisko`: oczekiwane 'Rafał Czajka', bez zaburzenia 'Rafał Czajka', po 'Rafał Czajek'
    - tekst przed: `przez osoby podpisane poniżej, udzielają pełnomocnictwa: r. pr. Rafał Piotrowski (nr wpisu na ⏎ listę: WA-1579), r. pr. Rafał Czajka (nr wpisu na listę: GD-5864`
    - tekst po: `przez osoby podpisane poniżej, udzielają pełnomocnictwa: radcę prawnego Rafał Piotrowski (nr wpisu na ⏎ listę: WA-1579), radcę prawnego Rafał Czajka (nr wpisu n`

### `zamiana_blokow` — F1 0.9995, gorzej w 2 dok.

blok Zamawiającego przed blokiem Odwołującego

- **`odwolanie:Zamawiajacy[].krs`** (2 dok.)
  - `przyklad_52/odwolanie` `Zamawiajacy[0].krs`: oczekiwane None, bez zaburzenia None, po '9992630248'
    - tekst przed: `Zamawiający: ⏎ Gmina Rudnik Wielki ⏎ ul. Wojska Polskiego 27, 93-924 Rudnik Wielki ⏎ NIP: 9990264287, REGON: 999242211 ⏎ zp@rudnikwiel.example`
    - tekst po: ``
  - `przyklad_58/odwolanie` `Zamawiajacy[0].krs`: oczekiwane None, bez zaburzenia None, po '9993696122'
    - tekst przed: `Zamawiający: ⏎ Państwowa Akademia Nauk Stosowanych w Krzemienicy ⏎ ul. Kościuszki 11, 83-226 Krzemienica ⏎ NIP: 9996334986, REGON: 999412535 ⏎ zamowienia@krzemi`
    - tekst po: ``

## Zaburzenia bez wpływu

`daty_slownie`, `daty_kropki`, `daty_iso`, `daty_ukosnik`, `dnia_w_naglowku`, `nip_kreski`, `nip_nr_po`, `nip_nr_przed`, `nip_numer_identyfikacji`, `regon_nr`, `krs_pod_numerem`, `krs_nr`, `identyfikatory_srednik`, `rachunek_ciag`, `rachunek_spacje`, `rachunek_bez_pl`, `kwota_pln_na_zl`, `kwota_zl_na_pln`, `kwota_kropka`, `kwota_bez_groszy`, `kwota_slownie`, `odwolujacy_wykonawca`, `zamawiajacy_myslnik`, `reprezentowany_w_imieniu`, `reprezentowany_pelnomocnik`, `pn_pod_nazwa`, `pn_pt`, `cudzyslowy_proste`, `cudzyslowy_francuskie`, `etykiety_wielkie`, `bez_naglowka_prezes`, `puste_linie`, `podwojne_spacje`, `przelew_wartosc_pod`, `przelew_wartosc_obok`, `przelew_etykiety_wielkie`, `przelew_nadawca`, `przelew_beneficjent`, `przelew_nr_rachunku`, `przelew_tytulem`, `przelew_kwota_przelewu`, `przelew_data_ksiegowania`, `przelew_data_zaksiegowania`, `pel_tytul_pelny`, `pel_tytul_bez_spacji`, `pel_ustanawia`, `pel_udzielam`, `pel_mocodawca_dwukropek`
