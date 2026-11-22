"""Arbitraż szeroki (sekcja model_szeroki w YAML): model pierwszym kandydatem, reguła walidatorem."""
from pathlib import Path

import yaml

from odwolania2json.arbitraz_szeroki import ArbitrazSzeroki, osoba_w_tekscie

KLASY = Path(__file__).resolve().parents[1] / "config" / "klasy"
SPEC = {
    "wlaczony": True,
    "polecenie": "x",
    "pola": {
        "pelnomocnicy[].imie_nazwisko": "osoba",
        "mocodawca[].data.nazwa": "doslownie",
        "mocodawca[].data.typ": "slownik",
    },
    "dozwolone": {"mocodawca[].data.typ": ["osoba_prawna", "osoba_fizyczna"]},
    "formy_zalezne": r"radcy\s+prawnemu|adwokatowi|\bPani",
    "listy": {"pelnomocnicy": {"dodawaj": True, "klucz": "imie_nazwisko"},
              "mocodawca": {"dodawaj": True, "klucz": "data.nazwa"}},
}
TEKST = ("Alfa Serwis sp. z o.o., NIP 1234567890, oraz Beta Instal S.A. udzielają pełnomocnictwa radcy prawnemu "
         "Cezaremu Zającowi oraz Pani Aleksandrze Kowalskiej, a podpisuje Aleksandra Jabłończyk.")


def test_osoba_tylko_zmiana_koncowek():
    assert osoba_w_tekscie("Cezary Zając", TEKST, SPEC["formy_zalezne"])
    assert osoba_w_tekscie("Aleksandra Kowalska", TEKST, SPEC["formy_zalezne"])
    assert osoba_w_tekscie("ALEKSANDRA JABŁOŃCZYK", TEKST)                                 # wielkość liter
    assert not osoba_w_tekscie("Aleksander Jabłończyk", TEKST, SPEC["formy_zalezne"])    # mianownik w tekście
    assert not osoba_w_tekscie("Cezary Zając", "r. pr. Cezaremu Zającowi", SPEC["formy_zalezne"])  # skrót
    assert not osoba_w_tekscie("Cezary Zając", TEKST)                                    # bez słownika form
    assert not osoba_w_tekscie("Cezary Zając Nowak", TEKST)      # dodany wyraz
    assert not osoba_w_tekscie("Marek Wiśniewski", TEKST)        # inny rdzeń
    assert not osoba_w_tekscie("Cezary Zajączkowski", TEKST)     # rdzeń zmieniony, nie tylko końcówka


def test_model_wygrywa_gdy_w_tekscie_inaczej_regula():
    regula = {"pelnomocnicy": [{"imie_nazwisko": "Cezaremu Zającowi", "pesel": "80010112345"}],
              "mocodawca": [{"data": {"typ": "osoba_prawna", "nazwa": "Alfa Serwis sp. z o.o.", "nip": "1234567890"}}]}
    model = {"pelnomocnicy": [{"imie_nazwisko": "Cezary Zając", "pesel": "99999999999"},
                              {"imie_nazwisko": "Aleksandra Kowalska"}],
             "mocodawca": [{"data": {"typ": "spółka", "nazwa": "Alfa Serwis Sp. z o.o.", "nip": "1"}},
                           {"data": {"typ": "osoba_prawna", "nazwa": "Beta Instal S.A."}}]}
    a = ArbitrazSzeroki(SPEC)
    w = a.scal(regula, model, TEKST)
    assert w["pelnomocnicy"][0] == {"imie_nazwisko": "Cezary Zając", "pesel": "80010112345"}  # PESEL z reguł
    assert w["pelnomocnicy"][1] == {"imie_nazwisko": "Aleksandra Kowalska", "pesel": None}
    assert w["mocodawca"][0]["data"] == {"typ": "osoba_prawna", "nazwa": "Alfa Serwis sp. z o.o.",
                                         "nip": "1234567890"}       # nazwa spoza tekstu i typ spoza słownika
    assert w["mocodawca"][1]["data"]["nazwa"] == "Beta Instal S.A."
    assert w["mocodawca"][1]["data"]["nip"] is None                  # identyfikatory nowego elementu puste


def test_identyfikatory_regula_za_nazwa_z_modelu():
    spec = {**SPEC, "listy": {"mocodawca": {"dodawaj": True, "klucz": "data.nazwa",
                                            "identyfikatory": {"data.nip": r"NIP\s*(?P<v>\d{10})"}}}}
    tekst = "Alfa sp. z o.o., NIP 1234567890 oraz Beta S.A., NIP 9876543210 udzielają pełnomocnictwa"
    regula = {"mocodawca": [{"data": {"nazwa": "Alfa sp. z o.o.", "nip": "1234567890", "typ": "osoba_prawna"}}]}
    model = {"mocodawca": [{"data": {"nazwa": "Alfa sp. z o.o."}}, {"data": {"nazwa": "Beta S.A."}}]}
    w = ArbitrazSzeroki(spec).scal(regula, model, tekst)
    assert [m["data"]["nip"] for m in w["mocodawca"]] == ["1234567890", "9876543210"]


def test_dwuznaczna_forma_zostaje_dosłownie():
    tekst = "udzielam pełnomocnictwa Radcy Prawnemu Aleksandra Rybak"
    spec = {**SPEC, "formy_zalezne": r"radcy\s+prawnemu"}
    regula = {"pelnomocnicy": [{"imie_nazwisko": "Aleksandra Rybak", "pesel": None}]}
    model = {"pelnomocnicy": [{"imie_nazwisko": "Aleksander Rybak"}]}
    assert ArbitrazSzeroki(spec).scal(regula, model, tekst) == regula


def test_element_spoza_tekstu_nie_jest_dodawany():
    regula = {"pelnomocnicy": [{"imie_nazwisko": "Cezary Zając", "pesel": None}]}
    model = {"pelnomocnicy": [{"imie_nazwisko": "Cezary Zając"}, {"imie_nazwisko": "Jan Nowak"}]}
    assert ArbitrazSzeroki(SPEC).scal(regula, model, TEKST) == regula


def test_zly_json_zostawia_reguly():
    regula = {"pelnomocnicy": [{"imie_nazwisko": "Cezary Zając", "pesel": None}]}
    assert ArbitrazSzeroki(SPEC).scal(regula, None, TEKST) == regula
    assert ArbitrazSzeroki(SPEC).scal(regula, {"pelnomocnicy": "x"}, TEKST) == regula


def test_przelacznik_wlaczony_po_werdykcie_testera():
    for nazwa in ("odwolanie", "pelnomocnictwo"):
        spec = yaml.safe_load((KLASY / f"{nazwa}.yaml").read_text(encoding="utf-8"))
        assert spec["model_szeroki"]["wlaczony"] is True  # włączony po pomiarze na zbiorach ukrytych
        assert all(r in ("osoba", "doslownie", "slownik") for r in spec["model_szeroki"]["pola"].values())
        assert not any(k in p for p in spec["model_szeroki"]["pola"]
                       for k in ("krs", "nip", "regon", "pesel", "numer", "przelew"))
