# Zbiór kontrolny 3: pełnomocnictwa (jawny, do strojenia)

18 pełnomocnictw w 6 nowych szablonach z tej samej rodziny co szablony UZP (po 3 dokumenty na szablon). Dane fikcyjne: KRS, NIP, REGON i PESEL z prefiksem 999 albo z poprawną sumą kontrolną. Formy przypadków wpisane ręcznie w `generuj3.py` (`OSOBY`).

| Szablon | Sprawy | Co sprawdza |
|---|---|---|
| `t_ustanawia` | P01–P03 | „ustanawia pełnomocnikami:” + lista numerowana w bierniku (radcę prawnego / adwokata / radczynię prawną), podpis: nazwisko, a pod nim funkcja |
| `t_formularz` | P04–P06 | formularz z etykietami w osobnych liniach (Firma, Siedziba, Numer KRS, NIP), pełnomocnik w mianowniku po „Imię i nazwisko pełnomocnika:”, JDG bez KRS |
| `t_jdg_celownik` | P07–P09 | osoba fizyczna „Ja, X, … udzielam pełnomocnictwa radcy prawnemu / Panu …” (celownik), nazwa firmy w cudzysłowie |
| `t_konsorcjum` | P10–P12 | Lider i Partner (P12: trzech członków), „ustanawiają … wspólnym pełnomocnikiem”, podpisy „W imieniu X:” i „imię nazwisko – funkcja” |
| `t_podpis_el` | P13–P15 | „upoważnia Pana/Panią …” (biernik), podpis elektroniczny „przez: IMIĘ NAZWISKO” wielkimi literami, funkcja w osobnej linii |
| `t_paragrafy` | P16–P18 | § 1 Mocodawca w nawiasie, „§ 2. Pełnomocnictwa udziela się dla …” (dopełniacz), funkcja nad nazwiskiem |

Referencje wg `oczekiwane-json/pelnomocnictwo.json`: imiona i nazwiska w mianowniku, wielkość liter jak w mianowniku (nie WIELKIE), podpisujący bez funkcji, `pesel` jako napis albo null, `nazwa` bez cudzysłowów.

Wynik odniesienia (same reguły, dev/06 @ 97e4c16, F1 ściśle): **0,636** (TP 68, FP 16, FN 62), zły typ 0/18.
