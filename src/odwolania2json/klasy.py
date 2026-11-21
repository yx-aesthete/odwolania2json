"""Rejestr klas dokumentów: każdy plik config/klasy/*.yaml to jedna klasa. Kod nie zna nazw klas."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Klasa:
    nazwa: str
    spec: dict
    zrodlo: Path


@dataclass(frozen=True)
class Rozpoznanie:
    klasa: Klasa | None
    punkty: dict[str, float]
    trafienia: dict[str, list[str]]


def wczytaj_klasy(katalog: Path) -> list[Klasa]:
    klasy = []
    for p in sorted(katalog.glob("*.yaml")):
        spec = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not isinstance(spec, dict) or "wynik" not in spec or "rozpoznanie" not in spec:
            raise ValueError(f"{p}: klasa musi mieć sekcje 'rozpoznanie' i 'wynik'")
        if spec.get("wylaczona"):
            continue
        klasy.append(Klasa(spec.get("nazwa", p.stem), spec, p))
    if not klasy:
        raise ValueError(f"brak klas w {katalog}")
    return klasy


def rozpoznaj(tekst: str, klasy: list[Klasa], okno: int = 4000) -> Rozpoznanie:
    """Suma wag słów kluczowych z YAML w początku dokumentu; poniżej progu klasy = dokument obcy."""
    poczatek = tekst[:okno]
    punkty: dict[str, float] = {}
    trafienia: dict[str, list[str]] = {}
    for k in klasy:
        r = k.spec["rozpoznanie"]
        suma, hity = 0.0, []
        for wzorzec, waga in (r.get("slowa") or {}).items():
            if re.search(wzorzec, poczatek, re.I):
                suma += float(waga)
                hity.append(wzorzec)
        for wzorzec in r.get("wyklucz") or []:
            if re.search(wzorzec, poczatek, re.I):
                suma = float("-inf")
                hity.append(f"wyklucz:{wzorzec}")
        punkty[k.nazwa], trafienia[k.nazwa] = suma, hity
    najlepsza = max(klasy, key=lambda k: punkty[k.nazwa])
    if punkty[najlepsza.nazwa] < float(najlepsza.spec["rozpoznanie"].get("prog", 1)):
        return Rozpoznanie(None, punkty, trafienia)
    return Rozpoznanie(najlepsza, punkty, trafienia)
