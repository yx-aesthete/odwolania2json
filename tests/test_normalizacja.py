from odwolania2json.normalizacja import bez_tytulu_zawodowego, bzp, data_iso, kwota, rachunek, ted


def test_daty():
    assert data_iso("dnia 15 lipca 2026 roku") == "2026-07-15"
    assert data_iso("11-10-2026") == "2026-10-11"
    assert data_iso("2026-03-21") == "2026-03-21"
    assert data_iso("18.03.2026 r.") == "2026-03-18"


def test_kwoty():
    assert kwota("7 500,00 zł") == 7500.0
    assert kwota("17.00 PLN") == 17.0
    assert kwota("10.000,00") == 10000.0


def test_rachunek_jak_w_dokumencie_bez_spacji():
    # Z44 (UZP 21.11): PL zostaje, gdy stoi w dokumencie przed numerem; bez PL w tekście — same cyfry
    assert rachunek("PL66 2111 8080 1009 8828 5708 1733") == "PL66211180801009882857081733"
    assert rachunek("75 2170 0008 9152 5017 5661 7062") == "75217000089152501756617062"


def test_dwa_rachunki_kazdy_wedlug_swojego_fragmentu():
    from odwolania2json.normalizacja import rachunek_drugi
    kolumny = "PL61 1090 1014 0000 0712 1981\n2874\n60 1010 1010 0081 3622 3100\n0000\n"
    assert rachunek(kolumny) == "PL61109010140000071219812874"
    assert rachunek_drugi(kolumny) == "60101010100081362231000000"
    assert rachunek_drugi("61 1090 1014 0000 0712 1981 2874\nPL60 1010 1010 0081 3622 3100 0000") == \
        "PL60101010100081362231000000"


def test_bzp_ted():
    assert bzp("2026/BZP 00999263") == "2026/BZP00999263"
    assert bzp("2026/BZP00999497/03") == "2026/BZP00999497/03"
    assert ted("2026/S 067-999583") == "999583-2026"
    assert ted("TED: 641651-2025") == "641651-2025"


def test_tytuly_zawodowe():
    assert bez_tytulu_zawodowego("r. pr. Aleksandra Marciniak") == "Aleksandra Marciniak"
    assert bez_tytulu_zawodowego("radcę prawnego Jana Nowaka") == "Jana Nowaka"


def test_mianownik_bezpieczny():
    from odwolania2json.normalizacja import mianownik
    assert mianownik("Tomaszowi Wierzbickiemu") == "Tomasz Wierzbicki"
    assert mianownik("Annę Kowalską") == "Anna Kowalska"
    assert mianownik("Annie Kowalskiej") == "Anna Kowalska"
    assert mianownik("Marka Zielińskiego") == "Marek Zieliński"
    assert mianownik("Jan Sroka") == "Jan Sroka"            # mianownik bez zmian
    assert mianownik("Katarzyna Wiśniewska-Lis") == "Katarzyna Wiśniewska-Lis"


def test_mianownik_w_kontekscie_zaleznym():
    from odwolania2json.normalizacja import mianownik_zalezny
    assert mianownik_zalezny("Jana Nowaka") == "Jan Nowak"
    assert mianownik_zalezny("Agacie Nowak") == "Agata Nowak"
    assert mianownik_zalezny("Jerzego Kowala") == "Jerzy Kowal"


def test_tytul_dr_nie_obcina_nazwisk_na_dr():
    assert bez_tytulu_zawodowego("Jan Drozd") == "Jan Drozd"
    assert bez_tytulu_zawodowego("adw. Anna Drabik") == "Anna Drabik"
    assert bez_tytulu_zawodowego("dr Jan Drozd") == "Jan Drozd"
    assert bez_tytulu_zawodowego("dr. Ewa Nowak") == "Ewa Nowak"


def test_franciszka_kobieta_zostaje_a_dopelniacz_meski_to_franciszek():
    from odwolania2json.normalizacja import mianownik, mianownik_zalezny
    assert mianownik("Franciszka Nowak") == "Franciszka Nowak"
    assert mianownik("Franciszka Kowalska") == "Franciszka Kowalska"
    assert mianownik("Franciszka Kowalskiego") == "Franciszek Kowalski"
    assert mianownik_zalezny("Franciszka Nowaka") == "Franciszek Nowak"
    assert mianownik_zalezny("Franciszkę Nowak") == "Franciszka Nowak"
    assert mianownik("Franciszkowi Nowakowi") == "Franciszek Nowak"
