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


def test_rachunek_bez_pl_i_spacji():
    assert rachunek("PL66 2111 8080 1009 8828 5708 1733") == "66211180801009882857081733"


def test_bzp_ted():
    assert bzp("2026/BZP 00999263") == "2026/BZP00999263"
    assert bzp("2026/BZP00999497/03") == "2026/BZP00999497/03"
    assert ted("2026/S 067-999583") == "999583-2026"
    assert ted("TED: 641651-2025") == "641651-2025"


def test_tytuly_zawodowe():
    assert bez_tytulu_zawodowego("r. pr. Aleksandra Marciniak") == "Aleksandra Marciniak"
    assert bez_tytulu_zawodowego("radcę prawnego Jana Nowaka") == "Jana Nowaka"
