"""Rejestr klas dokumentów: każdy plik config/klasy/*.yaml to jedna klasa. Kod nie zna nazw klas."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import yaml

BLAD_MODELU = "__blad_modelu__"  # odpowiedź wybor_modelu przy awarii API (wtedy rozstrzygają reguły)


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
    pewnosc: str = "wysoka"


def wczytaj_klasy(katalog: Path | list[Path]) -> list[Klasa]:
    """Klasy z jednego albo kilku katalogów (np. config/klasy + katalog klas dodatkowych).
    Klasa ma `rozpoznanie` i albo `wynik` (klocki), albo `pola` (klasa opisowa, patrz opisowa.py)."""
    from .opisowa import czy_opisowa, pola, rozpoznanie_z_fraz
    katalogi = katalog if isinstance(katalog, (list, tuple)) else [katalog]
    klasy = []
    for p in sorted(p for k in katalogi for p in Path(k).glob("*.yaml")):
        spec = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not isinstance(spec, dict) or "rozpoznanie" not in spec or not ("wynik" in spec or "pola" in spec):
            raise ValueError(f"{p}: klasa musi mieć sekcję 'rozpoznanie' oraz 'wynik' albo 'pola'")
        if spec.get("wylaczona"):
            continue
        spec = {**spec, "rozpoznanie": rozpoznanie_z_fraz(spec["rozpoznanie"])}
        if czy_opisowa(spec):
            pola(spec["pola"])  # błąd w opisie pól widać przy starcie, nie przy pierwszym dokumencie
        klasy.append(Klasa(spec.get("nazwa", p.stem), spec, p))
    if not klasy:
        raise ValueError(f"brak klas w {', '.join(map(str, katalogi))}")
    return klasy


@dataclass(frozen=True)
class UstawieniaKlasyfikacji:
    okno: int = 10000          # ile znaków od początku dokumentu przeszukują `slowa` i `ujemne`
    okno_tytulu: int = 3000    # w ilu pierwszych znakach szukać linii tytułowych
    min_punkty: float = 3      # poniżej: brak sygnałów -> dokument obcy (albo model)
    przewaga: float = 3        # najlepsza klasa poniżej progu wygrywa, gdy ma taką przewagę nad drugą

    @classmethod
    def z_pliku(cls, sciezka: Path | None) -> "UstawieniaKlasyfikacji":
        if sciezka is None or not sciezka.exists():
            return cls()
        konf = (yaml.safe_load(sciezka.read_text(encoding="utf-8")) or {}).get("klasyfikacja") or {}
        return cls(**{k: type(getattr(cls(), k))(v) for k, v in konf.items() if hasattr(cls(), k)})


def strefa_tytulu(tekst: str, dlugosc: int) -> str:
    """Kandydaci na tytuł bez białych znaków, WIELKIMI literami („O D WO ŁANIE” -> „ODWOŁANIE”):
    sam początek dokumentu oraz krótkie linie bez cyfr i dwukropka z pierwszych `dlugosc` znaków,
    zapisane wielkimi literami albo bardzo krótkie (np. „Pełnomocnictwo”). Części rozdziela „|”."""
    czesci = [re.sub(r"\s+", "", tekst)[:120].upper()]
    for linia in tekst[:dlugosc].splitlines():
        zwarta = re.sub(r"\s+", "", linia)
        if not zwarta or len(zwarta) > 70 or re.search(r"[\d:@]", zwarta):
            continue
        litery = [z for z in zwarta if z.isalpha()]
        if litery and (all(z.isupper() for z in litery) or len(zwarta) <= 30):
            czesci.append(zwarta.upper())
    return "|".join(czesci)


def scal_rozstrzelone(tekst: str) -> str:
    """„P O T W I E R D Z E N I E  P R Z E L E W U” -> „POTWIERDZENIE PRZELEWU” (słowa rozdziela 2+ spacji)."""
    def scal(m: re.Match) -> str:
        return " ".join(s.replace(" ", "") for s in re.split(r" {2,}", m.group(0)))
    return re.sub(r"(?<!\S)(?:\w {1,2}){3,}\w(?!\S)", scal, tekst)


def _punktuj(spec: dict, poczatek: str, tytul: str) -> tuple[float, list[str], bool]:
    suma, hity = 0.0, []
    for wzorzec, waga in (spec.get("tytul") or {}).items():
        if re.search(wzorzec, tytul, re.I):
            suma += float(waga)
            hity.append(f"tytul:{wzorzec}")
    for wzorzec, waga in (spec.get("slowa") or {}).items():
        if re.search(wzorzec, poczatek, re.I | re.M):
            suma += float(waga)
            hity.append(wzorzec)
    for wzorzec, waga in (spec.get("ujemne") or {}).items():
        if re.search(wzorzec, poczatek, re.I | re.M):
            suma -= abs(float(waga))
            hity.append(f"ujemne:{wzorzec}")
    for wzorzec, waga in (spec.get("tytul_ujemne") or {}).items():
        if re.search(wzorzec, tytul, re.I):
            suma -= abs(float(waga))
            hity.append(f"tytul_ujemne:{wzorzec}")
    wykluczona = False
    # dowód pozytywny: grupy z `wymagane` (każda to lista alternatyw). Domyślnie trafić muszą wszystkie;
    # `wymagane_min: N` = co najmniej N grup; `wymagane_z_tytulem: {wzorzec, min}` = przy takim tytule wystarczy `min`
    # (odporność na szum OCR: zgubiona etykieta albo cyfra nie gubi całego dokumentu)
    grupy = spec.get("wymagane") or []
    if grupy:
        braki = []
        for nr, grupa in enumerate(grupy):
            wzorce = grupa if isinstance(grupa, list) else [grupa]
            if not any(re.search(w, poczatek, re.I | re.M) for w in wzorce):
                braki.append(nr)
        trafione = len(grupy) - len(braki)
        minimum = int(spec.get("wymagane_min", len(grupy)))
        z_tytulem = spec.get("wymagane_z_tytulem") or {}
        if z_tytulem and re.search(z_tytulem["wzorzec"], tytul, re.I):   # tylko strefa tytułu, nie treść
            minimum = min(minimum, int(z_tytulem.get("min", minimum)))
        if trafione < minimum:
            wykluczona = True
        elif braki:   # bez kompletu cech: dodatkowy hamulec `wymagane_wyklucz_bez_kompletu` (np. faktura, nota)
            for w in spec.get("wymagane_wyklucz_bez_kompletu") or []:
                if re.search(w, poczatek, re.I | re.M):
                    wykluczona = True
                    hity.append(f"wyklucz_bez_kompletu:{w}")
                    break
        hity.extend(f"brak_wymaganego:{nr}" for nr in braki)
    for wzorzec in spec.get("wyklucz") or []:
        if re.search(wzorzec, poczatek, re.I | re.M):
            wykluczona = True
            hity.append(f"wyklucz:{wzorzec}")
    return suma, hity, wykluczona


def rozpoznaj(tekst: str, klasy: list[Klasa], ust: UstawieniaKlasyfikacji | None = None,
              wybor_modelu: Callable[[str, list[Klasa]], str | None] | None = None) -> Rozpoznanie:
    """Klasa dokumentu z sygnałów w YAML (`rozpoznanie`): tytuł (strefa bez spacji), słowa, sygnały ujemne.

    1. Najlepsza klasa >= jej `prog` -> ta klasa.
    2. Poniżej progu, ale >= min_punkty i z przewagą `przewaga` nad drugą -> najlepsza (pewność niska).
    3. W pozostałych przypadkach z sygnałami rozstrzyga model (gdy jest), inaczej dokument obcy.
    """
    ust = ust or UstawieniaKlasyfikacji()
    poczatek, tytul = scal_rozstrzelone(tekst[:ust.okno]), strefa_tytulu(tekst, ust.okno_tytulu)
    punkty: dict[str, float] = {}
    trafienia: dict[str, list[str]] = {}
    for k in klasy:
        suma, hity, wykluczona = _punktuj(k.spec["rozpoznanie"], poczatek, tytul)
        punkty[k.nazwa], trafienia[k.nazwa] = (float("-inf") if wykluczona else suma), hity
    ranking = sorted(klasy, key=lambda k: punkty[k.nazwa], reverse=True)
    najlepsza = ranking[0]
    p1 = punkty[najlepsza.nazwa]
    p2 = punkty[ranking[1].nazwa] if len(ranking) > 1 else float("-inf")
    if p2 == float("-inf") and len(ranking) > 1:
        p2 = 0.0   # inne klasy odpadły (brak wymaganych cech): przewaga liczona od zera, przy słabych sygnałach pyta model
    if p1 == float("-inf"):
        return Rozpoznanie(None, punkty, trafienia, "brak wymaganych cech")
    if p1 >= float(najlepsza.spec["rozpoznanie"].get("prog", 1)) and p1 - p2 >= 1:
        return Rozpoznanie(najlepsza, punkty, trafienia, "wysoka")
    if p1 >= ust.min_punkty and p1 - p2 >= ust.przewaga:
        return Rozpoznanie(najlepsza, punkty, trafienia, "niska")
    if p1 >= ust.min_punkty and wybor_modelu is not None:
        nazwa = wybor_modelu(tekst[:ust.okno], klasy)
        if nazwa == BLAD_MODELU:  # awaria API: najlepsza klasa z reguł (ma >= min_punkty), nie dokument obcy
            return Rozpoznanie(najlepsza, punkty, trafienia, "niska (model niedostępny)")
        wybrana = next((k for k in klasy if k.nazwa == nazwa), None)
        if wybrana is not None and punkty[wybrana.nazwa] == float("-inf"):
            wybrana = None   # model nie przywraca klasy bez minimalnego zestawu cech (`wymagane`)
        return Rozpoznanie(wybrana, punkty, trafienia, "model")
    if p1 >= float(najlepsza.spec["rozpoznanie"].get("prog", 1)):  # remis dwóch mocnych klas: wyższa
        return Rozpoznanie(najlepsza, punkty, trafienia, "niska")
    return Rozpoznanie(None, punkty, trafienia, "brak sygnałów")
