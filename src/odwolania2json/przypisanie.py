"""Przypisanie elementów podlisty do właściwego elementu listy po wzmiance w tekście (sekcja `przypisanie` w YAML).

Przykład (pełnomocnictwo konsorcjum): podpisujący są zebrani z bloku podpisów, ale bloki nie zawsze mówią, który
podpis należy do którego mocodawcy. W opisie mocodawców bywa „X sp. z o.o., …, reprezentowana przez: Jan Nowak –
Prezes Zarządu; Y S.A., …, reprezentowana przez: Anna Kowalska”. Fragment tekstu i-tego mocodawcy to tekst od jego
nazwy do nazwy następnego (najdalej do kotwicy końca, np. „udziela pełnomocnictwa”). Podpisujący, którego nazwisko
pada we fragmencie dokładnie jednego mocodawcy, trafia do niego; pozostali zostają tam, gdzie byli.
Działa tylko przy co najmniej dwóch elementach listy.
"""
from __future__ import annotations

import copy
import re
from typing import Any


def _pobierz(obj: Any, sciezka: str) -> Any:
    for k in sciezka.split("."):
        obj = obj.get(k) if isinstance(obj, dict) else None
    return obj


def _wzorzec_wzmianki(osoba: str) -> re.Pattern | None:
    """„reprezentowana przez: Jan Nowak” (także Jana Nowaka / Janowi Nowakowi): imię i nazwisko razem po „przez”."""
    czlony = osoba.split()
    if len(czlony) < 2:
        return None
    imie, nazwisko = czlony[0], czlony[-1]
    r_imie = re.escape(imie[: max(3, len(imie) - 2)])
    r_nazw = re.escape(nazwisko[: max(3, len(nazwisko) - 2)])
    return re.compile(rf"(?:reprezentowan\w*|dzia[łl]aj[aą]c\w*)\s+przez\s*:?\s*(?:[^;\n]{{0,60}}?\s)?{r_imie}\w*\s+{r_nazw}",
                      re.I)


def przypisz(dane: Any, tekst: str, spec: dict) -> Any:
    lista_k, nazwa_k, pod_k, pole_k = spec["lista"], spec["pole_nazwy"], spec["podlista"], spec["pole"]
    if not isinstance(dane, dict) or not isinstance(dane.get(lista_k), list) or len(dane[lista_k]) < 2:
        return dane
    elementy = dane[lista_k]
    koniec = len(tekst)
    if spec.get("do"):
        m = re.search(spec["do"], tekst, re.I)
        koniec = m.start() if m else koniec
    zakres = tekst[:koniec]
    pozycje = []
    for el in elementy:
        nazwa = _pobierz(el, nazwa_k)
        i = zakres.find(nazwa) if isinstance(nazwa, str) and nazwa else -1
        pozycje.append(i)
    if any(p < 0 for p in pozycje) or pozycje != sorted(pozycje):
        return dane  # nazwy nie stoją w tekście po kolei: nie zgadujemy
    fragmenty = [zakres[p: (pozycje[i + 1] if i + 1 < len(pozycje) else koniec)] for i, p in enumerate(pozycje)]
    wynik = copy.deepcopy(dane)
    wszyscy = [(i, os) for i, el in enumerate(wynik[lista_k]) for os in (el.get(pod_k) or [])
               if isinstance(os, dict) and os.get(pole_k)]
    if not wszyscy:
        return dane
    nowe: list[list[dict]] = [[] for _ in elementy]
    for i, os in wszyscy:
        wz = _wzorzec_wzmianki(os[pole_k])
        trafienia = [j for j, f in enumerate(fragmenty) if wz and wz.search(f)] if wz else []
        nowe[trafienia[0] if len(trafienia) == 1 else i].append(os)
    for j, el in enumerate(wynik[lista_k]):
        if nowe[j]:
            el[pod_k] = nowe[j]
        elif el.get(pod_k):
            el[pod_k] = [{k: None for k in el[pod_k][0]}]  # jak pusty element z reguł
    return wynik
