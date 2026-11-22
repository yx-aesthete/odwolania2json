"""Siatka modelu (metody `llm` z `siatka: true`): przelew (data, kwota, tytuł, rachunek odbiorcy) i czynność odwołania.

Warunki: model pytany tylko, gdy reguły pola nic nie dały; odpowiedź przyjęta tylko, gdy stoi w dokumencie
(`kandydaci`, `sprawdz: doslownie`) albo jest pozycją listy zamkniętej (`z_slownika`); BRAK i wszystko inne = null;
przełącznik `siatka_modelu` (config/aplikacja.yaml, zmienna SIATKA_MODELU) wyłącza całą ścieżkę.
Tekst syntetyczny, dane fikcyjne; model zastępuje atrapa w pamięci.
"""
import json
import re
import shutil
from pathlib import Path

import pytest
import yaml

from odwolania2json import llm as modul_llm
from odwolania2json.potok import Potok

KORZEN = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _siatka_wlaczona(monkeypatch):
    """Testy zachowania siatki nie zależą od ustawienia w config/aplikacja.yaml (przełącznik wolno przestawić):
    siatka włączona zmienną; testy przełącznika ustawiają zmienną i YAML same."""
    monkeypatch.setenv("SIATKA_MODELU", "1")


def pytania_siatki(katalog: Path = KORZEN / "config" / "klasy") -> list[str]:
    """Teksty pytań wszystkich metod `llm` oznaczonych `siatka: true` w YAML klas."""
    wynik: list[str] = []

    def zbierz(o):
        if isinstance(o, dict):
            if o.get("siatka") and "llm" in o:
                wynik.append(str(o["llm"]))
            for v in o.values():
                zbierz(v)
        elif isinstance(o, list):
            for v in o:
                zbierz(v)
    for plik in sorted(katalog.glob("*.yaml")):
        zbierz(yaml.safe_load(plik.read_text(encoding="utf-8")))
    return wynik


class Atrapa:
    """Model w pamięci: pierwsza odpowiedź, której wzorzec pasuje do pytania; brak dopasowania = None (BRAK)."""
    opis = "atrapa"

    def __init__(self, odpowiedzi=(), json_dokumentu=None):
        self.odpowiedzi, self.json_dokumentu, self.pytania = list(odpowiedzi), json_dokumentu, []

    def nowy_dokument(self):
        pass

    def koniec_dokumentu(self):
        pass

    def wybierz_klase(self, tekst, klasy):
        return None

    def zapytaj_json(self, polecenie, tekst, max_tokens=1500):
        self.pytania.append("JSON")
        return self.json_dokumentu

    def __call__(self, pytanie, tekst):
        self.pytania.append(pytanie)
        return next((odp for wz, odp in self.odpowiedzi if re.search(wz, pytanie, re.I)), None)

    def siatki(self) -> list[str]:
        """Zadane pytania należące do siatki modelu (po początku pytania z YAML)."""
        znane = pytania_siatki()
        return [p for p in self.pytania if any(p.startswith(z) for z in znane)]


def potok(atrapa=None, katalog: Path = KORZEN / "config" / "klasy") -> Potok:
    p = Potok(katalog, uzyj_llm=False)
    p.llm = atrapa
    return p


SZKODNIK = [(r".", "31.12.2031")]   # na każde pytanie odpowiada czymś, czego nie ma w dokumencie

PRZELEW_ZNANE_ETYKIETY = """Bank Testowy S.A.
Potwierdzenie wykonania przelewu
Z rachunku: 11 1111 1111 1111 1111 1111 1111
Na rachunek: 22 2222 2222 2222 2222 2222 2222
Kwota: 17,00 PLN
Data operacji: 05.03.2026
Tytuł: opłata skarbowa od pełnomocnictwa w przetargu ZP.1.2026
"""

PRZELEW_NIEZNANE_ETYKIETY = """Bank Testowy S.A.
Potwierdzenie wykonania przelewu
Wydruk z dnia 6 marca 2026
Zleceniodawca płatności: ALFA SERWIS SP. Z O.O.
Konto źródłowe: 11 1111 1111 1111 1111 1111 1111
Odbiorca płatności: Urząd Miasta Testowo
Konto docelowe: 22 2222 2222 2222 2222 2222 2222
Suma: 17,00
Waluta: PLN
Dzień wykonania: 5 marca 2026
Cel płatności: należność za pełnomocnictwo
w przetargu ZP.1.2026
Status: zrealizowany
"""

PRZELEW_JEDEN_RACHUNEK = """Bank Testowy S.A.
Potwierdzenie wpłaty gotówkowej
Wpłacający: ALFA SERWIS SP. Z O.O.
Konto docelowe odbiorcy: PL22 2222 2222 2222 2222 2222 2222
Kwota: 17,00 PLN
Data operacji: 05.03.2026
Tytuł: opłata skarbowa od pełnomocnictwa
"""


# ---------------------------------------------------------------- przelew
def test_przelew_regula_dala_wartosc_model_nie_jest_pytany():
    a = Atrapa(SZKODNIK)
    bez = potok().przetworz_tekst(PRZELEW_ZNANE_ETYKIETY)
    z = potok(a).przetworz_tekst(PRZELEW_ZNANE_ETYKIETY)
    assert bez.dane["przelew_bankowy"]["data_operacji"] == "2026-03-05"
    assert z.dane == bez.dane and a.pytania == []          # żadnego zapytania, wynik reguł bez zmian


def test_przelew_reguly_puste_odpowiedz_z_dokumentu_przyjeta():
    bez = potok().przetworz_tekst(PRZELEW_NIEZNANE_ETYKIETY).dane["przelew_bankowy"]
    assert bez["data_operacji"] is None and bez["tytul"] is None and bez["kwota"] is None   # same reguły: braki
    a = Atrapa([(r"dat[ęe] operacji", "2026-03-05"),          # model sam znormalizował datę („5 marca 2026” w tekście)
                (r"kwot[ęe] przelewu", "17.00"),              # i kwotę („17,00” w tekście)
                (r"tytuł przelewu", "należność za pełnomocnictwo w przetargu ZP.1.2026")])
    w = potok(a).przetworz_tekst(PRZELEW_NIEZNANE_ETYKIETY).dane["przelew_bankowy"]
    assert w["data_operacji"] == "2026-03-05" and w["kwota"] == 17.0
    assert w["tytul"] == "należność za pełnomocnictwo w przetargu ZP.1.2026"   # tytuł złamany w dokumencie
    # rachunki znalazły reguły: wartości z reguł, bez pytania; numer transakcji: brak i też bez pytania
    assert w["z_rachunku"] == "11111111111111111111111111" and w["na_rachunek"] == "22222222222222222222222222"
    assert w["numer_transakcji"] is None
    assert len(a.pytania) == 3 and len(a.siatki()) == 3
    assert not any(re.search(r"rachun|numer|identyfikator", p, re.I) for p in a.pytania)


def test_przelew_odpowiedz_spoza_dokumentu_to_null():
    a = Atrapa([(r"dat[ęe] operacji", "2026-03-07"),          # takiej daty nie ma w dokumencie
                (r"kwot[ęe] przelewu", "34,00"),              # ani takiej kwoty
                (r"tytuł przelewu", "wpis od odwołania w sprawie KIO 123/26")])
    w = potok(a).przetworz_tekst(PRZELEW_NIEZNANE_ETYKIETY).dane["przelew_bankowy"]
    assert len(a.siatki()) == 3                                # model był pytany, odpowiedzi odrzucone
    assert w["data_operacji"] is None and w["kwota"] is None and w["tytul"] is None


def test_przelew_tytul_tylko_doslownie_z_dokumentu():
    # jedna litera inaczej niż w dokumencie (podobieństwo > 92%): odrzucone, bez dopasowania przybliżonego
    a = Atrapa([(r"tytuł przelewu", "należność za pełnomocnictwo w przetargu ZP.2.2026")])
    assert potok(a).przetworz_tekst(PRZELEW_NIEZNANE_ETYKIETY).dane["przelew_bankowy"]["tytul"] is None
    assert len(a.siatki()) == 3
    # inna wielkość liter i odstępy: przyjęte, wartością jest zapis z dokumentu
    a = Atrapa([(r"tytuł przelewu", "NALEŻNOŚĆ ZA  pełnomocnictwo")])
    assert potok(a).przetworz_tekst(PRZELEW_NIEZNANE_ETYKIETY).dane["przelew_bankowy"]["tytul"] == \
        "należność za pełnomocnictwo"


def test_przelew_rachunek_odbiorcy_z_modelu_z_pl_jak_w_dokumencie():
    # jeden rachunek w dokumencie: reguła pozycyjna bierze go jako rachunek nadawcy (z PL, jak stoi: Z44), rachunku odbiorcy nie ma
    bez = potok().przetworz_tekst(PRZELEW_JEDEN_RACHUNEK).dane["przelew_bankowy"]
    assert bez["na_rachunek"] is None and bez["z_rachunku"] == "PL22222222222222222222222222"
    for odpowiedz in ("22222222222222222222222222", "PL22 2222 2222 2222 2222 2222 2222"):
        a = Atrapa([(r"rachunku odbiorcy", odpowiedz)])
        w = potok(a).przetworz_tekst(PRZELEW_JEDEN_RACHUNEK).dane["przelew_bankowy"]
        # odpowiedź z PL albo bez PL: wartością jest zapis z dokumentu, ten sam co z reguł (Z44: PL, bo stoi w dokumencie)
        assert w["na_rachunek"] == "PL22222222222222222222222222", odpowiedz
        assert len(a.siatki()) == 1                                      # tylko o rachunek, którego reguły nie dały
    a = Atrapa([(r"rachunku odbiorcy", "33 3333 3333 3333 3333 3333 3333")])   # rachunku nie ma w dokumencie
    assert potok(a).przetworz_tekst(PRZELEW_JEDEN_RACHUNEK).dane["przelew_bankowy"]["na_rachunek"] is None
    assert len(a.siatki()) == 1


def test_przelew_rachunek_nadawcy_bez_pytania():
    # żadnego czytelnego rachunku w dokumencie (OCR): o rachunek nadawcy model nie jest pytany, pole zostaje puste
    tekst = PRZELEW_ZNANE_ETYKIETY.replace("11 1111 1111 1111 1111 1111 1111", "11 1111 l111 1111 1111 1111 1111").replace(
        "22 2222 2222 2222 2222 2222 2222", "22 2222 2222 2222 2222 2222 222O")
    a = Atrapa([(r"rachunku", "11 1111 1111 1111 1111 1111 1111")])
    w = potok(a).przetworz_tekst(tekst).dane["przelew_bankowy"]
    assert w["z_rachunku"] is None and w["na_rachunek"] is None
    assert not any("rachunku nadawcy" in p for p in a.pytania)
    assert w["data_operacji"] == "2026-03-05" and w["kwota"] == 17.0      # pola z reguł bez zmian


# ---------------------------------------------------------------- odwołanie: czynność
ODWOLANIE = """Testowo, 10.03.2026 r.
Prezes Krajowej Izby Odwoławczej
ul. Postępu 17A, 02-676 Warszawa
Odwołujący: Alfa Serwis sp. z o.o.
ul. Długa 5, 00-001 Testowo
KRS: 9990000001, NIP: 9990000002, REGON: 999000003
reprezentowany przez pełnomocnika:
radca prawny Jan Testowy
adres do korespondencji:
Kancelaria Radcy Prawnego Jan Testowy
ul. Krótka 2, 00-002 Testowo
e-mail: j.testowy@kancelaria-testowa.example
Zamawiający: Gmina Testowo
ul. Rynek 1, 00-001 Testowo
Dotyczy: postępowania pn. „Budowa drogi gminnej w Testowie”, nr referencyjny: ZP.1.2026
ODWOŁANIE
Działając w imieniu Odwołującego – Alfa Serwis sp. z o.o. (dalej: „Odwołujący”), {czynnosc}
Zarzucam naruszenie art. 226 ust. 1 pkt 5 Pzp.
"""
CZYNNOSC_ZNANA = ("wnoszę odwołanie wobec:\n1. czynności odrzucenia oferty Odwołującego, o której poinformowano "
                  "w dniu 02.03.2026 r.;")
CZYNNOSC_NIEZNANA = "skarżę rozstrzygnięcie Zamawiającego z 02.03.2026 r. kończące przetarg bez wyłonienia wykonawcy."
P_KOD, P_DATA = r"Której czynności", r"datę pierwszej zaskarżonej czynności"


def _czynnosc(odpowiedzi, tekst=None):
    a = Atrapa(odpowiedzi)
    w = potok(a).przetworz_tekst(tekst or ODWOLANIE.format(czynnosc=CZYNNOSC_NIEZNANA)).dane["OdwolanieKIO"]
    return (w["czynnosc_powod_id"], w["czynnosc_opis"], w["czynnosc_dzien"]), a


def test_odwolanie_regula_dala_czynnosc_model_nie_jest_pytany_o_czynnosc():
    tekst = ODWOLANIE.format(czynnosc=CZYNNOSC_ZNANA)
    bez = potok().przetworz_tekst(tekst).dane
    assert bez["OdwolanieKIO"]["czynnosc_powod_id"] == 1 and bez["OdwolanieKIO"]["czynnosc_dzien"] == "2026-03-02"
    a = Atrapa([(r".", "Gmina Testowo")])
    z = potok(a).przetworz_tekst(tekst).dane
    assert z["OdwolanieKIO"] == bez["OdwolanieKIO"] and a.siatki() == []


def test_odwolanie_czynnosc_z_modelu_przyjeta_gdy_reguly_puste():
    bez = potok().przetworz_tekst(ODWOLANIE.format(czynnosc=CZYNNOSC_NIEZNANA)).dane["OdwolanieKIO"]
    assert bez["czynnosc_powod_id"] is None and bez["czynnosc_opis"] is None and bez["czynnosc_dzien"] is None
    w, a = _czynnosc([(P_KOD, "9"), (P_DATA, "2 marca 2026")])
    assert w == (9, "Decyzja o unieważnieniu postępowania", "2026-03-02")   # „02.03.2026” w dokumencie
    assert "9 – Decyzja o unieważnieniu postępowania" in next(p for p in a.pytania if re.search(P_KOD, p))
    # odpowiedź opisem pozycji albo całą linią listy „numer – opis” też wskazuje pozycję
    assert _czynnosc([(P_KOD, "decyzja o unieważnieniu postępowania")])[0][:2] == (9, "Decyzja o unieważnieniu postępowania")
    assert _czynnosc([(P_KOD, "9 – Decyzja o unieważnieniu postępowania")])[0][:2] == (9, "Decyzja o unieważnieniu postępowania")


def test_odwolanie_kod_spoza_listy_brak_i_data_spoza_dokumentu_to_null():
    for kod in ("13", "0", "BRAK", "9 albo 10", "2 marca 2026", "unieważnienie przetargu", "9 – Decyzja o odrzuceniu oferty"):
        w, a = _czynnosc([(P_KOD, kod), (P_DATA, "3 marca 2026")])           # 3 marca nie ma w dokumencie
        assert w == (None, None, None), kod
        assert len(a.siatki()) == 3                                          # pytany o id, opis i dzień
    assert _czynnosc([(P_DATA, "BRAK")])[0] == (None, None, None)


def test_brak_z_klienta_to_null_a_kod_i_opis_to_jedno_zapytanie(monkeypatch):
    """Prawdziwy klient (bez sieci): „BRAK” = null w każdym polu siatki; id i opis czynności = jedno zapytanie."""
    wyslane = []

    def wyslij(self, cialo, naglowki):
        wyslane.append(cialo["messages"][-1]["content"])
        return {"choices": [{"message": {"content": "BRAK"}}]}
    monkeypatch.setattr(modul_llm.KlientLLM, "_wyslij", wyslij)
    monkeypatch.setattr(modul_llm.KlientLLM, "zapytaj_json", lambda self, polecenie, tekst, max_tokens=1500: None)
    p = Potok(KORZEN / "config" / "klasy", uzyj_llm=False)
    p.llm = modul_llm.KlientLLM(base_url="http://127.0.0.1:9/v1", model="x")
    w = p.przetworz_tekst(PRZELEW_NIEZNANE_ETYKIETY).dane["przelew_bankowy"]
    assert w["data_operacji"] is None and w["kwota"] is None and w["tytul"] is None and len(wyslane) == 3
    wyslane.clear()
    w = p.przetworz_tekst(ODWOLANIE.format(czynnosc=CZYNNOSC_NIEZNANA)).dane["OdwolanieKIO"]
    assert (w["czynnosc_powod_id"], w["czynnosc_opis"], w["czynnosc_dzien"]) == (None, None, None)
    assert sum("Której czynności" in t for t in wyslane) == 1          # id i opis: to samo pytanie, pamięć klienta
    assert sum("datę pierwszej zaskarżonej czynności" in t for t in wyslane) == 1


# ---------------------------------------------------------------- przełącznik
DOBRE = [(r"dat[ęe] operacji", "05.03.2026"), (r"kwot[ęe] przelewu", "17,00"),
         (r"tytuł przelewu", "należność za pełnomocnictwo"), (P_KOD, "9"), (P_DATA, "02.03.2026")]


def _konfiguracja(tmp_path: Path, wlaczona: bool) -> Path:
    """Kopia config/ z przełącznikiem `siatka_modelu` ustawionym w aplikacja.yaml; zwraca katalog klas."""
    shutil.copytree(KORZEN / "config", tmp_path / "config")
    plik = tmp_path / "config" / "aplikacja.yaml"
    tresc = re.sub(r"(?m)^siatka_modelu:.*$", "", plik.read_text(encoding="utf-8"))
    plik.write_text(tresc + f"\nsiatka_modelu: {'true' if wlaczona else 'false'}\n", encoding="utf-8")
    return tmp_path / "config" / "klasy"


def _oba_dokumenty(katalog: Path = KORZEN / "config" / "klasy"):
    a = Atrapa(DOBRE)
    p = potok(a, katalog)
    return p.przetworz_tekst(PRZELEW_NIEZNANE_ETYKIETY).dane, p.przetworz_tekst(ODWOLANIE.format(czynnosc=CZYNNOSC_NIEZNANA)).dane, a


def test_przelacznik_domyslnie_wlaczony(monkeypatch, tmp_path):
    from odwolania2json.potok import siatka_modelu
    monkeypatch.delenv("SIATKA_MODELU")
    konf = yaml.safe_load((KORZEN / "config" / "aplikacja.yaml").read_text(encoding="utf-8"))
    assert isinstance(konf["siatka_modelu"], bool)                  # klucz jest w pliku (jedna linijka do przestawienia)
    assert siatka_modelu(tmp_path / "brak-pliku.yaml") is True      # brak klucza albo pliku: włączona
    przelew, odwolanie, a = _oba_dokumenty(_konfiguracja(tmp_path, True))
    assert przelew["przelew_bankowy"]["data_operacji"] == "2026-03-05" and odwolanie["OdwolanieKIO"]["czynnosc_powod_id"] == 9
    assert len(a.siatki()) == 6


def test_przelacznik_wylaczony_zmienna_zero_zapytan_i_wynik_samych_regul(monkeypatch):
    znane = pytania_siatki()
    assert len(znane) == 7                                   # 4 pola przelewu + 3 pola czynności
    monkeypatch.setenv("SIATKA_MODELU", "0")
    przelew, odwolanie, a = _oba_dokumenty()
    assert a.siatki() == []
    assert not any(re.search(r"przelewu|Której czynności|zaskarżonej czynności", p) for p in a.pytania)
    assert przelew == potok().przetworz_tekst(PRZELEW_NIEZNANE_ETYKIETY).dane          # przelew: dokładnie same reguły
    assert odwolanie["OdwolanieKIO"] == potok().przetworz_tekst(ODWOLANIE.format(czynnosc=CZYNNOSC_NIEZNANA)).dane["OdwolanieKIO"]


def test_przelacznik_w_yaml_jedna_linijka_a_zmienna_nadpisuje(monkeypatch, tmp_path):
    monkeypatch.delenv("SIATKA_MODELU")
    wylaczone = _konfiguracja(tmp_path / "wyl", False)
    przelew, odwolanie, a = _oba_dokumenty(wylaczone)
    assert a.siatki() == [] and przelew["przelew_bankowy"]["data_operacji"] is None
    assert odwolanie["OdwolanieKIO"]["czynnosc_powod_id"] is None
    monkeypatch.setenv("SIATKA_MODELU", "1")                 # zmienna nadpisuje YAML
    przelew, _, a = _oba_dokumenty(wylaczone)
    assert len(a.siatki()) == 6 and przelew["przelew_bankowy"]["data_operacji"] == "2026-03-05"
    monkeypatch.setenv("SIATKA_MODELU", "0")
    wlaczone = _konfiguracja(tmp_path / "wl", True)
    assert _oba_dokumenty(wlaczone)[2].siatki() == []


# ---------------------------------------------------------------- współdziałanie z wariantem szerokim
def test_siatka_nie_zmienia_pol_wariantu_szerokiego(monkeypatch):
    """Kolejność: reguły pola -> siatka (gdy pole puste) -> arbitraż szeroki. Pola siatki i pola wariantu szerokiego
    są rozłączne: te same wartości pól szerokich przy włączonej i wyłączonej siatce, czynność tylko z siatki."""
    tekst = ODWOLANIE.format(czynnosc=CZYNNOSC_NIEZNANA)
    szeroki = json.dumps({"Odwolujacy": [{"nazwa": "Alfa Serwis sp. z o.o.", "pelnomocnik": {
        "imie_nazwisko": "Jan Testowy", "nazwa": "Kancelaria Radcy Prawnego Jan Testowy",
        "mail": "j.testowy@kancelaria-testowa.example"}}], "Zamawiajacy": [{"nazwa": "Gmina Testowo"}],
        "ZamowieniePubliczne": {"tytul": "Budowa drogi gminnej w Testowie"},
        "OdwolanieKIO": {"czynnosc_powod_id": 3, "czynnosc_opis": "Decyzja o wykluczeniu wykonawcy",
                         "czynnosc_dzien": "2026-03-10"}}, ensure_ascii=False)   # model szeroki nie ma głosu w czynności
    klasa = yaml.safe_load((KORZEN / "config" / "klasy" / "odwolanie.yaml").read_text(encoding="utf-8"))
    assert klasa["model_szeroki"]["wlaczony"] is True
    assert not any(p.startswith("OdwolanieKIO") for p in klasa["model_szeroki"]["pola"])
    a_wl = Atrapa([(P_KOD, "9"), (P_DATA, "02.03.2026")], json_dokumentu=szeroki)
    wl = potok(a_wl).przetworz_tekst(tekst).dane
    monkeypatch.setenv("SIATKA_MODELU", "0")
    a_wyl = Atrapa([(P_KOD, "9"), (P_DATA, "02.03.2026")], json_dokumentu=szeroki)
    wyl = potok(a_wyl).przetworz_tekst(tekst).dane
    assert a_wl.pytania[-1] == "JSON" and a_wyl.pytania == ["JSON"]      # arbitraż szeroki po polach, raz na dokument
    for klucz in ("Odwolujacy", "Zamawiajacy", "ZamowieniePubliczne"):
        assert wl[klucz] == wyl[klucz], klucz
    czynnosc = {k: v for k, v in wl["OdwolanieKIO"].items() if k.startswith("czynnosc")}
    assert czynnosc == {"czynnosc_dzien": "2026-03-02", "czynnosc_powod_id": 9,
                        "czynnosc_opis": "Decyzja o unieważnieniu postępowania"}
    assert all(wyl["OdwolanieKIO"][k] is None for k in czynnosc)


def test_kandydat_kwoty_nie_z_daty():
    """Model odpowiada fragmentem daty: „30.03” przy „30.03.2026” i „6” przy „6 marca 2026” nie są kwotą (Z46)."""
    from odwolania2json.silnik import Silnik
    import yaml
    from pathlib import Path
    spec = yaml.safe_load((Path(__file__).resolve().parents[1] / "config/klasy/przelew.yaml").read_text(encoding="utf-8"))
    tekst = "Historia rachunku\nZlecono: 30.03.2026\nDzień: 6 marca 2026\nSuma do zapłaty\nbez waluty\n"
    for odp in ("30.03", "6", "2026"):
        class M:
            def __call__(self, pytanie, t):
                return odp if "kwot" in pytanie.lower() else None
            def __getattr__(self, n):
                return lambda *a, **k: None
        wynik = Silnik(spec, M()).ekstrahuj(tekst)
        assert (wynik.dane.get("przelew_bankowy") or {}).get("kwota") is None, odp
