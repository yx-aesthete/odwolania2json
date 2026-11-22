"""Klasa opisowa: typ dokumentu opisany w YAML samymi słowami (config/klasy-demo/odpowiedz_na_odwolanie.yaml)."""
import json
import re
from pathlib import Path

import pytest

from odwolania2json.klasy import wczytaj_klasy
from odwolania2json.opisowa import Pole, polecenie, sprawdz_pole, wzorzec_frazy
from odwolania2json.potok import Potok, katalogi_dodatkowe

KORZEN = Path(__file__).resolve().parents[1]
DEMO = KORZEN / "config/klasy-demo"
TEKST = """Warszawa, dnia 12 października 2026 r.
Sygn. akt: KIO 9991/26
Zamawiający: Gmina Miasto Zielonka Dolna, NIP 999-104-51-25
Odwołujący: Budimex-Fikcja Konstrukcje sp. z o.o.
ODPOWIEDŹ NA ODWOŁANIE
W odpowiedzi na odwołanie Zamawiający wnosi o oddalenie odwołania w całości.
W imieniu Zamawiającego:
Agnieszka Wróblewska
"""


class Model:
    """Atrapa modelu: zwraca zadany JSON na pytanie o cały dokument."""
    def __init__(self, odp: dict):
        self.odp, self.pytania = odp, []

    def nowy_dokument(self) -> None: ...

    def wybierz_klase(self, tekst, klasy):
        return None

    def zapytaj_json(self, polecenie: str, tekst: str) -> str:
        self.pytania.append(polecenie)
        return json.dumps(self.odp, ensure_ascii=False)


def potok_demo(odp: dict | None = None) -> Potok:
    p = Potok(KORZEN / "config/klasy", uzyj_llm=False, dodatkowe=[DEMO])
    p.llm = Model(odp) if odp is not None else None
    return p


def test_fraza_bez_regexow_pasuje_z_ogonkami_i_bez():
    w = wzorzec_frazy("odpowiedź na odwołanie")
    assert re.search(w, "W  odpowiedz na\nodwolanie", re.I)
    assert re.search(wzorzec_frazy("odpowiedź na odwołanie", tytul=True), "|ODPOWIEDZNAODWOŁANIE|", re.I)
    assert re.search(wzorzec_frazy("sygn. akt (KIO)"), "sygn. akt (KIO)", re.I) and not re.search(wzorzec_frazy("a.b"), "axb")


def test_klasa_demo_poza_domyslnym_zestawem():
    assert "odpowiedz_na_odwolanie" not in {k.nazwa for k in wczytaj_klasy(KORZEN / "config/klasy")}
    assert katalogi_dodatkowe(KORZEN / "config/aplikacja.yaml") == []
    w = Potok(KORZEN / "config/klasy", uzyj_llm=False).przetworz_tekst(TEKST)
    assert w.klasa is None and w.dane is None  # bez klasy demo dokument jest obcy -> {}


def test_wlaczenie_zmienna_i_zly_katalog(monkeypatch, tmp_path):
    monkeypatch.setenv("KLASY_DODATKOWE", str(DEMO))
    assert katalogi_dodatkowe(KORZEN / "config/aplikacja.yaml") == [DEMO]
    monkeypatch.setenv("KLASY_DODATKOWE", str(tmp_path / "nie_ma"))
    with pytest.raises(ValueError, match="brak katalogu"):
        katalogi_dodatkowe(KORZEN / "config/aplikacja.yaml")


def test_ekstrakcja_po_opisach_z_walidacja_w_tekscie():
    model = potok_demo({
        "OdpowiedzNaOdwolanie": {"sygnatura": "KIO 9991/26", "data": "2026-10-12", "wniosek": "Oddalenie"},
        "Zamawiajacy": {"nazwa": "Gmina Miasto Zielonka Dolna", "nip": "999-104-51-25"},
        "Odwolujacy": {"nazwa": "Firma Zmyślona S.A."},       # nie ma w tekście -> null
        "pelnomocnik": "Agnieszka Wróblewska",
    })
    w = model.przetworz_tekst(TEKST)
    assert w.klasa == "odpowiedz_na_odwolanie"
    assert w.dane == {
        "OdpowiedzNaOdwolanie": {"sygnatura": "KIO 9991/26", "data": "2026-10-12", "wniosek": "oddalenie"},
        "Zamawiajacy": {"nazwa": "Gmina Miasto Zielonka Dolna", "nip": "9991045125"},
        "Odwolujacy": {"nazwa": None},
        "pelnomocnik": "Agnieszka Wróblewska",
    }
    assert {p["pole"] for p in w.audyt["pola"]} >= {"OdpowiedzNaOdwolanie.sygnatura", "pelnomocnik"}
    assert all(p["metoda"] == "model#opis" for p in w.audyt["pola"])
    assert "data sporządzenia pisma" in model.llm.pytania[0]


def test_bez_modelu_pola_puste_a_struktura_jest():
    w = potok_demo().przetworz_tekst(TEKST)
    assert w.klasa == "odpowiedz_na_odwolanie"
    assert w.dane["Zamawiajacy"] == {"nazwa": None, "nip": None}


@pytest.mark.parametrize("pole,wartosc,oczekiwane", [
    (Pole(("w",), "wniosek", wybor=("oddalenie", "odrzucenie")), "uwzględnienie", None),
    (Pole(("n",), "NIP", "cyfry"), "999-000-00-00", None),
    (Pole(("d",), "data", "data"), "12 października 2026 r.", "2026-10-12"),
    (Pole(("d",), "data", "data"), "2026-10-13", None),
    (Pole(("o",), "osoba", "osoba"), "Jan Kowalski", None),
    (Pole(("t",), "tekst"), {"zagniezdzone": 1}, None),
])
def test_walidator_odrzuca_wartosci_spoza_dokumentu(pole, wartosc, oczekiwane):
    assert sprawdz_pole(pole, wartosc, TEKST)[0] == oczekiwane


def test_polecenie_z_opisow_i_zly_typ():
    spec = {"nazwa": "x", "pola": {"A": {"b": "opis b", "c": {"opis": "opis c", "wybor": ["p", "q"]}}}}
    assert '{"A": {"b": null, "c": null}}' in polecenie(spec) and "jedna z wartości: p, q" in polecenie(spec)
    with pytest.raises(ValueError, match="nieznany typ"):
        polecenie({"pola": {"a": {"opis": "x", "typ": "regex"}}})


def test_klasa_demo_nie_przejmuje_dokumentow_uzp():
    """Przy włączonych klasach demo zbiór kontrolny ma te same klasy co bez nich (dokumenty obce dalej {})."""
    zwykly = Potok(KORZEN / "config/klasy", uzyj_llm=False)
    demo = potok_demo()
    pdfy = sorted((KORZEN / "tests/kontrolny/input").rglob("*.pdf"))
    assert pdfy
    for pdf in pdfy:
        assert demo.przetworz(pdf).klasa == zwykly.przetworz(pdf).klasa, pdf.name


def test_trzy_przyklady_pdf_rozpoznane():
    demo = potok_demo()
    for pdf in sorted((KORZEN / "tests/demo_odpowiedz/input").rglob("*.pdf")):
        assert demo.przetworz(pdf).klasa == "odpowiedz_na_odwolanie", pdf.name
