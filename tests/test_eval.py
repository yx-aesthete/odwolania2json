from odwolania2json.eval import Licznik, Raport, Ustawienia, normalizuj, porownaj


def _l(gold, pred, **kw):
    r = Raport()
    porownaj(gold, pred, Ustawienia(**kw), "k", "s", r)
    return r.ogolem


def test_null_null_to_tn():
    l = _l({"a": None, "b": "x"}, {"a": None, "b": "x"})
    assert (l.tp, l.fp, l.fn, l.tn) == (1, 0, 0, 1)


def test_zla_wartosc_to_fp():
    l = _l({"a": "x"}, {"a": "y"})
    assert (l.tp, l.fp, l.fn) == (0, 1, 0)


def test_brak_wartosci_to_fn():
    l = _l({"a": "x"}, {})
    assert (l.tp, l.fp, l.fn) == (0, 0, 1)


def test_wartosc_przy_null_w_referencji_to_fp():
    l = _l({"a": None}, {"a": "y"})
    assert (l.tp, l.fp, l.fn) == (0, 1, 0)


def test_dokument_obcy_pusty_wynik():
    l = _l({}, {})
    assert (l.tp, l.fp, l.fn) == (0, 0, 0)


def test_dlugie_pole_podobienstwo():
    # długie wg UZP (ścieżki): pełnomocnik.nazwa, przelew tytul, nazwy stron, tytuł zamówienia
    assert _l({"Odwolujacy": [{"pelnomocnik": {"nazwa": "Kancelaria Adwokacka Kowalski"}}]},
              {"Odwolujacy": [{"pelnomocnik": {"nazwa": "Kancelaria Adwokacka Kowalsky"}}]}).tp == 1
    assert _l({"x": {"nip": "1234567890"}}, {"x": {"nip": "1234567891"}}).tp == 0


def test_czynnosc_opis_i_nazwa_mocodawcy_dokladnie():
    assert _l({"OdwolanieKIO": {"czynnosc_opis": "Odpowiedzi i wyjaśnienia do SWZ"}},
              {"OdwolanieKIO": {"czynnosc_opis": "Odpowiedzi/wyjaśnienia do SWZ"}}).tp == 0
    assert _l({"mocodawca": [{"data": {"nazwa": "Alfa Serwis sp. z o.o."}}]},
              {"mocodawca": [{"data": {"nazwa": "Alfa Serwis Sp. z o.o"}}]}).tp == 0


def test_normalizacja_liczb_i_cudzyslowow():
    assert normalizuj(10000.0) == normalizuj(10000)
    assert normalizuj("„Abc”  Sp. z o.o.") == normalizuj("abc sp. z o.o.")


def test_listy_po_kolejnosci_i_po_tresci():
    g = {"L": [{"n": "a"}, {"n": "b"}]}
    p = {"L": [{"n": "b"}, {"n": "a"}]}
    assert _l(g, p).tp == 0
    assert _l(g, p, listy_po_tresci=True).tp == 2


def test_f1():
    assert Licznik(tp=1, fp=1, fn=1).f1() == 0.5


def test_rachunek_rozny_na_koncu_to_fp():
    l = _l({"r": "60101010100081362231000000"}, {"r": "60101010100081362231000001"})
    assert (l.tp, l.fp) == (0, 1)


def test_zera_wiodace_krs():
    l = _l({"krs": "0000054588"}, {"krs": "54588"})
    assert (l.tp, l.fp) == (0, 1)


def test_tryb_scisly_rozroznia_wielkosc_liter():
    assert _l({"x": "Abc"}, {"x": "abc"}).tp == 1
    assert _l({"x": "Abc"}, {"x": "abc"}, scisle=True).tp == 0


def test_tryb_scisly_zly_typ_to_fp():
    assert _l({"kwota": 100.0}, {"kwota": "100"}).tp == 1                 # tryb luźny: jak dotąd
    l = _l({"kwota": 100.0}, {"kwota": "100"}, scisle=True)
    assert (l.tp, l.fp, l.fn) == (0, 1, 0)
    l = _l({"krs": "54588"}, {"krs": 54588}, scisle=True)
    assert (l.tp, l.fp) == (0, 1)
    assert _l({"kwota": 100}, {"kwota": 100.0}, scisle=True).tp == 1     # int i float to ta sama liczba
