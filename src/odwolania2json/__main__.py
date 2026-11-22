"""CLI: python -m odwolania2json --input ./input --output ./output [--audit ./audit]

Dla każdego PDF z input/<sprawa>/ zapisuje output/<sprawa>/<ta sama nazwa>.json.
Dokument spoza znanych klas -> „nie dopasowano typu” w logu i plik z {} (domyślnie), 0 B albo brak pliku (config/aplikacja.yaml: obcy).
Cytaty i metoda dla każdego pola -> audit/<sprawa>/<nazwa>.json (poza output, żeby nie mylić oceny).
"""
from __future__ import annotations

import argparse
import json
import os
import logging
import sys
import time
from pathlib import Path

import yaml

from .potok import Potok, przetworz_bezpiecznie

KORZEN = Path(__file__).resolve().parents[2]


OBCY_TRYBY = ("pusty_obiekt", "pusty_plik", "brak_pliku")
ZAPIS_OBCEGO = {"pusty_obiekt": "{}", "pusty_plik": ""}


def tryb_obcych(sciezka: Path = KORZEN / "config" / "aplikacja.yaml") -> str:
    konf = yaml.safe_load(sciezka.read_text(encoding="utf-8")) or {} if sciezka.exists() else {}
    tryb = (os.environ.get("OBCY") or konf.get("obcy") or "pusty_obiekt").strip()
    if tryb not in OBCY_TRYBY:
        logging.getLogger("odwolania2json").warning("nieznane ustawienie obcy=%r, używam pusty_obiekt", tryb)
        return "pusty_obiekt"
    return tryb


def bezpieczne_wyjscie() -> None:
    """Polskie znaki w logu nie mogą przerwać przebiegu, gdy stdout/stderr ma stronę kodową bez nich
    (np. przekierowanie do pliku w Windows z cp1252): znak spoza kodowania zapisuje się jako \\uXXXX."""
    for strumien in (sys.stdout, sys.stderr):
        try:
            strumien.reconfigure(errors="backslashreplace")
        except (AttributeError, ValueError):  # strumień podmieniony (np. w testach) albo zamknięty
            pass


def _strony_bez_tekstu(pdf: Path) -> tuple[int, int]:
    """(liczba stron, liczba stron bez warstwy tekstowej) — szybki odczyt pypdf, bez OCR."""
    try:
        from pypdf import PdfReader
        strony = PdfReader(str(pdf)).pages
        return len(strony), sum(1 for p in strony if len((p.extract_text() or "").strip()) < 20)
    except Exception:  # uszkodzony PDF: na koniec kolejki, obsłuży go zwykła ścieżka
        return 0, 0


def kolejnosc(pdfy: list[Path]) -> list[Path]:
    """Najpierw PDF z warstwą tekstową (szybkie), potem skany wielostronicowe, na końcu jednostronicowe:
    gdy budżet czasu się skończy, bez OCR zostają dokumenty z najmniejszą liczbą pól."""
    def klucz(p: Path) -> tuple[int, int]:
        n, bez = _strony_bez_tekstu(p)
        # Z34: po tekście najpierw skany wielostronicowe (odwołania, ok. 20 pól), na końcu jednostronicowe
        # (przelewy, ok. 6 pól): gdy budżet się skończy, tracimy mniej pól
        return (0 if bez == 0 else 1 if n > 1 else 2), 0
    return sorted(pdfy, key=klucz)   # sortowanie stabilne: w grupie kolejność alfabetyczna


def main(argv: list[str] | None = None) -> int:
    bezpieczne_wyjscie()
    ap = argparse.ArgumentParser(prog="odwolania2json", description="PDF sprawy KIO -> JSON w formacie UZP")
    ap.add_argument("--input", type=Path, default=KORZEN / "input")
    ap.add_argument("--output", type=Path, default=KORZEN / "output")
    ap.add_argument("--audit", type=Path, default=KORZEN / "audit")
    ap.add_argument("--klasy", type=Path, default=KORZEN / "config" / "klasy")
    ap.add_argument("--klasy-dodatkowe", type=Path, action="append", default=[],
                    help="dodatkowy katalog klas, np. config/klasy-demo (można powtórzyć)")
    ap.add_argument("--bez-llm", action="store_true", help="same reguły, bez modelu językowego")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    from .llm import wczytaj_env
    wczytaj_env()  # .env także przy run.bat / start.bat / python -m
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(message)s")
    log = logging.getLogger("odwolania2json")

    if not a.input.is_dir():
        log.error("Brak katalogu wejściowego: %s", a.input)
        return 2
    potok = Potok(a.klasy, uzyj_llm=not a.bez_llm, dodatkowe=a.klasy_dodatkowe)
    pdfy = kolejnosc(sorted(p for p in a.input.rglob("*") if p.suffix.lower() == ".pdf"))
    if not pdfy:
        log.warning("Brak plików PDF w %s", a.input)
    obcy = tryb_obcych()
    t0 = time.time()
    from . import budzet
    maks = budzet.start()  # MAKS_CZAS_S: po wyczerpaniu reszta samymi regułami (bez OCR i modelu)
    if maks != float("inf"):
        log.info("Budżet czasu przebiegu: %.0f s (MAKS_CZAS_S)", maks)
    def jeden(pdf: Path) -> None:
        wzgl = pdf.relative_to(a.input).with_suffix(".json")
        wynik = przetworz_bezpiecznie(potok, pdf, log)
        out = a.output / wzgl
        if wynik.dane or obcy in ZAPIS_OBCEGO:
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(wynik.dane, ensure_ascii=False, indent=2) if wynik.dane else ZAPIS_OBCEGO[obcy],
                           encoding="utf-8")
        aud = a.audit / wzgl
        aud.parent.mkdir(parents=True, exist_ok=True)
        aud.write_text(json.dumps(wynik.audyt, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("%-60s -> %s", str(pdf.relative_to(a.input)), wynik.klasa or f"nie dopasowano typu ({ {'pusty_obiekt': 'JSON {}', 'pusty_plik': 'plik 0 B'}.get(obcy, 'bez pliku JSON') })")

    # pliki równolegle (PLIKI_WATKI, domyślnie 8): skany czekają głównie na API; równoczesne zapytania i tak
    # ogranicza wspólny OGRANICZNIK (API_WATKI). Kolejność zgłaszania = kolejność z `kolejnosc()`; JSON każdego
    # pliku zapisywany od razu po nim. PLIKI_WATKI=1: po kolei jak wcześniej.
    watki = max(1, int(os.environ.get("PLIKI_WATKI", "8") or 8))
    if watki == 1:
        for pdf in pdfy:
            jeden(pdf)
    else:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(watki, thread_name_prefix="plik") as ex:
            for f in [ex.submit(jeden, pdf) for pdf in pdfy]:
                f.result()
    from .sprawa import ujednolic_sprawy, wlaczone
    if wlaczone(KORZEN / "config" / "aplikacja.yaml"):
        ujednolic_sprawy(a.output)  # te same nazwy w pismach sprawy: wariant z polskimi znakami (błędy OCR)
    log.info("Gotowe: %d plików w %.1f s", len(pdfy), time.time() - t0)
    from .pdftext import LICZNIK_OCR
    czesci = [potok.llm.podsumowanie()] if potok.llm is not None else []
    if LICZNIK_OCR.strony or LICZNIK_OCR.bledy or LICZNIK_OCR.z_pamieci:
        czesci.append(LICZNIK_OCR.opis())  # ekstrakcja i OCR liczone osobno (OCR ma własnego klienta)
    if czesci:
        log.info("Podsumowanie: %s", "; ".join(czesci))
    return 0


if __name__ == "__main__":
    sys.exit(main())
