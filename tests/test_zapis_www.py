"""Z36: wgranie przez WWW zapisuje JSON-y do ./output/<sprawa>/ tak jak CLI (nazwy jak PDF, obcy jako {})."""
import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

KORZEN = Path(__file__).resolve().parents[1]
CASE06 = KORZEN / "tests" / "kontrolny" / "input" / "case06"


def test_wgranie_zapisuje_do_output(monkeypatch):
    monkeypatch.setenv("BEZ_LLM", "1")
    from odwolania2json import web
    monkeypatch.setattr(web, "_potok", None)
    pliki = sorted(CASE06.glob("*.pdf"))
    r = TestClient(web.app).post("/api/sprawa?czekaj=true", data={"nazwa": "test sprawa/../x"},
                                 files=[("pliki", (p.name, p.read_bytes(), "application/pdf")) for p in pliki])
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["gotowa"] and d["zapis"] == {"katalog": "output/test-sprawa-.-x/", "pliki": len(pliki)}
    katalog = Path(os.environ["WEB_OUTPUT"]) / d["zapis"]["katalog"].removeprefix("output/").rstrip("/")
    zapisane = sorted(p.name for p in katalog.glob("*.json"))
    assert zapisane == sorted(p.with_suffix(".json").name for p in pliki)
    assert json.loads((katalog / "wezwanie_kio.json").read_text(encoding="utf-8")) == {}   # obcy
    assert "przelew_bankowy" in json.loads((katalog / "przelew_nr_6.json").read_text(encoding="utf-8"))
    assert ".." not in katalog.name and "/" not in katalog.name
    assert (Path(os.environ["WEB_AUDIT"]) / katalog.name / "przelew_nr_6.json").exists()


def test_nazwa_domyslna():
    from odwolania2json.sprawy import nazwa_sprawy
    n = nazwa_sprawy(None, "abcdef123")
    assert n.startswith("sprawa-") and n.endswith("-abcdef")
