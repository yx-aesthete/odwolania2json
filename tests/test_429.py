"""Z42: HTTP 429 to „zwolnij”, nie awaria — nie wyłącza modelu; 401 i seria timeoutów wyłączają jak dotąd."""
import io
import urllib.error

from odwolania2json import llm
from odwolania2json.llm import KlientLLM, Wylacznik


def _http(kod, naglowki=None):
    return urllib.error.HTTPError("https://x", kod, "błąd", naglowki or {}, io.BytesIO(b""))


def _klient(monkeypatch, bledy, spanie):
    k = KlientLLM(base_url="https://x.example/v1", model="m", proby=(1.0, 1.0), wylacznik=Wylacznik())
    seria = list(bledy)

    def wyslij(cialo, naglowki):
        if seria:
            raise seria.pop(0)
        return {"choices": [{"message": {"content": "ok"}}]}
    monkeypatch.setattr(k, "_wyslij_raz", wyslij)
    monkeypatch.setattr(llm, "_spij", lambda s: spanie.append(s))
    monkeypatch.setattr(llm, "MAKS_PONOWIEN_429_S", 0.0)   # bez ponowień: każde 429 kończy wywołanie błędem
    return k


def test_trzy_razy_429_nie_wylacza_modelu(monkeypatch):
    k = _klient(monkeypatch, [_http(429), _http(429), _http(429)], [])
    for i in range(3):
        k.nowy_dokument()
        assert k(f"p{i}", "t") is None
    assert not k.wylacznik.wylaczony
    k.nowy_dokument()
    assert k("p9", "t") == "ok"   # kolejne wywołanie idzie do API


def test_retry_after_respektowany(monkeypatch):
    spanie = []
    k = _klient(monkeypatch, [_http(429, {"Retry-After": "2"})], spanie)
    monkeypatch.setattr(llm, "MAKS_PONOWIEN_429_S", 60.0)
    k.nowy_dokument()
    assert k("p", "t") == "ok" and spanie == [2.0]


def test_401_wylacza_od_razu(monkeypatch):
    k = _klient(monkeypatch, [_http(401)], [])
    k.nowy_dokument()
    assert k("p", "t") is None and k.wylacznik.wylaczony


def test_trzy_timeouty_wylaczaja(monkeypatch):
    k = _klient(monkeypatch, [TimeoutError("t")] * 9, [])
    for i in range(3):
        k.nowy_dokument()
        k(f"p{i}", "t")
    assert k.wylacznik.wylaczony
