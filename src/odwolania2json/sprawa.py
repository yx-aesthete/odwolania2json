"""Ujednolicenie nazw w obrębie jednej sprawy (katalog w ./output).

Te same osoby i firmy występują w kilku pismach sprawy (odwołanie, pełnomocnictwo, przelew). OCR skanów gubi czasem
polskie znaki („Zaneta Olszewska” zamiast „Żaneta Olszewska”). Gdy dwie wartości pól `imie_nazwisko` albo `nazwa`
w tej samej sprawie różnią się wyłącznie polskimi znakami, wszędzie wpisujemy wariant z większą liczbą polskich znaków.
Inne różnice (litery, kolejność, długość) nie są ruszane. Wyłącznik: `ujednolicaj_nazwy: false` w config/aplikacja.yaml
albo zmienna UJEDNOLICAJ_NAZWY=0.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger("odwolania2json")
POLA = ("imie_nazwisko", "nazwa")
_POLSKIE = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
_BEZ = str.maketrans(_POLSKIE, "acelnoszzACELNOSZZ")


def wlaczone(konfig: Path) -> bool:
    z_env = os.environ.get("UJEDNOLICAJ_NAZWY")
    if z_env in ("0", "1"):
        return z_env == "1"
    if konfig.exists():
        return bool((yaml.safe_load(konfig.read_text(encoding="utf-8")) or {}).get("ujednolicaj_nazwy", True))
    return True


def _klucz(t: str) -> str:
    return " ".join(t.translate(_BEZ).casefold().split())


def _wartosci(obj: Any, wynik: list[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in POLA and isinstance(v, str) and v.strip():
                wynik.append(v)
            else:
                _wartosci(v, wynik)
    elif isinstance(obj, list):
        for v in obj:
            _wartosci(v, wynik)


def _zamien(obj: Any, mapa: dict[str, str]) -> Any:
    if isinstance(obj, dict):
        return {k: (mapa.get(v, v) if k in POLA and isinstance(v, str) else _zamien(v, mapa)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_zamien(v, mapa) for v in obj]
    return obj


def mapa_ujednolicen(wartosci: list[str]) -> dict[str, str]:
    """wartość -> wariant z największą liczbą polskich znaków wśród wartości o tym samym kluczu bez znaków."""
    grupy: dict[str, set[str]] = {}
    for w in wartosci:
        grupy.setdefault(_klucz(w), set()).add(w)
    mapa = {}
    for warianty in grupy.values():
        if len(warianty) < 2:
            continue
        najlepszy = max(sorted(warianty), key=lambda w: sum(z in _POLSKIE for z in w))
        for w in warianty:
            if w != najlepszy and sum(z in _POLSKIE for z in w) < sum(z in _POLSKIE for z in najlepszy):
                mapa[w] = najlepszy
    return mapa


def ujednolic_sprawy(katalog_wyjscia: Path) -> int:
    """Dla każdego katalogu z JSON-ami w ./output: ujednolicenie nazw. Zwraca liczbę zmienionych plików."""
    zmienione = 0
    katalogi = {p.parent for p in katalog_wyjscia.rglob("*.json")}
    for kat in sorted(katalogi):
        dane: dict[Path, Any] = {}
        for p in sorted(kat.glob("*.json")):
            try:
                tekst = p.read_text(encoding="utf-8").strip()
                obj = json.loads(tekst) if tekst else None
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(obj, dict) and obj:
                dane[p] = obj
        wartosci: list[str] = []
        for obj in dane.values():
            _wartosci(obj, wartosci)
        mapa = mapa_ujednolicen(wartosci)
        if not mapa:
            continue
        for p, obj in dane.items():
            nowy = _zamien(obj, mapa)
            if nowy != obj:
                p.write_text(json.dumps(nowy, ensure_ascii=False, indent=2), encoding="utf-8")
                zmienione += 1
        log.info("[sprawa] %s: ujednolicone nazwy %s", kat.name, "; ".join(f"{a} -> {b}" for a, b in mapa.items()))
    return zmienione
