"""Odporność przebiegu: zepsute pliki (tekst z rozszerzeniem .pdf, PDF 0 B, PDF zaszyfrowany) obok dobrej sprawy
nie przerywają przebiegu; za zepsuty plik jest {} i linia w logu."""
import subprocess
import sys
from pathlib import Path

import pytest
from pypdf import PdfReader, PdfWriter

KORZEN = Path(__file__).resolve().parents[1]
DOBRA = KORZEN / "tests/kontrolny/input/case06"


def _zepsute(katalog: Path) -> None:
    (katalog / "tekst.pdf").write_text("to nie jest PDF", encoding="utf-8")
    (katalog / "pusty.pdf").write_bytes(b"")
    w = PdfWriter()
    for strona in PdfReader(str(next(DOBRA.glob("przelew*.pdf")))).pages:
        w.add_page(strona)
    w.encrypt("tajne")
    with open(katalog / "zaszyfrowany.pdf", "wb") as f:
        w.write(f)


@pytest.mark.skipif(not DOBRA.exists(), reason="brak zbioru kontrolnego")
def test_cli_zepsute_pliki_obok_dobrej_sprawy(tmp_path):
    wej = tmp_path / "input" / "sprawa"
    wej.mkdir(parents=True)
    for p in DOBRA.glob("*.pdf"):
        (wej / p.name).write_bytes(p.read_bytes())
    _zepsute(wej)
    wyj = tmp_path / "output"
    r = subprocess.run([sys.executable, "-m", "odwolania2json", "--input", str(tmp_path / "input"), "--output", str(wyj),
                        "--audit", str(tmp_path / "audit"), "--bez-llm"],
                       cwd=KORZEN, env={"PYTHONPATH": str(KORZEN / "src"), "PATH": "", "OCR": "0", "O2J_BEZ_ENV": "1"},
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    for zly in ("tekst", "pusty", "zaszyfrowany"):
        assert (wyj / "sprawa" / f"{zly}.json").read_text(encoding="utf-8") == "{}"
    assert (wyj / "sprawa" / "odwolanie_nr_6.json").read_text(encoding="utf-8") != "{}"


@pytest.mark.skipif(not DOBRA.exists(), reason="brak zbioru kontrolnego")
def test_web_zepsute_pliki(tmp_path, monkeypatch):
    monkeypatch.setenv("BEZ_LLM", "1")
    monkeypatch.setenv("OCR", "0")
    from fastapi.testclient import TestClient

    from odwolania2json.web import app
    _zepsute(tmp_path)
    pliki = [("pliki", (p.name, p.read_bytes(), "application/pdf")) for p in sorted(tmp_path.glob("*.pdf"))]
    pliki.append(("pliki", ("odwolanie.pdf", next(DOBRA.glob("odwolanie*.pdf")).read_bytes(), "application/pdf")))
    r = TestClient(app).post("/api/przetworz", files=pliki)
    assert r.status_code == 200
    wyniki = {w["plik"]: w for w in r.json()}
    assert wyniki["odwolanie.pdf"]["klasa"] == "odwolanie"
    for zly in ("tekst.pdf", "pusty.pdf", "zaszyfrowany.pdf"):
        assert wyniki[zly].get("json", {}) == {}


def test_rachunek_znany_poprawia_zgubione_cyfry_ocr():
    from odwolania2json.normalizacja import rachunek_znany
    assert rachunek_znany("60 1010 10081 3622 3100 0000") == "60101010100081362231000000"   # 3 cyfry zgubione
    assert rachunek_znany("PL61 1030 1508 1403 0456 9635 6736") == "PL61103015081403045696356736"  # jak w dokumencie
    assert rachunek_znany("61 1030 1508 1403 0456 9635") is None        # obcy rachunek z błędem: nie zgadujemy
    assert rachunek_znany("123") is None


def test_przelew_rachunek_odbiorcy_z_bledem_ocr():
    from pathlib import Path
    from odwolania2json.potok import Potok
    potok = Potok(Path(__file__).resolve().parents[1] / "config/klasy", uzyj_llm=False)
    t = ("Bank Testowy\nPotwierdzenie transakcji\nOpis\nwpis od odwołania - postępowanie nr ZP.1.2026\nKwota\n7 500,00 PLN\n"
         "Data transakcji\n11.09.2026\nDane nadawcy\nNazwa i adres\nFIRMA SP. Z O.O., UL. DŁUGA 1, 00-001 WARSZAWA\n"
         "Numer rachunku\nPL62 2170 0008 9152 5017 5661 7062\nDane odbiorcy\nNazwa i adres\n"
         "Urząd Zamówień Publicznych, ul. Postępu 17A, 02-676 Warszawa\nNumer rachunku\n60 1010 10081 3622 3100 0000\n")
    w = potok.przetworz_tekst(t)
    assert w.dane["przelew_bankowy"]["na_rachunek"] == "60101010100081362231000000"
    assert w.dane["przelew_bankowy"]["z_rachunku"] == "PL62217000089152501756617062"


def test_napraw_znaki_rozbite_diakrytyki_i_ligatury():
    from odwolania2json.pdftext import napraw_znaki, rozbite_znaki
    t = "Odwoluja˛cy: S\n´\nla˛skie Mlyny Zboz˙owe S.A.\nczynnos´ci, Z\n˙\no´lkiewski, „Dostawa ﬁltrów i ﬂokulantów”"
    assert rozbite_znaki(t) >= 3
    w = napraw_znaki(t)
    assert "Odwolujący: Śląskie Mlyny Zbożowe S.A." in w
    assert "czynności, Żólkiewski" in w and "filtrów i flokulantów" in w
    assert napraw_znaki("Wnoszę o: 7 500,00 zł") == "Wnoszę o: 7 500,00 zł"


def test_odmiana_obocznosci_e_a_i_wilk():
    from odwolania2json.normalizacja import mianownik_zalezny
    assert mianownik_zalezny("Marka Gołębia") == "Marek Gołąb"
    assert mianownik_zalezny("Szymona Dęba") == "Szymon Dąb"
    assert mianownik_zalezny("Bartosza Wilka") == "Bartosz Wilk"
    assert mianownik_zalezny("Adama Kurka") == "Adam Kurek"


def test_identyfikatory_krs_bez_zer_regon_zlamany_email_zlamany():
    from odwolania2json.normalizacja import email, krs, regon
    assert krs("KRS nr 123456") == "0000123456" and krs("0000123456") == "0000123456" and krs("12") is None
    assert regon("1234\n56789") == "123456789" and regon("12345678") is None
    assert email("e-mail: a.nowak@nowak-\nlegal.example") == "a.nowak@nowak-legal.example"


def test_przelew_wydruk_kolumnowy():
    from pathlib import Path
    from odwolania2json.potok import Potok
    potok = Potok(Path(__file__).resolve().parents[1] / "config/klasy", uzyj_llm=False)
    t = ("Bank Testowy\nHistoria rachunku – wydruk pojedynczej operacji\nData operacji\nData księgowania\nTyp operacji\n"
         "Kwota operacji\nSaldo po operacji\n03.02.2026\n04.02.2026\nPrzelew wychodzący\n-7 500,00 PLN\n1 000,00 PLN\n"
         "Rachunek nadawcy\nRachunek odbiorcy\nOdbiorca\nPL61 1090 1014 0000 0712 1981\n2874\n60 1010 1010 0081 3622 3100\n0000\n"
         "Urząd Zamówień Publicznych\nTytuł\nIdentyfikator transakcji\nWpis od odwołania ZP/1/2026 Firma\nsp. z o.o.\n"
         "12320260203000111\nDokument wygenerowany elektronicznie.\n")
    w = potok.przetworz_tekst(t).dane["przelew_bankowy"]
    assert w["data_operacji"] == "2026-02-03" and w["kwota"] == 7500.0
    assert w["z_rachunku"] == "PL61109010140000071219812874" and w["na_rachunek"] == "60101010100081362231000000"
    assert w["numer_transakcji"] == "12320260203000111"
    assert w["tytul"] == "Wpis od odwołania ZP/1/2026 Firma sp. z o.o"   # bez_kropki jak w referencjach


def test_data_slownie_i_data_przy_podpisie():
    from odwolania2json.normalizacja import data_iso
    assert data_iso("dnia szóstego października 2026 r.") == "2026-10-06"
    assert data_iso("dwudziestego pierwszego marca 2026") == "2026-03-21"
    from pathlib import Path
    from odwolania2json.potok import Potok
    potok = Potok(Path(__file__).resolve().parents[1] / "config/klasy", uzyj_llm=False)
    t = ("Prezes Krajowej Izby Odwoławczej\nul. Postępu 17A\n02-676 Warszawa\nOdwołujący: Firma sp. z o.o., ul. Długa 1, "
         "00-001 Warszawa\nZamawiający: Gmina Testowa, ul. Krótka 2, 00-002 Testowo\nODWOŁANIE\nWnoszę odwołanie wobec "
         "czynności Zamawiającego polegającej na odrzuceniu oferty.\nMając na uwadze powyższe, wnoszę jak na wstępie.\n"
         "Szczecin, 3 listopada 2026 r.\n r. pr. Hanna Kurowska\n")
    d = potok.przetworz_tekst(t).dane["OdwolanieKIO"]
    assert d["data"] is None and d["miejscowosc"] is None


def test_reprezentacja_przez_organ_to_nie_pelnomocnik():
    from pathlib import Path
    from odwolania2json.potok import Potok
    potok = Potok(Path(__file__).resolve().parents[1] / "config/klasy", uzyj_llm=False)
    t = ("Lublin, 02.10.2026\nPrezes Krajowej Izby Odwoławczej\nOdwołujący: Testtrans sp.k., ul. Długa 1, 20-001 Lublin, "
         "KRS 9990000011, e-mail: biuro@testtrans.example – działający przez\nkomplementariusza Testtrans sp. z o.o., "
         "reprezentowanego przez Prezesa Zarządu Jana Kota\nZamawiający: Gmina Testowa, ul. Krótka 2, 00-002 Testowo\n"
         "ODWOŁANIE\n")
    o = potok.przetworz_tekst(t).dane["Odwolujacy"][0]
    assert o["przez-pelnomocnika"] == 0 and o["pelnomocnik"]["mail"] is None


def test_jedna_linia_bez_anonimizacji_przecinka_i_etykiety_adresu():
    from odwolania2json.normalizacja import jedna_linia
    assert jedna_linia("Kancelaria ████ Adwokacka,") == "Kancelaria Adwokacka"
    assert jedna_linia("Adres do doręczeń: Kancelaria Radcy Prawnego Jan Kot") == "Kancelaria Radcy Prawnego Jan Kot"
    assert jedna_linia("Gmina Testowa ■■■") == "Gmina Testowa"


def test_pdf_ktorego_pypdf_nie_otworzy_czytany_przez_pdfium(monkeypatch):
    """Z40: np. PDF szyfrowany AES bez pakietu cryptography — tekst z PDFium, nie pusty dokument."""
    from pathlib import Path
    from odwolania2json import pdftext
    pdf = next((Path(__file__).parent / "kontrolny/input").rglob("przelew*.pdf"))

    def zly_reader(*a, **k):
        raise RuntimeError("cryptography>=3.1 is required for AES algorithm")
    monkeypatch.setattr(pdftext, "PdfReader", zly_reader)
    d = pdftext.wczytaj(pdf)
    assert len(d.strony) >= 1 and len(d.tekst) > 100


def test_plik_uszkodzony_daje_pusty_dokument(tmp_path):
    from odwolania2json import pdftext
    zly = tmp_path / "zly.pdf"
    zly.write_bytes(b"to nie jest PDF")
    assert pdftext.wczytaj(zly).strony == ()


def test_historia_rachunku_kwota_nie_z_daty_i_data_operacji_z_kolumny():
    from pathlib import Path
    from odwolania2json.normalizacja import kwota
    from odwolania2json.potok import Potok
    assert kwota("30-03-2026") is None and kwota("2026-03-30") is None
    assert kwota("-7 500,00 PLN") == 7500.0
    potok = Potok(Path(__file__).resolve().parents[1] / "config/klasy", uzyj_llm=False)
    rach = "Rachunek nadawcy\nPL61 1090 1014 0000 0712 1981 2874\nRachunek odbiorcy\n60 1010 1010 0081 3622 3100 0000\n"
    t1 = ("Historia rachunku\nData księgowania\nData operacji\nOpis\nKwota\n31-03-2026\n30-03-2026\n"
          "Wpis od odwołania ZP/1/2026\n-7 500,00 PLN\n" + rach)
    w = potok.przetworz_tekst(t1).dane["przelew_bankowy"]
    assert w["data_operacji"] == "2026-03-30" and w["kwota"] == 7500.0
    t2 = ("Historia rachunku\nData operacji\nData księgowania\nOpis\nKwota\n30-03-2026\n31-03-2026\n"
          "Wpis od odwołania ZP/1/2026\n-7 500,00 PLN\n" + rach)
    w = potok.przetworz_tekst(t2).dane["przelew_bankowy"]
    assert w["data_operacji"] == "2026-03-30" and w["kwota"] == 7500.0


def test_nazwisko_na_a_w_mianowniku_po_tytule_zostaje():
    from odwolania2json.normalizacja import mianownik_zalezny
    assert mianownik_zalezny("Jan Kępa") == "Jan Kępa" and mianownik_zalezny("Jerzy Sowa") == "Jerzy Sowa"
    assert mianownik_zalezny("Jana Nowaka") == "Jan Nowak" and mianownik_zalezny("Marka Gołębia") == "Marek Gołąb"
