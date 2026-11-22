"""Z33: dzienny sufit wywołań modelu w podglądzie WWW — po przekroczeniu same reguły, bez błędu."""
from odwolania2json import budzet
from odwolania2json.llm import KlientLLM


def test_sufit_trzy_wywolania_czwarte_regulami(monkeypatch):
    k = KlientLLM(base_url="http://127.0.0.1:9", api_key="k", model="m")
    wyslane = []
    monkeypatch.setattr(k, "_wyslij_raz", lambda c, n: wyslane.append(1) or
                        {"choices": [{"message": {"content": "odp"}}]})
    budzet.ustaw_sufit_dzienny(3)
    try:
        odp = [k(f"Pytanie {i}?", "tekst") for i in range(4)]
        assert odp[:3] == ["odp"] * 3 and odp[3] is None
        assert len(wyslane) == 3 and k.bledy == 0
        assert budzet.stan_sufitu() == {"maks_wywolan_dziennie": 3, "wywolan_dzis": 3, "wyczerpany": True}
        assert budzet.wyczerpany()   # OCR też nie pyta
    finally:
        budzet.ustaw_sufit_dzienny(None)
    assert not budzet.wyczerpany()


def test_limity_pokazuja_sufit():
    from fastapi.testclient import TestClient
    from odwolania2json.web import app
    d = TestClient(app).get("/api/limity").json()
    assert {"maks_stron_ocr", "maks_wywolan_dziennie", "wywolan_dzis", "wyczerpany"} <= set(d)
