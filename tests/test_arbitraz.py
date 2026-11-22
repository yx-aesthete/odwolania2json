"""Arbitraż model ↔ reguły (sekcja model_dokumentu w YAML): walidacja wartości modelu w tekście."""
from odwolania2json.arbitraz import Arbitraz, json_z_odpowiedzi, sprawdz

SPEC = {
    "wlaczony": True,
    "polecenie": "x",
    "pola": {
        "pelnomocnicy[].imie_nazwisko": "osoba",
        "pelnomocnicy[].pesel": "cyfry",
        "mocodawca[].data.typ": "slownik",
        "mocodawca[].data.nazwa": "nazwa",
    },
    "dozwolone": {"mocodawca[].data.typ": ["osoba_prawna", "osoba_fizyczna"]},
}
TEKST = ("Alfa Serwis sp. z o.o., NIP 1234567890, udziela pełnomocnictwa radcy prawnemu Cezaremu Zającowi "
         "(PESEL 80010112345) oraz adw. Aleksandrze Kowalskiej.")


def test_osoba_po_rdzeniu_a_nie_doslownie():
    assert sprawdz("osoba", "Cezary Zając", TEKST)[0]
    assert not sprawdz("osoba", "Marek Wiśniewski", TEKST)[0]


def test_model_poprawia_mianownik_i_zachowuje_pewna_regule():
    regula = {"pelnomocnicy": [{"imie_nazwisko": "Cezaremu Zającowi", "pesel": None}],
              "mocodawca": [{"data": {"typ": "osoba_prawna", "nazwa": "Alfa Serwis sp. z o.o."}}]}
    model = {"pelnomocnicy": [{"imie_nazwisko": "Cezary Zając", "pesel": "80010112345"},
                              {"imie_nazwisko": "Aleksandra Kowalska", "pesel": None}],
             "mocodawca": [{"data": {"typ": "spółka", "nazwa": "Alfa Serwis Sp. z o.o."}}]}
    a = Arbitraz(SPEC)
    w = a.scal(regula, model, TEKST)
    assert w["pelnomocnicy"][0] == {"imie_nazwisko": "Cezary Zając", "pesel": "80010112345"}
    assert w["pelnomocnicy"][1]["imie_nazwisko"] == "Aleksandra Kowalska"   # element dodany przez model
    assert w["mocodawca"][0]["data"]["typ"] == "osoba_prawna"               # spoza słownika: zostaje reguła
    assert w["mocodawca"][0]["data"]["nazwa"] == "Alfa Serwis sp. z o.o."   # reguła dosłownie w tekście
    assert any(d.metoda == "model#dokument" for d in a.dowody)


def test_model_gubiacy_element_listy_nie_nadpisuje():
    regula = {"pelnomocnicy": [{"imie_nazwisko": "Cezary Zając", "pesel": None},
                               {"imie_nazwisko": "Aleksandra Kowalska", "pesel": None}]}
    model = {"pelnomocnicy": [{"imie_nazwisko": "Cezary Zając", "pesel": None}]}
    assert Arbitraz(SPEC).scal(regula, model, TEKST) == regula


def test_bez_polskich_znakow_zostaje_regula():
    regula = {"pelnomocnicy": [{"imie_nazwisko": "Cezary Zając", "pesel": None}]}
    model = {"pelnomocnicy": [{"imie_nazwisko": "Cezary Zajac", "pesel": None}]}
    assert Arbitraz(SPEC).scal(regula, model, "radcy prawnemu Cezaremu Zającowi, Zajac")["pelnomocnicy"][0][
        "imie_nazwisko"] == "Cezary Zając"


def test_json_z_odpowiedzi():
    assert json_z_odpowiedzi('```json\n{"a": 1}\n```') == {"a": 1}
    assert json_z_odpowiedzi("brak") is None
