"""Model po API przy złym otoczeniu: .env zapisany w Windows, zły klucz, wiszące API, zerwane i nietypowe odpowiedzi.
Atrapa API na 127.0.0.1, bez sieci i bez prawdziwego klucza."""
import json
import logging
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from odwolania2json import llm
from odwolania2json.klasy import BLAD_MODELU

KONFIG = Path(__file__).resolve().parents[1] / "config" / "model.yaml"
ZMIENNE = ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL", "MODEL_TRYB", "OCR_MODEL", "ZMIENNA_O2J_A", "ZMIENNA_O2J_B")


@pytest.fixture
def czyste_env(monkeypatch):
    for z in ZMIENNE:
        monkeypatch.delenv(z, raising=False)
    yield monkeypatch
    for z in ZMIENNE:  # wczytaj_env pisze wprost do os.environ
        os.environ.pop(z, None)


# --- .env (pkt 2) ---------------------------------------------------------------------------------------------

TRESC_ENV = "# klucz modelu\r\nZMIENNA_O2J_A=zażółć\r\nZMIENNA_O2J_B=\"b c\"\r\n"


@pytest.mark.parametrize("kodowanie", ["utf-16", "utf-16-le-bom", "utf-16-be-bom", "utf-16-le", "utf-16-be",
                                       "utf-8-sig", "utf-8", "cp1250"])
def test_env_w_kodowaniach_windows(tmp_path, czyste_env, kodowanie):
    plik = tmp_path / ".env"
    if kodowanie == "utf-16-le-bom":
        dane = b"\xff\xfe" + TRESC_ENV.encode("utf-16-le")
    elif kodowanie == "utf-16-be-bom":
        dane = b"\xfe\xff" + TRESC_ENV.encode("utf-16-be")
    else:
        dane = TRESC_ENV.encode(kodowanie)  # "utf-16": z BOM, jak PowerShell 5.1 (`>` / Out-File)
    plik.write_bytes(dane)
    llm.wczytaj_env(plik)
    assert os.environ["ZMIENNA_O2J_A"] == "zażółć" and os.environ["ZMIENNA_O2J_B"] == "b c"


def test_env_set_export_spacje_komentarze(tmp_path, czyste_env):
    plik = tmp_path / ".env"
    plik.write_text(
        "LLM_API_KEY=\n"                              # pusta linia klucza nad właściwą: nie blokuje
        "set LLM_API_KEY = abc123   # klucz z konsoli\n"
        "export LLM_MODEL= gemma-4 \n"
        "SET ZMIENNA_O2J_A = \"x # y\"  # komentarz za cudzysłowem\n"
        "ZMIENNA_O2J_B=a#b\n",                       # „#” bez spacji przed nim to część wartości
        encoding="utf-8")
    llm.wczytaj_env(plik)
    assert os.environ["LLM_API_KEY"] == "abc123"
    assert os.environ["LLM_MODEL"] == "gemma-4"
    assert os.environ["ZMIENNA_O2J_A"] == "x # y"
    assert os.environ["ZMIENNA_O2J_B"] == "a#b"


def test_env_nieczytelny_nie_przerywa(tmp_path, czyste_env, caplog):
    katalog = tmp_path / ".env"
    katalog.mkdir()  # zamiast pliku katalog: read_bytes() rzuca wyjątek
    with caplog.at_level(logging.WARNING, logger="odwolania2json"):
        llm.wczytaj_env(katalog)
    assert "Nie udało się odczytać" in caplog.text


def test_klient_obcina_spacje_i_cr(czyste_env):
    czyste_env.setenv("MODEL_TRYB", "api")
    czyste_env.setenv("LLM_API_KEY", " klucz\r")
    czyste_env.setenv("LLM_BASE_URL", "https://x.example/v1 ")
    czyste_env.setenv("LLM_MODEL", "gemma\r")
    k = llm.klient_z_env(KONFIG)
    assert (k.api_key, k.base_url, k.model) == ("klucz", "https://x.example/v1", "gemma")


# --- atrapa API (pkt 5) ----------------------------------------------------------------------------------------

class Atrapa:
    def __init__(self, tryb: str):
        self.tryb, self.zapytania = tryb, 0
        atrapa = self

        class Obsluga(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
                atrapa.zapytania += 1
                tryb = atrapa.tryb
                if tryb in ("401", "403", "404"):
                    self.send_response(int(tryb))
                    self.end_headers()
                    self.wfile.write(b'{"error": "nope"}')
                    return
                if tryb == "wisi":
                    time.sleep(1.0)
                    return
                if tryb == "zerwane":  # Content-Length większy niż treść: IncompleteRead
                    self.send_response(200)
                    self.send_header("Content-Length", "1000")
                    self.end_headers()
                    self.wfile.write(b'{"choices": [')
                    return
                tresc = {
                    "ok": {"choices": [{"message": {"content": "Gmina Kielce"}}]},
                    "lista": {"choices": [{"message": {"content": [{"type": "text", "text": "Gmina "},
                                                                   {"type": "text", "text": "Kielce"}]}}]},
                    "zly_json": {"wynik": "brak choices"},
                    "liczba": {"choices": [{"message": {"content": 7}}]},
                    # OCR: za każdym razem trochę inny tekst, jak model obrazowy mimo temperatury 0
                    "ocr": {"choices": [{"message": {"content": "ODWOŁANIE do Krajowej Izby Odwoławczej, "
                                                                f"strona przepisana po raz {atrapa.zapytania}."}}]},
                }[tryb]
                dane = json.dumps(tresc).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(dane)))
                self.end_headers()
                self.wfile.write(dane)

        self.serwer = ThreadingHTTPServer(("127.0.0.1", 0), Obsluga)
        self.url = f"http://127.0.0.1:{self.serwer.server_address[1]}/v1"
        threading.Thread(target=self.serwer.serve_forever, daemon=True).start()

    def zamknij(self):
        self.serwer.shutdown()
        self.serwer.server_close()


@pytest.fixture
def atrapa():
    utworzone = []

    def zrob(tryb):
        a = Atrapa(tryb)
        utworzone.append(a)
        return a
    yield zrob
    for a in utworzone:
        a.zamknij()


def _klient(url, **kw):
    return llm.KlientLLM(base_url=url, model="m", api_key="test", proby=(), timeout_s=0.3, **kw)


@pytest.mark.parametrize("kod", ["401", "403", "404"])
def test_blad_trwaly_wylacza_model_na_caly_przebieg(atrapa, caplog, kod):
    a = atrapa(kod)
    k = _klient(a.url)
    with caplog.at_level(logging.WARNING, logger="odwolania2json"):
        for i in range(5):  # 5 dokumentów po 2 pytania
            k.nowy_dokument()
            assert k("p1", f"tekst {i}") is None and k("p2", f"tekst {i}") is None
        assert k.wybierz_klase("tekst", []) == BLAD_MODELU
        assert k.zapytaj_json("polecenie", "tekst") is None
    assert a.zapytania == 1
    assert caplog.text.count("MODEL WYŁĄCZONY") == 1 and f"HTTP {kod}" in caplog.text
    assert "wyłączony" in k.podsumowanie()


def test_wiszace_api_wylacza_po_trzech_kolejnych_bledach(atrapa, caplog):
    a = atrapa("wisi")
    k = _klient(a.url, max_bledow=5)
    t0 = time.time()
    with caplog.at_level(logging.WARNING, logger="odwolania2json"):
        for i in range(4):
            k.nowy_dokument()
            for j in range(3):
                assert k(f"p{j}", f"tekst {i}") is None
    assert a.zapytania == 3 and k.bledy == 3
    assert caplog.text.count("MODEL WYŁĄCZONY") == 1 and "3 kolejne błędy" in caplog.text
    assert time.time() - t0 < 5


def test_udana_odpowiedz_zeruje_licznik_kolejnych_bledow(atrapa):
    a = atrapa("wisi")
    k = _klient(a.url, max_bledow=10)
    k.nowy_dokument()
    assert k("p1", "t") is None and k("p2", "t") is None
    a.tryb = "ok"
    assert k("p3", "t") == "Gmina Kielce"
    a.tryb = "wisi"
    assert k("p4", "t") is None and k("p5", "t") is None
    assert k.aktywny and not k.wylacznik.wylaczony  # 2 + 2 błędy, ale nie 3 z rzędu
    assert k("p6", "t") is None
    assert k.wylacznik.wylaczony


@pytest.mark.parametrize("tryb", ["zerwane", "zly_json"])
def test_zerwana_i_nietypowa_odpowiedz_nie_przerywa(atrapa, tryb):
    a = atrapa(tryb)
    k = _klient(a.url)
    k.nowy_dokument()
    assert k("p", "tekst") is None
    assert k.zapytaj_json("polecenie", "tekst") is None
    assert k.bledy == 2


def test_tresc_jako_lista_czesci_i_liczba(atrapa):
    a = atrapa("lista")
    k = _klient(a.url)
    k.nowy_dokument()
    assert k("p", "tekst") == "Gmina Kielce"
    a.tryb = "liczba"
    assert k("p", "inny tekst") == "7" and k.bledy == 0


def test_ocr_po_api_korzysta_z_tego_samego_wylacznika(atrapa, czyste_env, caplog):
    from PIL import Image


    a = atrapa("401")
    czyste_env.setattr(llm, "_WYLACZNIK_PRZEBIEGU", llm.Wylacznik())
    czyste_env.setenv("MODEL_TRYB", "api")
    czyste_env.setenv("LLM_API_KEY", "test")
    czyste_env.setenv("LLM_BASE_URL", a.url)
    czyste_env.setenv("OCR_MODEL", "inny-model-ocr")  # osobny klient OCR (replace), ten sam wyłącznik
    ekstrakcja, ocr = llm.klient_z_env(KONFIG), llm.klient_ocr(KONFIG)
    assert ocr is not ekstrakcja and ocr.wylacznik is ekstrakcja.wylacznik
    ekstrakcja.nowy_dokument()
    with caplog.at_level(logging.WARNING, logger="odwolania2json"):
        assert ekstrakcja("p", "tekst") is None
    assert a.zapytania == 1 and ekstrakcja.wylacznik.wylaczony
    with pytest.raises(RuntimeError, match="wyłączony"):
        ocr.przepisz_obraz(Image.new("RGB", (20, 20), "white"))
    assert a.zapytania == 1  # OCR nie pyta już API: od razu następny silnik (Tesseract)
    assert caplog.text.count("MODEL WYŁĄCZONY") == 1


def test_ocr_po_api_wlacza_wylacznik_dla_ekstrakcji(atrapa, czyste_env):
    from PIL import Image

    a = atrapa("403")
    czyste_env.setattr(llm, "_WYLACZNIK_PRZEBIEGU", llm.Wylacznik())
    czyste_env.setenv("MODEL_TRYB", "api")
    czyste_env.setenv("LLM_API_KEY", "test")
    czyste_env.setenv("LLM_BASE_URL", a.url)
    ocr = llm.klient_ocr(KONFIG)
    with pytest.raises(Exception):
        ocr.przepisz_obraz(Image.new("RGB", (20, 20), "white"))
    ekstrakcja = llm.klient_z_env(KONFIG)
    ekstrakcja.nowy_dokument()
    assert not ekstrakcja.aktywny and ekstrakcja("p", "tekst") is None
    assert a.zapytania == 1


# --- pamięć i licznik OCR (pkt 8, 9) -----------------------------------------------------------------------------

def _skan(sciezka: Path, kolor: str = "white") -> Path:
    """PDF bez warstwy tekstowej (sam obraz), jak skan."""
    from PIL import Image, ImageDraw

    obraz = Image.new("RGB", (400, 300), kolor)
    ImageDraw.Draw(obraz).rectangle((40, 40, 360, 80), fill="black")
    obraz.save(sciezka, "PDF")
    return sciezka


@pytest.fixture
def ocr_api(atrapa, czyste_env):
    """Świeży stan przebiegu (klient OCR, pamięć, licznik, wyłącznik) i model OCR za atrapą API."""
    from odwolania2json import pdftext

    def zrob(tryb):
        a = atrapa(tryb)
        czyste_env.setattr(llm, "_WYLACZNIK_PRZEBIEGU", llm.Wylacznik())
        czyste_env.setattr(pdftext, "_KLIENT_OCR", [])
        czyste_env.setattr(pdftext, "_PAMIEC_OCR", {})
        czyste_env.setattr(pdftext, "LICZNIK_OCR", pdftext.LicznikOCR())
        for k, v in {"MODEL_TRYB": "api", "LLM_API_KEY": "test", "LLM_BASE_URL": a.url, "OCR_SILNIKI": "model",
                     "OCR": "1"}.items():
            czyste_env.setenv(k, v)
        return a, pdftext
    return zrob


def test_ta_sama_strona_idzie_do_modelu_raz(tmp_path, ocr_api):
    a, pdftext = ocr_api("ocr")
    d1 = pdftext.wczytaj(_skan(tmp_path / "a.pdf"))
    d2 = pdftext.wczytaj(_skan(tmp_path / "b.pdf"))       # ten sam obraz strony w innym pliku
    d3 = pdftext.wczytaj(_skan(tmp_path / "c.pdf", "lightgray"))
    assert a.zapytania == 2
    assert d1.tekst == d2.tekst and d1.strony_ocr == d2.strony_ocr == (1,)
    assert d3.tekst != d1.tekst
    licznik = pdftext.LICZNIK_OCR
    assert (licznik.strony, licznik.z_pamieci, licznik.bledy) == (3, 1, 0)
    assert licznik.opis().startswith("OCR: 3 stron (model 3), 0 błędów, ") and "1 z pamięci" in licznik.opis()


def test_licznik_ocr_liczy_bledy_a_po_wylaczeniu_nie_pyta(tmp_path, ocr_api):
    a, pdftext = ocr_api("401")
    for i, kolor in enumerate(("white", "lightgray", "gray")):
        assert pdftext.wczytaj(_skan(tmp_path / f"{i}.pdf", kolor)).strony_ocr == ()
    assert a.zapytania == 1                                 # 401: model wyłączony, dalej bez zapytań
    assert pdftext.LICZNIK_OCR.strony == 0 and pdftext.LICZNIK_OCR.bledy == 1


def test_podsumowanie_cli_z_licznikiem_ocr(tmp_path, atrapa):
    import subprocess
    import sys

    a = atrapa("ocr")
    wej = tmp_path / "input" / "sprawa"
    wej.mkdir(parents=True)
    _skan(wej / "skan1.pdf")
    _skan(wej / "skan2.pdf")
    korzen = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(korzen / "src"), "O2J_BEZ_ENV": "1", "MODEL_TRYB": "api",
           "LLM_API_KEY": "test", "LLM_BASE_URL": a.url, "OCR_SILNIKI": "model", "OCR": "1",
           "PLIKI_WATKI": "1"}  # po kolei: drugi taki sam skan z pamięci OCR
    r = subprocess.run([sys.executable, "-m", "odwolania2json", "--input", str(tmp_path / "input"),
                        "--output", str(tmp_path / "out"), "--audit", str(tmp_path / "audit")],
                       cwd=korzen, env=env, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    linia = next(l for l in r.stderr.splitlines() if l.startswith("Podsumowanie"))
    assert "OCR: 2 stron (model 2), 0 błędów" in linia and "1 z pamięci" in linia
    assert a.zapytania >= 1 and sum("skan" in l for l in r.stderr.splitlines()) >= 2
