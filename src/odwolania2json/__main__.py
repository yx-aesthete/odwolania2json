"""CLI: python -m odwolania2json --input ./input --output ./output [--audit ./audit]

Dla każdego PDF z input/<sprawa>/ zapisuje output/<sprawa>/<ta sama nazwa>.json.
Dokument spoza znanych klas -> pusty plik .json (wymóg README UZP).
Cytaty i metoda dla każdego pola -> audit/<sprawa>/<nazwa>.json (poza output, żeby nie mylić oceny).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from .potok import Potok

KORZEN = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="odwolania2json", description="PDF sprawy KIO -> JSON w formacie UZP")
    ap.add_argument("--input", type=Path, default=KORZEN / "input")
    ap.add_argument("--output", type=Path, default=KORZEN / "output")
    ap.add_argument("--audit", type=Path, default=KORZEN / "audit")
    ap.add_argument("--klasy", type=Path, default=KORZEN / "config" / "klasy")
    ap.add_argument("--bez-llm", action="store_true", help="same reguły, bez modelu językowego")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(message)s")
    log = logging.getLogger("odwolania2json")

    if not a.input.is_dir():
        log.error("Brak katalogu wejściowego: %s", a.input)
        return 2
    potok = Potok(a.klasy, uzyj_llm=not a.bez_llm)
    pdfy = sorted(p for p in a.input.rglob("*") if p.suffix.lower() == ".pdf")
    if not pdfy:
        log.warning("Brak plików PDF w %s", a.input)
    t0 = time.time()
    for pdf in pdfy:
        wzgl = pdf.relative_to(a.input).with_suffix(".json")
        wynik = potok.przetworz(pdf)
        out = a.output / wzgl
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(wynik.dane, ensure_ascii=False, indent=2) if wynik.dane else "", encoding="utf-8")
        aud = a.audit / wzgl
        aud.parent.mkdir(parents=True, exist_ok=True)
        aud.write_text(json.dumps(wynik.audyt, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("%-60s -> %s", str(pdf.relative_to(a.input)), wynik.klasa or "obcy (pusty JSON)")
    log.info("Gotowe: %d plików w %.1f s", len(pdfy), time.time() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
