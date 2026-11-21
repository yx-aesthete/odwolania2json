"""Potok dla jednego pliku: tekst -> klasa -> ekstrakcja -> wynik + audyt."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .klasy import rozpoznaj, wczytaj_klasy
from .pdftext import wczytaj
from .silnik import Silnik

log = logging.getLogger("odwolania2json")


def oczysc(tekst: str, wzorce: list[str]) -> str:
    for w in wzorce:
        tekst = re.sub(w, "", tekst)
    return tekst


@dataclass(frozen=True)
class WynikPliku:
    klasa: str | None
    dane: Any
    audyt: dict


def _strona(pozycja: int | None, granice: list[int]) -> int | None:
    if pozycja is None:
        return None
    return next((i + 1 for i, g in enumerate(granice) if pozycja < g), len(granice))


class Potok:
    def __init__(self, katalog_klas: Path, uzyj_llm: bool = True):
        self.klasy = wczytaj_klasy(katalog_klas)
        self.llm = None
        if uzyj_llm:
            from .llm import klient_z_env
            self.llm = klient_z_env()
        log.info("Klasy: %s; model: %s", ", ".join(k.nazwa for k in self.klasy),
                 getattr(self.llm, "opis", "brak (same reguły)"))

    def przetworz_tekst(self, tekst: str, strony: tuple[str, ...] = ()) -> WynikPliku:
        rozp = rozpoznaj(tekst, self.klasy)
        audyt: dict = {"klasyfikacja": {"punkty": rozp.punkty, "trafienia": rozp.trafienia}}
        if rozp.klasa is None:
            audyt["klasa"] = None
            return WynikPliku(None, None, audyt)
        strony = tuple(oczysc(st, rozp.klasa.spec.get("oczysc", [])) for st in (strony or (tekst,)))
        tekst = "\n".join(strony)
        wynik = Silnik(rozp.klasa.spec, self.llm).ekstrahuj(tekst)
        granice, suma = [], 0
        for s in strony:
            suma += len(s) + 1
            granice.append(suma)
        audyt["klasa"] = rozp.klasa.nazwa
        audyt["pola"] = [
            {"pole": d.pole, "wartosc": d.wartosc, "metoda": d.metoda, "cytat": d.cytat,
             "strona": _strona(d.pozycja, granice)}
            for d in wynik.dowody
        ]
        return WynikPliku(rozp.klasa.nazwa, wynik.dane, audyt)

    def przetworz(self, pdf: Path) -> WynikPliku:
        dok = wczytaj(pdf)
        w = self.przetworz_tekst(dok.tekst, dok.strony)
        w.audyt["plik"] = pdf.name
        w.audyt["strony"] = len(dok.strony)
        return w
