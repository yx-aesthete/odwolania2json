"""OCR: strona bez tekstu idzie do Tesseracta; brak Tesseracta nie wywraca programu."""
from pathlib import Path

import pytest

from odwolania2json import pdftext

SKAN = Path(__file__).resolve().parents[1] / "data/raw/uzp/szablon-aplikacja/input/case1/przyklad odwolanie.pdf"


def test_bez_ocr_skan_daje_puste_strony(monkeypatch):
    if not SKAN.exists():
        pytest.skip("brak danych UZP (scripts/pobierz_dane.sh)")
    monkeypatch.setenv("OCR", "0")
    dok = pdftext.wczytaj(SKAN)
    assert dok.strony and dok.strony_ocr == ()
    assert len(dok.tekst.strip()) < pdftext.MIN_ZNAKOW * len(dok.strony)


def test_blad_ocr_jednej_strony_nie_zatrzymuje(monkeypatch):
    monkeypatch.setattr(pdftext, "ocr_dostepny", lambda: True)
    def zly(_s, i):
        if i == 0:
            raise RuntimeError("zepsuta")
        return "tekst ze skanu " * 5
    monkeypatch.setattr(pdftext, "_ocr_strony", zly)
    strony = ["", "", "pełna strona z warstwą tekstową, dość długa, by nie iść do OCR"]
    zrobione = pdftext._uzupelnij_ocr(Path("x.pdf"), strony)
    assert zrobione == (2,)
    assert strony[0] == "" and strony[1].startswith("tekst ze skanu")


def test_jakosc_tekstu():
    assert pdftext.jakosc("Warszawa, dnia 3 marca 2026 r. Odwołujący: Alfa sp. z o.o. ul. Długa 5") > 0.75
    assert pdftext.jakosc("ÿþ ¤ ¦ § ¨ © ª « ¬ ® ¯") < 0.2


def test_slaba_strona_bierze_tekst_z_pdfium(monkeypatch):
    dobry = "Potwierdzenie przelewu z rachunku nr 12 na rachunek Urzędu, kwota 100,00 zł, dnia 2 marca"
    monkeypatch.setattr(pdftext, "_strony_pdfium", lambda _s: [dobry, "x"])
    wynik = pdftext._lepsze_strony(Path("x.pdf"), ["ÿþ ¤ ¦ § ¨ ©", "Pełna strona z tekstem i słowami na miejscu, w porządku."])
    assert wynik[0] == dobry and wynik[1].startswith("Pełna")


def test_kolejnosc_silnikow_ocr_model_potem_tesseract(monkeypatch):
    monkeypatch.setenv("OCR_SILNIKI", "model,tesseract")
    monkeypatch.setattr(pdftext, "_ocr_modelem", lambda s, i: (_ for _ in ()).throw(RuntimeError("brak klucza")))
    monkeypatch.setattr(pdftext, "_ocr_strony", lambda s, i: "tekst z tesseracta " * 5)
    strony = [""]
    assert pdftext._uzupelnij_ocr(Path("x.pdf"), strony) == (1,)
    assert strony[0].startswith("tekst z tesseracta")
    monkeypatch.setattr(pdftext, "_ocr_modelem", lambda s, i: "tekst z modelu " * 5)
    strony = [""]
    pdftext._uzupelnij_ocr(Path("x.pdf"), strony)
    assert strony[0].startswith("tekst z modelu")


def test_naglowek_strony_do_wykrycia_obrotu():
    from odwolania2json.pdftext import ma_naglowek
    assert ma_naglowek("Olsztyn, 5 listopada 2026 r.\n\nPEŁNOMOCNICTWO\n")
    assert ma_naglowek("BANK X S.A.\nPOTWIERDZENIE WYKONANIA PRZELEWU")
    # skan do góry nogami „przeczytany” bez błędu: zaczyna od środka zdania, bez tytułu i daty
    assert not ma_naglowek("Firma sp. z o.o., KRS 0000420318, ul. Lubelska 30, reprezentowana przez Prezesa, "
                           "udziela pełnomocnictwa radcy prawnemu")
