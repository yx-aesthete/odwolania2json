"""Wskazanie elementu listy zdaniem w treści (sekcja `wskazanie` w YAML klasy).

Przykład (odwołanie, dwóch zamawiających wspólnie): który prowadzi postępowanie, bywa napisane tylko zdaniem
w uzasadnieniu („postępowanie przygotowuje i przeprowadza Gmina X”). Gdy lista ma co najmniej dwa elementy,
a nazwa z trafienia wzorca pasuje (początkiem) do nazwy dokładnie jednego elementu, ten element dostaje
`wartosc`, pozostałe `inaczej`. Bez trafienia albo przy niejednoznacznym trafieniu wynik reguł zostaje.
"""
from __future__ import annotations

import copy
import re
from typing import Any


def _klucz(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip(" ,.;:").lower()


def wskaz(dane: Any, tekst: str, specs: list[dict]) -> Any:
    wynik = dane
    for spec in specs or []:
        lista = wynik.get(spec["lista"]) if isinstance(wynik, dict) else None
        if not isinstance(lista, list) or len(lista) < 2:
            continue
        nazwy = [_klucz(str(el.get(spec["pole_nazwy"]) or "")) for el in lista]
        trafione: set[int] = set()
        for m in re.finditer(spec["regex"], tekst, re.I):
            wzm = _klucz(m.group("v"))
            pasuje = [i for i, n in enumerate(nazwy) if n and len(wzm) >= 5 and (n.startswith(wzm) or wzm.startswith(n))]
            if len(pasuje) == 1:
                trafione.add(pasuje[0])
        if len(trafione) != 1:
            continue
        (cel,) = trafione
        wynik = copy.deepcopy(wynik)
        for i, el in enumerate(wynik[spec["lista"]]):
            el[spec["pole"]] = spec.get("wartosc", 1) if i == cel else spec.get("inaczej", 0)
    return wynik
