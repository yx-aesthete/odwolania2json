# Wyniki F1 (60 spraw treningowych UZP, same reguły, bez modelu)

Pomiar: `PYTHONPATH=src python -m odwolania2json.eval --pred <output> --scisle --md docs/WYNIKI.md`.
Uwaga: reguły pisane na tych samych 60 sprawach — to wynik na zbiorze uczącym, nie prognoza dla testu.

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
