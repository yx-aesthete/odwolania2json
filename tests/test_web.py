from pathlib import Path

import pytest
from fastapi.testclient import TestClient

KORZEN = Path(__file__).resolve().parents[1]
PRZYKLAD = KORZEN / "data/raw/uzp/dane/przyklad_01"


@pytest.mark.skipif(not PRZYKLAD.exists(), reason="brak danych UZP")
def test_upload_trzech_dokumentow(monkeypatch):
    monkeypatch.setenv("BEZ_LLM", "1")
    from odwolania2json.web import app
    c = TestClient(app)
    pliki = [("pliki", (p.name, p.read_bytes(), "application/pdf")) for p in sorted(PRZYKLAD.glob("*.pdf"))]
    r = c.post("/api/przetworz", files=pliki)
    assert r.status_code == 200
    assert sorted(x["klasa"] for x in r.json()) == ["odwolanie", "pelnomocnictwo", "przelew"]
    assert all(x["audyt"]["pola"] for x in r.json())


def test_odrzuca_nie_pdf(monkeypatch):
    monkeypatch.setenv("BEZ_LLM", "1")
    from odwolania2json.web import app
    r = TestClient(app).post("/api/przetworz", files=[("pliki", ("a.txt", b"x", "text/plain"))])
    assert r.json()[0]["blad"]
