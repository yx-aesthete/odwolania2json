"""Sprawy wgrane przez stronę WWW: pliki w katalogu tymczasowym, przetwarzanie w tle, stan każdego pliku.

Sprawa żyje w pamięci serwera i w katalogu tymczasowym najwyżej WEB_SPRAWA_MIN minut (domyślnie 60) albo
do zamknięcia (DELETE /api/sprawa/{id}). Dzięki temu podgląd może pokazać stronę PDF i zaznaczyć cytat.
Wynik każdego pliku jest taki sam jak w ./output (JSON UZP) i ./audit (cytaty), plus położenia cytatów na stronach.
"""
from __future__ import annotations

import io
import json
import re
import logging
import os
import secrets
import shutil
import tempfile
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import podglad
from .potok import Potok, przetworz_bezpiecznie

log = logging.getLogger("odwolania2json.web")
KORZEN = Path(__file__).resolve().parents[2]
CZAS_ZYCIA_S = int(float(os.environ.get("WEB_SPRAWA_MIN", "60")) * 60)
MAKS_SPRAW = int(os.environ.get("WEB_MAKS_SPRAW", "50"))
SEKUNDY_NA_STRONE_TEKST = 1
SEKUNDY_NA_STRONE_OCR = 12  # OCR skanu po API: ok. 10-15 s na stronę


@dataclass
class PlikSprawy:
    nr: int
    plik: str
    sciezka: Path | None
    stan: str = "oczekuje"  # oczekuje | przetwarzanie | gotowe | blad
    strony: int = 0
    strony_skan: list[int] = field(default_factory=list)
    start: float | None = None
    koniec: float | None = None
    wynik: dict | None = None
    blad: str | None = None

    @property
    def json_nazwa(self) -> str:
        return Path(self.plik).with_suffix(".json").name

    def szacunek_s(self) -> int:
        tekst = self.strony - len(self.strony_skan)
        return max(1, tekst * SEKUNDY_NA_STRONE_TEKST + len(self.strony_skan) * SEKUNDY_NA_STRONE_OCR)

    def opis(self) -> dict:
        teraz = time.time()
        stan = {"nr": self.nr, "plik": self.plik, "json_nazwa": self.json_nazwa, "stan": self.stan,
                "strony": self.strony, "strony_skan": self.strony_skan, "szacunek_s": self.szacunek_s(),
                "czas_s": round((self.koniec or teraz) - self.start, 1) if self.start else 0}
        if self.blad:
            stan["blad"] = self.blad
        if self.wynik:
            stan.update(self.wynik)
        return stan


@dataclass
class Sprawa:
    id: str
    katalog: Path
    pliki: list[PlikSprawy]
    utworzona: float = field(default_factory=time.time)
    nazwa: str = ""                                   # katalog w ./output i ./audit (Z36)
    zapisane: list[str] = field(default_factory=list)  # nazwy plików JSON zapisanych w ./output/<nazwa>/

    @property
    def gotowa(self) -> bool:
        return all(p.stan in ("gotowe", "blad") for p in self.pliki)

    def opis(self) -> dict:
        return {"id": self.id, "gotowa": self.gotowa, "wygasa_s": max(0, int(self.utworzona + CZAS_ZYCIA_S - time.time())),
                "pliki": [p.opis() for p in self.pliki],
                "zapis": {"katalog": f"output/{self.nazwa}/", "pliki": len(self.zapisane)} if self.nazwa else None}


def katalog_wyjscia() -> Path:
    return Path(os.environ.get("WEB_OUTPUT") or KORZEN / "output")


def katalog_audytu() -> Path:
    return Path(os.environ.get("WEB_AUDIT") or KORZEN / "audit")


def nazwa_sprawy(podana: str | None, id_: str) -> str:
    """Nazwa katalogu sprawy: podana w GUI (bez znaków spoza [A-Za-z0-9._-]) albo sprawa-RRRRMMDD-HHMMSS-<id>."""
    czysta = re.sub(r"\.{2,}", ".", re.sub(r"[^A-Za-z0-9._-]+", "-", (podana or "").strip())).strip(".-")[:60]
    return czysta or f"sprawa-{time.strftime('%Y%m%d-%H%M%S')}-{id_[:6]}"


def _zapisz(sprawa: "Sprawa", p: "PlikSprawy") -> None:
    """JSON i audyt pliku do ./output/<sprawa>/<nazwa PDF>.json i ./audit/<sprawa>/ — tak jak CLI (obcy: {})."""
    from .__main__ import ZAPIS_OBCEGO, tryb_obcych
    if not sprawa.nazwa or not p.wynik:
        return
    nazwa = Path(p.plik).with_suffix(".json").name
    if nazwa in sprawa.zapisane:   # dwa pliki o tej samej nazwie w jednym wgraniu
        nazwa = f"{Path(nazwa).stem}_{p.nr}.json"
    dane, obcy = p.wynik.get("json") or {}, tryb_obcych()
    try:
        if dane or obcy in ZAPIS_OBCEGO:
            out = katalog_wyjscia() / sprawa.nazwa / nazwa
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(dane, ensure_ascii=False, indent=2) if dane else ZAPIS_OBCEGO[obcy],
                           encoding="utf-8")
        aud = katalog_audytu() / sprawa.nazwa / nazwa
        aud.parent.mkdir(parents=True, exist_ok=True)
        aud.write_text(json.dumps(p.wynik.get("audyt") or {}, ensure_ascii=False, indent=2), encoding="utf-8")
        sprawa.zapisane.append(nazwa)
    except OSError as exc:
        log.warning("[www] nie udało się zapisać %s do output/%s: %s", p.plik, sprawa.nazwa, exc)


def _uwagi(p: "PlikSprawy", audyt: dict) -> list[str]:
    """Komunikaty dla użytkownika podglądu: dzienny sufit modelu (Z33), OCR tylko do strony WEB_MAKS_STRON."""
    from . import budzet
    uwagi = []
    if budzet.sufit_wyczerpany():
        uwagi.append("Dzienny limit modelu wyczerpany: wynik z reguł, skany nieodczytane.")
    limit = int(os.environ.get("OCR_MAKS_STRON") or 0)
    if limit and len(p.strony_skan) > limit:
        uwagi.append(f"Długi skan: odczytano tylko strony 1–{limit} z {len(p.strony_skan)} stron bez tekstu.")
    return uwagi


class Rejestr:
    """Sprawy w pamięci: tworzenie, przetwarzanie w tle (pula wątków), wygaszanie po czasie."""

    def __init__(self, potok: Callable[[], Potok], watki: int = 3):
        self._potok = potok
        self._sprawy: dict[str, Sprawa] = {}
        self._blokada = threading.Lock()
        self._pula = ThreadPoolExecutor(max(1, watki), thread_name_prefix="sprawa")

    def utworz(self, pliki: list[tuple[str, bytes | None, str | None]], nazwa: str | None = None) -> Sprawa:
        """pliki: (nazwa, zawartość albo None, błąd albo None). Zwraca sprawę od razu; przetwarzanie idzie w tle.
        Wyniki trafiają też do ./output/<nazwa sprawy>/ (Z36)."""
        self.sprzataj()
        katalog = Path(tempfile.mkdtemp(prefix="odw-sprawa-"))
        id_ = secrets.token_urlsafe(12)
        sprawa = Sprawa(id_, katalog, [], nazwa=nazwa_sprawy(nazwa, id_))
        for nr, (nazwa, dane, blad) in enumerate(pliki):
            sciezka = None
            if dane is not None and blad is None:
                sciezka = katalog / f"{nr}.pdf"
                sciezka.write_bytes(dane)
            p = PlikSprawy(nr, nazwa, sciezka, stan="blad" if blad else "oczekuje", blad=blad)
            if sciezka is not None:
                try:
                    p.strony = podglad.liczba_stron(sciezka)
                    p.strony_skan = podglad.strony_bez_tekstu(sciezka)
                except Exception:
                    p.stan, p.blad = "blad", "Plik nie jest poprawnym PDF-em"
            sprawa.pliki.append(p)
        with self._blokada:
            self._sprawy[sprawa.id] = sprawa
        for p in sprawa.pliki:
            if p.stan == "oczekuje":
                self._pula.submit(self._przetworz, p, sprawa)
        return sprawa

    def _przetworz(self, p: PlikSprawy, sprawa: Sprawa | None = None) -> None:
        p.stan, p.start = "przetwarzanie", time.time()
        try:
            w = przetworz_bezpiecznie(self._potok(), p.sciezka, log)
            audyt = {**w.audyt, "plik": p.plik}
            if audyt.get("blad"):
                p.blad = "Nie udało się przetworzyć pliku (wynik: {})"
                p.wynik = {"klasa": None, "json": {}, "audyt": audyt}
                p.stan = "blad"
                if sprawa is not None:
                    _zapisz(sprawa, p)
                return
            pola = audyt.get("pola") or []
            p.wynik = {"klasa": w.klasa, "json": w.dane or {}, "audyt": audyt,
                       "polozenia": podglad.polozenia_pol(p.sciezka, pola, audyt.get("strony_ocr") or []),
                       "uwagi": _uwagi(p, audyt)}
            if sprawa is not None:
                _zapisz(sprawa, p)
            p.stan = "gotowe"
        except Exception:
            log.exception("[błąd] %s: przetwarzanie w sprawie nie powiodło się", p.plik)
            p.stan, p.blad = "blad", "Nie udało się przetworzyć pliku"
        finally:
            p.koniec = time.time()

    def czekaj(self, sprawa: Sprawa, limit_s: float = 600) -> None:
        koniec = time.time() + limit_s
        while not sprawa.gotowa and time.time() < koniec:
            time.sleep(0.2)

    def pobierz(self, id_: str) -> Sprawa | None:
        self.sprzataj()
        with self._blokada:
            return self._sprawy.get(id_)

    def usun(self, id_: str) -> bool:
        with self._blokada:
            sprawa = self._sprawy.pop(id_, None)
        if sprawa:
            shutil.rmtree(sprawa.katalog, ignore_errors=True)
        return sprawa is not None

    def sprzataj(self) -> None:
        teraz = time.time()
        with self._blokada:
            stare = [s.id for s in self._sprawy.values() if teraz - s.utworzona > CZAS_ZYCIA_S]
            nadmiar = sorted(self._sprawy.values(), key=lambda s: s.utworzona)[:max(0, len(self._sprawy) - MAKS_SPRAW)]
            stare += [s.id for s in nadmiar if s.gotowa]
        for id_ in set(stare):
            self.usun(id_)


def json_pliku(p: PlikSprawy, tryb_obcych: str = "pusty_obiekt") -> str | None:
    """Treść pliku .json taka jak w ./output: JSON UZP; dla obcego {} / pusty / brak pliku (config/aplikacja.yaml)."""
    dane = (p.wynik or {}).get("json") or {}
    if dane:
        return json.dumps(dane, ensure_ascii=False, indent=2)
    return {"pusty_obiekt": "{}", "pusty_plik": ""}.get(tryb_obcych)


def zip_sprawy(sprawa: Sprawa, tryb_obcych: str = "pusty_obiekt", ujednolicaj: bool = True) -> bytes:
    """ZIP z plikami .json całej sprawy, z ujednoliceniem nazw jak w przebiegu wsadowym (sprawa.py)."""
    from .sprawa import ujednolic_sprawy
    with tempfile.TemporaryDirectory(prefix="odw-zip-") as tmp:
        kat = Path(tmp) / "sprawa"
        kat.mkdir()
        nazwy: set[str] = set()
        for p in sprawa.pliki:
            if p.stan != "gotowe" and not (p.wynik and p.stan == "blad"):
                continue
            tresc = json_pliku(p, tryb_obcych)
            if tresc is None:
                continue
            nazwa = p.json_nazwa if p.json_nazwa not in nazwy else f"{p.nr}_{p.json_nazwa}"
            nazwy.add(nazwa)
            (kat / nazwa).write_text(tresc, encoding="utf-8")
        if ujednolicaj:
            ujednolic_sprawy(kat)
        bufor = io.BytesIO()
        with zipfile.ZipFile(bufor, "w", zipfile.ZIP_DEFLATED) as z:
            for plik in sorted(kat.iterdir()):
                z.write(plik, plik.name)
        return bufor.getvalue()
