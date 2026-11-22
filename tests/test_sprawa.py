"""Ujednolicenie nazw w sprawie: tylko różnice w polskich znakach."""
import json

from odwolania2json.sprawa import mapa_ujednolicen, ujednolic_sprawy


def test_mapa_tylko_polskie_znaki():
    m = mapa_ujednolicen(["Zaneta Olszewska", "Żaneta Olszewska", "Jan Kowalski", "Jan Kowalsky", "ASTERION SP. K."])
    assert m == {"Zaneta Olszewska": "Żaneta Olszewska"}


def test_ujednolicenie_plikow_sprawy(tmp_path):
    s = tmp_path / "case01"
    s.mkdir()
    (s / "odwolanie.json").write_text(json.dumps({"Odwolujacy": [{"pelnomocnik": {"imie_nazwisko": "Zaneta Olszewska"}}]}))
    (s / "pelnomocnictwo.json").write_text(json.dumps({"pelnomocnicy": [{"imie_nazwisko": "Żaneta Olszewska", "pesel": None}]}))
    (s / "obcy.json").write_text("{}")
    assert ujednolic_sprawy(tmp_path) == 1
    d = json.loads((s / "odwolanie.json").read_text())
    assert d["Odwolujacy"][0]["pelnomocnik"]["imie_nazwisko"] == "Żaneta Olszewska"
    assert (s / "obcy.json").read_text() == "{}"
