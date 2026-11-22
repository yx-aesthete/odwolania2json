"""Przelew po OCR (dane fikcyjne): zgubiona etykieta tytułu i daty, stopka banku z błędem na początku linii,
rachunek znany z config/znane_rachunki.yaml jako rachunek odbiorcy niezależnie od kolejności w druku; imię „Ewie”."""
from pathlib import Path

import pytest

from odwolania2json.potok import Potok

KLASY = Path(__file__).resolve().parents[1] / "config/klasy"
ZNANY = "60 1010 1010 0081 3622 3100 0000"   # rachunek z config/znane_rachunki.yaml
INNY = "11 1140 2004 0000 3102 7654 3210"


@pytest.fixture(scope="module")
def potok():
    return Potok(KLASY, uzyj_llm=False)


def _przelew(potok, tekst):
    return potok.przetworz_tekst(tekst).dane["przelew_bankowy"]


def test_tytul_po_tresci_stopka_z_bledem_i_data_bez_etykiety(potok):
    # OCR: „Tytut:”, „Dala operacji”, data operacji nieczytelna, stopka „Dokumentj jest wydrukiem komputerowymi it nie wymaga…”
    t = ("Bank Fikcyjny\nData wydruku: 2026-01-15 godz. 08:00\nData Opis Kwota\n"
         "Dala operacji PRZELEW ELIXIR - ONLINE -9 000,00 PLN\n"
         f"D20-0I-I5 Z rachunku: {INNY}\nNa rachunek: {ZNANY}\nUrząd Testowy\n"
         "Tytut: Wpis od odwołania, ZP.900.1.2026, MUZEUM TESTOWE W TESTOWIE\n"
         "Dokumentj jest wydrukiem komputerowymi it nie wymaga dodatkowych podpisów oraz stempla bankowego.\n"
         "Bank Fikcyjny S.A. z siedzibą w Miastowie, ul. Testowa 1\n")
    w = _przelew(potok, t)
    assert w["tytul"] == "Wpis od odwołania, ZP.900.1.2026, MUZEUM TESTOWE W TESTOWIE"
    assert w["data_operacji"] == "2026-01-15" and w["kwota"] == 9000.0


def test_stopka_z_bledem_ocr_nie_wchodzi_do_tytulu(potok):
    t = (f"Bank Fikcyjny\nZ rachunku: {INNY}\nNa rachunek: {ZNANY}\nData operacji: 2026-01-16\nKwota: 19,00 PLN\n"
         "Tytuł: opłata skarbowa od pełnomocnictwa w postępowaniu przed KIO w\nprzetargu ZP.900.2.2026\n"
         "Dokument jest.v wydrukiem komputerowym inie. wymaga dodatkowych podpisów oraz stempla bankowego.\n")
    assert _przelew(potok, t)["tytul"] == "opłata skarbowa od pełnomocnictwa w postępowaniu przed KIO w przetargu ZP.900.2.2026"


def test_tytul_wielowierszowy_zostaje_caly(potok):
    # druga linia tytułu z nazwą firmy „z siedzibą w …” albo z „Zamawiający: …” to dalej tytuł
    t = (f"Bank Fikcyjny S.A.\nPotwierdzenie przelewu\nZ rachunku: {INNY}\nNa rachunek: {ZNANY}\nData operacji: 2026-05-12\n"
         "Tytuł: Wpis od odwołania wykonawcy BUDMAX TESTOWY SP. Z O.O.\nz siedzibą w Miastowie, Zamawiający: Gmina Testowa\n"
         "Kwota: 7 500,00 PLN\nDokument nie wymaga podpisu ani stempla.\n")
    assert _przelew(potok, t)["tytul"] == ("Wpis od odwołania wykonawcy BUDMAX TESTOWY SP. Z O.O. z siedzibą w Miastowie, "
                                          "Zamawiający: Gmina Testowa")


def test_rachunek_znany_to_odbiorca_takze_gdy_stoi_pierwszy(potok):
    t = ("Bank Fikcyjny\nPOLECENIE PRZELEWU – POTWIERDZENIE WYKONANIA\nNazwa odbiorcy: Urząd Testowy\n"
         f"Nr rachunku odbiorcy: {ZNANY}\nNazwa zleceniodawcy: Firma Testowa sp. z o.o.\nNr rachunku zleceniodawcy: {INNY}\n"
         "Kwota: 15 000,00 PLN\nData operacji: 03.02.2026\nTytuł: Wpis od odwołania ZP.1.2026\n")
    w = _przelew(potok, t)
    assert w["na_rachunek"] == ZNANY.replace(" ", "") and w["z_rachunku"] == INNY.replace(" ", "")


def test_rachunek_inny_niz_znany_tylko_gdy_jeden():
    from odwolania2json.normalizacja import rachunek_inny_niz_znany, rachunek_znany_w_tekscie
    trzeci = "43 1030 1508 0000 0005 5000 1234"
    assert rachunek_znany_w_tekscie(f"a {INNY} b") is None
    assert rachunek_znany_w_tekscie(f"a {INNY}\nb 60 1010 1010 0081 3622 3100\n0000") == ZNANY.replace(" ", "")
    assert rachunek_inny_niz_znany(f"{ZNANY} {INNY}") == INNY.replace(" ", "")
    assert rachunek_inny_niz_znany(f"{ZNANY} {INNY} {trzeci}") is None and rachunek_inny_niz_znany(ZNANY) is None


def test_imie_ewie_do_mianownika():
    from odwolania2json.normalizacja import mianownik
    assert mianownik("Ewie Nowak") == "Ewa Nowak" and mianownik("Ewie Kowalskiej") == "Ewa Kowalska"
    assert mianownik("Ewa Nowak") == "Ewa Nowak"


def test_rachunki_z_tekstu_z_pl_jak_w_dokumencie():
    """Z44: rachunek z PL w dokumencie zostaje z PL (porównanie ze znanymi po samych cyfrach)."""
    from odwolania2json.normalizacja import rachunek_inny_niz_znany, rachunek_znany_w_tekscie
    assert rachunek_znany_w_tekscie(f"Na rachunek: PL{ZNANY}") == "PL" + ZNANY.replace(" ", "")
    assert rachunek_inny_niz_znany(f"Z rachunku: PL{INNY}\nNa rachunek: {ZNANY}") == "PL" + INNY.replace(" ", "")
    assert rachunek_inny_niz_znany(f"PL{ZNANY} {ZNANY} {INNY}") == INNY.replace(" ", "")   # ten sam numer z PL i bez: jeden
