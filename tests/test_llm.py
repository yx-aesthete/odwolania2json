"""Adapter modelu: tryby z config/model.yaml, odporność na błędy, odpowiedź modelu musi być w tekście."""
from pathlib import Path

from odwolania2json import llm
from odwolania2json.normalizacja import osoba
from odwolania2json.silnik import Silnik, znajdz_w_tekscie

KONFIG = Path(__file__).resolve().parents[1] / "config" / "model.yaml"


def test_domyslnie_api_bez_klucza_to_same_reguly(monkeypatch):
    monkeypatch.delenv("MODEL_TRYB", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert llm.klient_z_env(KONFIG) is None


def test_domyslny_model_i_dostawca(monkeypatch):
    for z in ("MODEL_TRYB", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(z, raising=False)
    monkeypatch.setenv("LLM_API_KEY", "k")
    k = llm.klient_z_env(KONFIG)
    assert k.base_url == "https://api.scaleway.ai/v1" and k.model == "gemma-4-26b-a4b-it"
    assert k.dodatkowe == {"reasoning_effort": "none"}


def test_tryb_api_bez_adresu_to_same_reguly(monkeypatch):
    monkeypatch.setenv("MODEL_TRYB", "api")
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    assert llm.klient_z_env(KONFIG) is None


def test_tryb_api_z_env(monkeypatch):
    monkeypatch.setenv("MODEL_TRYB", "api")
    monkeypatch.setenv("LLM_BASE_URL", "https://api.example.eu/v1")
    monkeypatch.setenv("LLM_MODEL", "otwarty-model")
    monkeypatch.setenv("LLM_API_KEY", "k")
    k = llm.klient_z_env(KONFIG)
    assert k and k.base_url == "https://api.example.eu/v1" and k.model == "otwarty-model" and k.api_key == "k"


def test_tryb_lokalny_domyslny_adres(monkeypatch):
    monkeypatch.setenv("MODEL_TRYB", "lokalny")
    monkeypatch.delenv("OLLAMA_URL", raising=False)
    k = llm.klient_z_env(KONFIG)
    assert k and k.base_url == "http://127.0.0.1:11434/v1"


def test_blad_polaczenia_wylacza_model_w_dokumencie_bez_wywrotki():
    k = llm.KlientLLM(base_url="http://127.0.0.1:9/v1", model="x", timeout_s=1, max_bledow=2, proby=())
    k.nowy_dokument()
    assert k("pytanie", "tekst a") is None
    assert k("pytanie", "tekst b") is None
    assert not k.aktywny
    assert k("pytanie", "tekst c") is None and k.bledy == 2  # po limicie: bez kolejnych prób w tym dokumencie
    k.nowy_dokument()                                          # następny dokument: model znowu próbuje
    assert k.aktywny
    assert k("pytanie", "tekst d") is None and k.bledy == 3
    assert "2 dokumentów bez modelu" in k.podsumowanie() or "1 dokumentów bez modelu" in k.podsumowanie()


def test_ponowienie_przy_429(monkeypatch):
    import io
    import urllib.error
    k = llm.KlientLLM(base_url="https://x.example/v1", model="m", proby=(0, 0))
    wywolania = []
    def falszywy(cialo, naglowki):
        wywolania.append(1)
        if len(wywolania) < 3:
            raise urllib.error.HTTPError("u", 429, "Too Many", {}, io.BytesIO(b""))
        return {"choices": [{"message": {"content": "Gmina Kielce"}}]}
    monkeypatch.setattr(k, "_wyslij_raz", falszywy)
    k.nowy_dokument()
    assert k("p", "tekst") == "Gmina Kielce" and len(wywolania) == 3 and k.bledy == 0


def test_wczytaj_env_nie_nadpisuje_srodowiska(tmp_path, monkeypatch):
    plik = tmp_path / ".env"
    plik.write_text('# komentarz\nLLM_MODEL="z-pliku"\nZMIENNA_TESTOWA_O2J=1\n', encoding="utf-8")
    monkeypatch.setenv("LLM_MODEL", "ze-srodowiska")
    monkeypatch.delenv("ZMIENNA_TESTOWA_O2J", raising=False)
    llm.wczytaj_env(plik)
    import os
    assert os.environ["LLM_MODEL"] == "ze-srodowiska" and os.environ["ZMIENNA_TESTOWA_O2J"] == "1"
    monkeypatch.delenv("ZMIENNA_TESTOWA_O2J")


def test_oczysc_odpowiedz():
    assert llm.oczysc_odpowiedz("BRAK") is None
    assert llm.oczysc_odpowiedz("brak.") is None
    assert llm.oczysc_odpowiedz("„Gmina Kielce”") == "Gmina Kielce"
    assert llm.oczysc_odpowiedz("<think>hmm</think>Odpowiedź: RZP.1.2025") == "RZP.1.2025"


def test_znajdz_w_tekscie():
    t = "Zamawiający:\nGmina   Miasto\nKielce, ul. Rynek 1"
    od, do = znajdz_w_tekscie("gmina miasto kielce", t)
    assert t[od:do].split() == ["Gmina", "Miasto", "Kielce"]
    assert znajdz_w_tekscie("Gmina Radom", t) is None


def test_silnik_odrzuca_odpowiedz_spoza_tekstu():
    spec = {"wynik": {"a": {"metody": [{"regex": "NIE MA"}, {"llm": "?"}]}}}
    tekst = "Zamawiający: Gmina Kielce, ul. Rynek 1"
    assert Silnik(spec, lambda p, t: "Gmina Radom").ekstrahuj(tekst).dane == {"a": None}
    w = Silnik(spec, lambda p, t: "Gmina Kielce").ekstrahuj(tekst)
    assert w.dane == {"a": "Gmina Kielce"}
    assert w.dowody[0].cytat == "Gmina Kielce" and w.dowody[0].metoda == "llm#1"


def test_walidator_osoby():
    assert osoba("Jan Kowalski") == "Jan Kowalski"
    assert osoba("Anna Nowak-Wiśniewska") == "Anna Nowak-Wiśniewska"
    assert osoba("ią EM") is None


def test_kotwica_sekcji_z_modelu_gdy_brak_etykiety():
    spec = {
        "sekcje": {"strona": {"od": "ETYKIETA_KTOREJ_NIE_MA", "llm": "nazwa?", "do": ["\\n\\n"]}},
        "wynik": {"nip": {"metody": [{"regex": "NIP (?P<v>\\d{10})", "w": "strona"}]}},
    }
    tekst = "Nagłówek\nAlfa sp. z o.o.\nNIP 1234567890\n\nBeta S.A.\nNIP 9999999999"
    assert Silnik(spec, None).ekstrahuj(tekst).dane == {"nip": None}
    assert Silnik(spec, lambda p, t: "Beta S.A.").ekstrahuj(tekst).dane == {"nip": "9999999999"}
    assert Silnik(spec, lambda p, t: "Gamma").ekstrahuj(tekst).dane == {"nip": None}  # spoza tekstu: brak sekcji


def test_klucz_nie_trafia_do_repr():
    k = llm.KlientLLM(base_url="https://x.example/v1", model="m", api_key="TAJNY-KLUCZ")
    assert "TAJNY-KLUCZ" not in repr(k) and "TAJNY-KLUCZ" not in k.opis


def test_pamiec_nie_zapisuje_bledu(monkeypatch):
    import urllib.error
    k = llm.KlientLLM(base_url="https://x.example/v1", model="m", proby=(), max_bledow=5)
    odpowiedzi = [urllib.error.URLError("awaria"), {"choices": [{"message": {"content": "Gmina Kielce"}}]}]
    def falszywy(cialo, naglowki):
        o = odpowiedzi.pop(0)
        if isinstance(o, Exception):
            raise o
        return o
    monkeypatch.setattr(k, "_wyslij_raz", falszywy)
    k.nowy_dokument()
    assert k("p", "tekst") is None
    assert k("p", "tekst") == "Gmina Kielce"  # po błędzie pytanie idzie ponownie


def test_awaria_modelu_przy_klasyfikacji_to_klasa_z_regul():
    from odwolania2json.klasy import BLAD_MODELU, UstawieniaKlasyfikacji, rozpoznaj, wczytaj_klasy
    klasy = wczytaj_klasy(KONFIG.parent / "klasy")
    ust = UstawieniaKlasyfikacji(min_punkty=1, przewaga=99)
    tekst = ("Potwierdzenie przelewu kwota 100,00 zł na rachunek PL61 1090 1014 0000 0712 1981 2874 tytułem wpis, "
             "data operacji 02.03.2026")
    r = rozpoznaj(tekst, klasy, ust, wybor_modelu=lambda t, k: BLAD_MODELU)
    assert r.klasa is not None and r.klasa.nazwa == "przelew"


def test_osobny_model_ocr(monkeypatch):
    for z in ("MODEL_TRYB", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(z, raising=False)
    monkeypatch.setenv("LLM_API_KEY", "k")
    monkeypatch.delenv("OCR_MODEL", raising=False)
    assert [k.model for k in llm.klienci_ocr(KONFIG)] == ["mistral-small-3.2-24b-instruct-2506", "gemma-4-26b-a4b-it"]  # domyślnie Mistral, zapas Gemma
    monkeypatch.setenv("OCR_MODEL", "mistral-small-3.2-24b-instruct-2506")
    k = llm.klient_ocr(KONFIG)
    assert k.model == "mistral-small-3.2-24b-instruct-2506" and k.api_key == "k"
    monkeypatch.setenv("OCR_MODEL", "lightonocr-3-0.8b, mistral-small-3.2-24b-instruct-2506")
    assert [k.model for k in llm.klienci_ocr(KONFIG)] == ["lightonocr-3-0.8b", "mistral-small-3.2-24b-instruct-2506"]


def test_bez_markdown_w_odpowiedzi_ocr():
    t = "## Potwierdzenie\n| Z rachunku | 68 1090 1505 |\n|------------|-------------|\n| **Kwota przelewu** | 10 000,00 PLN |\nZwykła linia"
    assert llm.bez_markdown(t) == "Potwierdzenie\nZ rachunku  68 1090 1505\nKwota przelewu  10 000,00 PLN\nZwykła linia"
