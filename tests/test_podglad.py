"""Podgląd sprawy w przeglądarce: położenie cytatu na stronie PDF i API sprawy (wgranie, stan, PNG, JSON, ZIP)."""
import io
import json
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from odwolania2json import podglad

KORZEN = Path(__file__).resolve().parents[1]
SPRAWA = KORZEN / "tests/kontrolny/input/case06"
ODWOLANIE = SPRAWA / "odwolanie_nr_6.pdf"

from conftest import wymaga_kontrolnego

pytestmark = wymaga_kontrolnego   # pisma UZP z tests/kontrolny (poza eksportem)


def test_zwarty_pomija_biale_znaki_i_myslniki():
    assert podglad.zwarty("NIP 999-\n850-03-77") == "nip9998500377"


def test_polozenie_cytatu_i_wartosci_na_stronie():
    strona = podglad.tekst_stron(ODWOLANIE)[0]
    miejsce = podglad.polozenie(strona, "NIP: 9998500377", "9998500377")
    assert miejsce and miejsce["cytat"] and miejsce["wartosc"]
    x0, y0, x1, y1 = miejsce["wartosc"][0]
    assert 0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1


def test_data_i_kwota_znalezione_mimo_innego_zapisu():
    strona = podglad.tekst_stron(ODWOLANIE)[0]
    data = podglad.polozenie(strona, "udzieleniu w dniu 14 października 2026 r. wyjaśnień", "2026-10-14")
    assert data and data["wartosc"]
    assert "20000,00" in podglad._warianty(20000.0)


def test_brak_cytatu_na_stronie_to_none_a_nie_blad():
    strona = podglad.tekst_stron(ODWOLANIE)[0]
    assert podglad.polozenie(strona, "tego tekstu nie ma w dokumencie", "x") is None
    assert podglad.polozenie(strona, None, "x") is None
    pusta = podglad.TekstStrony("", (), ())  # strona ze skanu: brak warstwy tekstowej
    assert podglad.polozenie(pusta, "NIP: 9998500377", "9998500377") is None


def test_obraz_strony_to_png():
    png = podglad.obraz_strony(ODWOLANIE, 1, skala=0.5)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    with pytest.raises(ValueError):
        podglad.obraz_strony(ODWOLANIE, 99)


@pytest.fixture
def klient(monkeypatch):
    monkeypatch.setenv("BEZ_LLM", "1")
    from odwolania2json import web
    web._wgrania.clear()
    yield TestClient(web.app)
    web._wgrania.clear()


def _czekaj(klient, id_, limit=60):
    koniec = time.time() + limit
    while time.time() < koniec:
        stan = klient.get(f"/api/sprawa/{id_}").json()
        if stan["gotowa"]:
            return stan
        time.sleep(0.2)
    raise AssertionError("sprawa nie skończyła się w czasie")


def test_api_sprawy_od_wgrania_do_zip(klient):
    pliki = [("pliki", (p.name, p.read_bytes(), "application/pdf")) for p in sorted(SPRAWA.glob("*.pdf"))]
    pliki.append(("pliki", ("notatka.txt", b"x", "text/plain")))
    r = klient.post("/api/sprawa", files=pliki)
    assert r.status_code == 200
    stan = _czekaj(klient, r.json()["id"])
    po_nazwie = {p["plik"]: p for p in stan["pliki"]}
    assert po_nazwie["odwolanie_nr_6.pdf"]["klasa"] == "odwolanie"
    assert po_nazwie["wezwanie_kio.pdf"]["stan"] == "gotowe" and po_nazwie["wezwanie_kio.pdf"]["klasa"] is None
    assert po_nazwie["notatka.txt"]["stan"] == "blad"
    odw = po_nazwie["odwolanie_nr_6.pdf"]
    assert len(odw["polozenia"]) == len(odw["audyt"]["pola"])
    assert sum(1 for p in odw["polozenia"] if p) >= 15  # PDF z tekstem: prawie każde pole zaznaczone na stronie

    id_ = stan["id"]
    nr = odw["nr"]
    png = klient.get(f"/api/sprawa/{id_}/plik/{nr}/strona/1.png")
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"
    assert klient.get(f"/api/sprawa/{id_}/plik/{nr}/strona/9.png").status_code == 404
    assert json.loads(klient.get(f"/api/sprawa/{id_}/plik/{nr}.json").text) == odw["json"]
    obcy = po_nazwie["wezwanie_kio.pdf"]["nr"]
    assert klient.get(f"/api/sprawa/{id_}/plik/{obcy}.json").text == "{}"

    z = zipfile.ZipFile(io.BytesIO(klient.get(f"/api/sprawa/{id_}/zip").content))
    assert sorted(z.namelist()) == ["odwolanie_nr_6.json", "pelnomocnictwo_nr_6.json", "przelew_nr_6.json", "wezwanie_kio.json"]
    assert z.read("wezwanie_kio.json") == b"{}"

    assert klient.delete(f"/api/sprawa/{id_}").json() == {"usunieta": True}
    assert klient.get(f"/api/sprawa/{id_}").status_code == 404


def test_api_sprawy_czekaj_i_przyklad(klient):
    r = klient.post("/api/sprawa?czekaj=true", files=[("pliki", (ODWOLANIE.name, ODWOLANIE.read_bytes(), "application/pdf"))])
    assert r.json()["gotowa"] and r.json()["pliki"][0]["json"]["OdwolanieKIO"]
    assert klient.get("/api/przyklad").json()["dostepny"]
    assert klient.post("/api/sprawa/przyklad").json()["pliki"]


def test_strona_i_opis_api(klient):
    assert "app.js" in klient.get("/").text
    assert klient.get("/static/app.js").status_code == 200
    assert "/api/sprawa" in klient.get("/openapi.json").json()["paths"]
    jak = klient.get("/jak-to-dziala")
    assert jak.status_code == 200 and "Jak działa Odwołania2json" in jak.text
    assert "googleapis" not in jak.text and "googleapis" not in klient.get("/").text  # bez zasobów z sieci
