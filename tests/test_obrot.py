"""Z43: obrót skanu tylko, gdy wersja obrócona jest wyraźnie lepsza; 90° i 270° wykrywane z obrazu."""
from pathlib import Path

from odwolania2json import pdftext

KORZEN = Path(__file__).resolve().parents[1]
DOBRY = ("Warszawa, 3 marca 2026 r.\nPEŁNOMOCNICTWO\nAlfa sp. z o.o. udziela pełnomocnictwa radcy prawnemu Janowi "
         "Kowalskiemu do reprezentowania przed Krajową Izbą Odwoławczą w postępowaniu odwoławczym. Mocodawca.")


def _skan(tmp_path, obrot: int) -> Path:
    """PDF bez warstwy tekstowej z obrazem prawdziwej strony (opcjonalnie obróconej)."""
    from conftest import LINIE_PRZELEWU, pdf_tekstowy
    # linie na całą szerokość strony, jak w prawdziwym piśmie (bez danych spoza repo)
    linie = [(l + " ") * 3 for l in LINIE_PRZELEWU * 2]
    pdf = pdf_tekstowy(tmp_path / f"tekst_{obrot}.pdf", [l[:95] for l in linie])
    obraz = pdftext._obraz_strony(pdf, 0, 100).convert("RGB").rotate(obrot, expand=True)
    wyj = tmp_path / f"skan_{obrot}.pdf"
    obraz.save(wyj, "PDF", resolution=100)
    return wyj


def test_prosty_dokument_nie_jest_obracany_mimo_zmyslonej_daty(tmp_path, monkeypatch):
    skan = _skan(tmp_path, 0)
    prosta = "Alfa sp. z o.o. udziela pełnomocnictwa radcy prawnemu Janowi Kowalskiemu do reprezentowania przed KIO."
    pytania = []

    def atrapa(sciezka, indeks, obrot=0):
        pytania.append(obrot)
        return "Kraków, 12.05.2026\nlorem ipsum dolor sit amet" if obrot == 180 else prosta
    monkeypatch.setattr(pdftext, "_ocr_modelem", atrapa)
    strony = [prosta]
    pdftext._sprawdz_obrot(skan, strony, [1])
    assert strony == [prosta] and 180 in pytania      # sprawdzone, ale odrzucone (nie lepsze od prostej)


def test_dokument_obrocony_o_90_dostaje_obrot(tmp_path, monkeypatch):
    skan = _skan(tmp_path, 90)
    assert pdftext.tekst_pionowy(pdftext._obraz_strony(skan, 0, 100))
    assert not pdftext.tekst_pionowy(pdftext._obraz_strony(_skan(tmp_path, 0), 0, 100))

    def atrapa(sciezka, indeks, obrot=0):
        return DOBRY if obrot == 270 else "śmieci bez sensu xx yy"
    monkeypatch.setattr(pdftext, "_ocr_modelem", atrapa)
    strony = ["śmieci bez sensu xx yy"]
    pdftext._sprawdz_obrot(skan, strony, [1])
    assert strony == [DOBRY]
