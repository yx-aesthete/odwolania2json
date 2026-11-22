"""Wspólne ustawienia testów: bez lokalnego pliku .env (klucz API i model z niego nie wpływają na wyniki testów)."""
import pytest


@pytest.fixture(autouse=True)
def _bez_lokalnego_env(monkeypatch):
    monkeypatch.setenv("O2J_BEZ_ENV", "1")


@pytest.fixture(autouse=True)
def _wyniki_www_do_tmp(monkeypatch, tmp_path):
    """Z36: podgląd WWW zapisuje do ./output; w testach do katalogu tymczasowego, nie do repozytorium."""
    monkeypatch.setenv("WEB_OUTPUT", str(tmp_path / "output"))
    monkeypatch.setenv("WEB_AUDIT", str(tmp_path / "audit"))


from pathlib import Path as _Path

KONTROLNY = _Path(__file__).resolve().parent / "kontrolny" / "input"
# testy na pismach UZP z tests/kontrolny: pomijane, gdy katalogu nie ma (np. w eksporcie do publicznego repo)
wymaga_kontrolnego = pytest.mark.skipif(not KONTROLNY.is_dir(), reason="brak tests/kontrolny (dane spoza eksportu)")


def pdf_tekstowy(sciezka: _Path, linie: list[str]) -> _Path:
    """Mały PDF z warstwą tekstową (Helvetica, ASCII), bez zależności od danych i bibliotek do tworzenia PDF."""
    tresc = "BT /F1 12 Tf 50 780 Td 16 TL " + " ".join(
        "(" + l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") '" for l in linie) + " ET"
    obiekty = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 5 0 R >> >> "
        "/Contents 4 0 R >>",
        f"<< /Length {len(tresc)} >>\nstream\n{tresc}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    dane, przes = b"%PDF-1.4\n", []
    for i, o in enumerate(obiekty, 1):
        przes.append(len(dane))
        dane += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    xref = len(dane)
    dane += f"xref\n0 {len(obiekty) + 1}\n0000000000 65535 f \n".encode()
    dane += "".join(f"{p:010d} 00000 n \n" for p in przes).encode()
    dane += f"trailer\n<< /Size {len(obiekty) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    sciezka.write_bytes(dane)
    return sciezka


LINIE_PRZELEWU = ["Potwierdzenie wykonania przelewu", "Data operacji: 03.03.2026", "Kwota: 7 500,00 PLN",
                  "Z rachunku: PL61 1090 1014 0000 0712 1981 2874",
                  "Na rachunek: 60 1010 1010 0081 3622 3100 0000",
                  "Tytul: wpis od odwolania ZP/1/2026", "Odbiorca: Urzad Zamowien Publicznych"] * 3
