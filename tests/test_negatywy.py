"""Regresja: dokumenty obce z danych UZP (dane/negatywne i PDF-y bez referencji w sprawach) nie dostają typu."""
from pathlib import Path

import pytest

from odwolania2json.klasy import UstawieniaKlasyfikacji, rozpoznaj, wczytaj_klasy
from odwolania2json.pdftext import wczytaj

KORZEN = Path(__file__).resolve().parents[1]
DANE = KORZEN / "data/raw/uzp/dane"
ALIASY = {"potwierdzenie_przelewu": "przelew"}  # starsza nazwa pliku w danych UZP


def _ma_referencje(pdf: Path) -> bool:
    gold = pdf.with_suffix(".json")
    if not gold.exists():
        gold = pdf.with_name(ALIASY.get(pdf.stem, pdf.stem) + ".json")
    return gold.exists() and gold.read_text(encoding="utf-8").strip() not in ("", "{}")


def _obce() -> list[Path]:
    """Obce: dane/negatywne oraz PDF-y w sprawach bez (niepustej) referencji o tej samej nazwie."""
    if not DANE.exists():
        return []
    pliki = sorted((DANE / "negatywne").glob("*.pdf"))
    for sprawa in sorted(DANE.glob("przyklad_*")):
        pliki += [p for p in sorted(sprawa.glob("*.pdf")) if not _ma_referencje(p)]
    return pliki


@pytest.mark.skipif(not DANE.exists(), reason="brak danych UZP (scripts/pobierz_dane.sh)")
@pytest.mark.parametrize("pdf", _obce(), ids=lambda p: f"{p.parent.name}/{p.name}")
def test_obcy_bez_typu(pdf, monkeypatch):
    monkeypatch.setenv("OCR", "0")
    klasy = wczytaj_klasy(KORZEN / "config/klasy")
    r = rozpoznaj(wczytaj(pdf).tekst, klasy, UstawieniaKlasyfikacji.z_pliku(KORZEN / "config/aplikacja.yaml"))
    assert r.klasa is None, (r.punkty, r.trafienia)
