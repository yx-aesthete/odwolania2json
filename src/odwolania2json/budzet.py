"""Budżet czasu przebiegu wsadowego (README UZP: 150 PDF w najwyżej 45 minut) i dzienny sufit wywołań w WWW.

`MAKS_CZAS_S` (domyślnie 2100 s = 35 min, zapas 10 min) liczony od startu przebiegu CLI. Każde zapytanie do API
i każdy OCR strony dostaje timeout = min(własny, pozostały budżet). Po wyczerpaniu budżetu kolejne dokumenty idą
samymi regułami (bez OCR i modelu), a pliki wynikowe i tak powstają. Bez `start()` (WWW, testy) budżet jest
nieograniczony.
"""
from __future__ import annotations

import datetime as dt
import math
import os
import threading
import time

DOMYSLNY_S = 2100.0
_start: float | None = None
_maks: float = math.inf


class BudzetWyczerpany(RuntimeError):
    """Budżet czasu przebiegu się skończył: zapytanie nie jest wysyłane (to nie jest błąd dostawcy)."""


def start(maks_s: float | None = None) -> float:
    """Uruchamia odliczanie; zwraca budżet w sekundach (`MAKS_CZAS_S`, 0 albo mniej = bez limitu)."""
    global _start, _maks
    if maks_s is None:
        try:
            maks_s = float(os.environ.get("MAKS_CZAS_S", DOMYSLNY_S))
        except ValueError:
            maks_s = DOMYSLNY_S
    _start, _maks = time.monotonic(), (maks_s if maks_s > 0 else math.inf)
    return _maks


def zatrzymaj() -> None:
    global _start, _maks
    _start, _maks = None, math.inf


def aktywny() -> bool:
    """Czy trwa przebieg wsadowy z budżetem (CLI); w WWW i testach nie."""
    return _start is not None


def pozostalo() -> float:
    return math.inf if _start is None else _maks - (time.monotonic() - _start)


def wyczerpany(zapas_s: float = 0.0) -> bool:
    return pozostalo() <= zapas_s or sufit_wyczerpany()


def limit(timeout_s: float, minimum_s: float = 1.0) -> float:
    """Timeout jednej operacji przycięty do pozostałego budżetu (najmniej `minimum_s`)."""
    return max(minimum_s, min(timeout_s, pozostalo()))


def sprawdz() -> None:
    if pozostalo() <= 0:
        raise BudzetWyczerpany("budżet czasu przebiegu wyczerpany (MAKS_CZAS_S)")
    _policz_wywolanie()


# Dzienny sufit wywołań API (tylko podgląd WWW: strona publiczna woła model kluczem właściciela). Model i OCR
# łącznie, licznik w pamięci procesu, zerowany o północy czasu lokalnego. Po przekroczeniu: same reguły.
_sufit: int | None = None
_licznik = 0
_dzien: dt.date | None = None
_blokada_sufitu = threading.Lock()


def ustaw_sufit_dzienny(n: int | None) -> None:
    global _sufit, _licznik, _dzien
    with _blokada_sufitu:
        _sufit, _licznik, _dzien = (n if n and n > 0 else None), 0, dt.date.today()


def _zeruj_o_polnocy() -> None:
    global _licznik, _dzien
    if _dzien != dt.date.today():
        _licznik, _dzien = 0, dt.date.today()


def sufit_wyczerpany() -> bool:
    if _sufit is None:
        return False
    with _blokada_sufitu:
        _zeruj_o_polnocy()
        return _licznik >= _sufit


def _policz_wywolanie() -> None:
    global _licznik
    if _sufit is None:
        return
    with _blokada_sufitu:
        _zeruj_o_polnocy()
        if _licznik >= _sufit:
            raise BudzetWyczerpany("dzienny limit wywołań modelu wyczerpany (WEB_MAKS_WYWOLAN_DZIENNIE)")
        _licznik += 1


def stan_sufitu() -> dict:
    with _blokada_sufitu:
        _zeruj_o_polnocy()
        return {"maks_wywolan_dziennie": _sufit, "wywolan_dzis": _licznik,
                "wyczerpany": _sufit is not None and _licznik >= _sufit}
