"""Router pism (router.py, sekcja `router_prozy` w config/klasy/odwolanie.yaml, przełącznik `router_prozy`).

- układ generatora UZP: reguły bez zmian, 0 zapytań routera;
- długie pismo prozą: czynność, opis i dzień z jednego zapytania (lista zamknięta, data musi stać w tekście);
- numer TED w zapisach „RRRR/S NNN-NNNNNN”, „NNNNNN- RRRR”, „Dz.U. S”, „OJ S”;
- ROUTER_PROZY=0: wynik jak bez routera.
Dane fikcyjne; model zastępuje atrapa.
"""
import json
from pathlib import Path

import pytest
import yaml

from odwolania2json import router
from odwolania2json.potok import Potok

KORZEN = Path(__file__).resolve().parents[1]
SPEC = yaml.safe_load((KORZEN / "config/klasy/odwolanie.yaml").read_text(encoding="utf-8"))["router_prozy"]

WYPELNIACZ = ("Odwołujący wskazuje, że zamawiający jest obowiązany przygotować i przeprowadzić postępowanie w sposób "
              "zapewniający zachowanie uczciwej konkurencji oraz równe traktowanie wykonawców. ") * 12

STRONY_PROZY = (
    "Kraków, 14 marca 2026 r.\nPrezes Krajowej Izby Odwoławczej\nul. Postępu 17A, 02-676 Warszawa\n"
    "Odwołujący: Fikcja Serwis sp. z o.o., ul. Zmyślona 1, 00-001 Warszawa, KRS 0000000001\n"
    "Zamawiający: Gmina Przykładowo, ul. Rynek 1, 00-002 Przykładowo\n"
    "ODWOŁANIE\ndotyczy postępowania pn. „Dostawa ławek parkowych”, nr referencyjny ZP.1.2026, "
    "ogłoszenie opublikowane w Dzienniku Urzędowym Unii Europejskiej pod numerem 2026/S 041-012345.\n"
    "Działając w imieniu Odwołującego, wnoszę odwołanie wobec czynności Zamawiającego polegającej na "
    "wyborze jako najkorzystniejszej oferty wykonawcy Inny Przykład S.A. Zamawiający w dniu 3 marca 2026 r. "
    "przekazał wykonawcom informację o wyborze oferty najkorzystniejszej.\n"
    "Zarzucam Zamawiającemu naruszenie art. 239 ust. 1 Pzp poprzez wybór oferty, która nie jest najkorzystniejsza.\n",
    "UZASADNIENIE\n" + WYPELNIACZ,
    WYPELNIACZ,
    "Załączniki: pełnomocnictwo, dowód uiszczenia wpisu.\n" + WYPELNIACZ,
)


class Atrapa:
    """Model w pamięci: zapytanie routera (znacznik w poleceniu) dostaje `odpowiedz`; reszta = brak."""
    opis = "atrapa"

    def __init__(self, odpowiedz=None):
        self.odpowiedz, self.router = odpowiedz, 0

    def nowy_dokument(self):
        pass

    def koniec_dokumentu(self):
        pass

    def wybierz_klase(self, tekst, klasy):
        return None

    def zapytaj_json(self, polecenie, tekst, max_tokens=1500):
        if router.ZNACZNIK_POLECENIA in polecenie:
            self.router += 1
            return self.odpowiedz
        return None

    def __call__(self, pytanie, tekst):
        return None


@pytest.fixture(autouse=True)
def _router_wlaczony(monkeypatch):
    monkeypatch.setenv("ROUTER_PROZY", "1")
    monkeypatch.delenv("ROUTER_NADPISUJ", raising=False)


def _potok(atrapa):
    p = Potok(KORZEN / "config" / "klasy", uzyj_llm=False)
    p.llm = atrapa
    return p


def _odwolanie(potok, strony=STRONY_PROZY):
    w = potok.przetworz_tekst("\n".join(strony), strony)
    assert w.klasa == "odwolanie"
    return w


# ---------- wykrywacz ----------

def test_dlugie_pismo_bez_zdan_szablonu_to_proza():
    jest, syg = router.czy_proza("\n".join(STRONY_PROZY), STRONY_PROZY, SPEC["wykrywacz"])
    assert jest and syg["uklad_uzp"] == 0


def test_zdanie_szablonu_uzp_mimo_bledow_ocr_to_uklad_uzp():
    strony = STRONY_PROZY[:1] + ("Kopia odwolania zostala przekazana Zamawiajacemu przed uplywem terminu.\n",) + STRONY_PROZY[1:]
    assert router.czy_proza("\n".join(strony), strony, SPEC["wykrywacz"])[0] is False


def test_krotkie_pismo_to_uklad_uzp():
    assert router.czy_proza(STRONY_PROZY[0], STRONY_PROZY[:1], SPEC["wykrywacz"])[0] is False


# ---------- TED ----------

@pytest.mark.parametrize("zapis, oczekiwany", [
    ("ogłoszenie w Dz.U. UE S pod numerem 2025/S 017-051234", "051234-2025"),
    ("opublikowane w Dzienniku Urzędowym UE pod nr 2025/S 17-51234", "51234-2025"),
    ("Ogłoszenie nr Dz.U. S: 120/2026 z dnia 25/06/2026 Nr 123456-2026", "123456-2026"),
    ("numer ogłoszenia w Dzienniku Urzędowym UE: 654321- 2026", "654321-2026"),
    ("OJ S 041/2026, publication number 222333-2026", "222333-2026"),
    ("Numer publikacji ogłoszenia: 777888-2026, numer wydania Dz.U. S: 12/2026", "777888-2026"),
])
def test_numer_ted_zapisy(zapis, oczekiwany):
    assert router.numer_ted("Dotyczy postępowania.\n" + zapis + "\n", SPEC["ted"]) == oczekiwany


def test_numer_ted_nie_z_bzp_ani_bez_slowa_kluczowego():
    assert router.numer_ted("ogłoszenie w BZP nr 2026/BZP 00123456/01, numer 123456-2026", SPEC["ted"]) is None
    assert router.numer_ted("faktura 123456-2026 z dnia 1.01.2026", SPEC["ted"]) is None


def test_numer_ted_innego_postepowania_pominiety():
    t = ("W postępowaniu prowadzonym przez inny podmiot, ogłoszonym w Dzienniku Urzędowym UE pod numerem 2025/S\n"
         "233-998150, zamawiający postawił podobne wymagania.")
    assert router.numer_ted(t, SPEC["ted"]) is None


def test_ted_z_routera_tylko_w_piśmie_prozą():
    krotkie = (STRONY_PROZY[0],)
    w = _potok(Atrapa()).przetworz_tekst(krotkie[0], krotkie)
    assert w.audyt["router"]["proza"] is False and "numer_ted" not in w.audyt["router"]


def test_ted_z_routera_w_wyniku_pisma_prozy():
    w = _odwolanie(_potok(Atrapa()))
    assert w.dane["ZamowieniePubliczne"]["numer_ted"] == "012345-2026"


# ---------- czynność przez model ----------

def test_proza_czynnosc_i_dzien_z_modelu():
    a = Atrapa('{"kod": 2, "data": "3 marca 2026 r."}')
    w = _odwolanie(_potok(a))
    kio = w.dane["OdwolanieKIO"]
    assert a.router == 1
    assert (kio["czynnosc_powod_id"], kio["czynnosc_opis"], kio["czynnosc_dzien"]) == (2, "Ogłoszenie wyboru oferty", "2026-03-03")
    assert w.audyt["router"]["proza"] is True


def test_proza_kod_6_opis_ze_slownika_ze_slashem():
    kio = _odwolanie(_potok(Atrapa('{"kod": 6, "data": null}'))).dane["OdwolanieKIO"]
    assert (kio["czynnosc_powod_id"], kio["czynnosc_opis"]) == (6, "Odpowiedzi/wyjaśnienia do SWZ")


def test_proza_data_bez_roku_bierze_rok_pisma():
    strony = (STRONY_PROZY[0].replace("Zamawiający w dniu 3 marca 2026 r.", "Zamawiający w dniu 3 marca"),) + STRONY_PROZY[1:]
    kio = _odwolanie(_potok(Atrapa('{"kod": 2, "data": "3 marca"}')), strony).dane["OdwolanieKIO"]
    assert kio["czynnosc_dzien"] == "2026-03-03"


@pytest.mark.parametrize("odp", ['{"kod": 13, "data": "3 marca 2026 r."}', '{"kod": null, "data": null}', "BRAK", None])
def test_odpowiedz_spoza_listy_zostawia_regule(odp):
    baza = _odwolanie(_potok(Atrapa())).dane["OdwolanieKIO"]
    kio = _odwolanie(_potok(Atrapa(odp))).dane["OdwolanieKIO"]
    assert kio == baza


def test_data_spoza_tekstu_odrzucona():
    baza = _odwolanie(_potok(Atrapa())).dane["OdwolanieKIO"]
    kio = _odwolanie(_potok(Atrapa('{"kod": 2, "data": "7 lutego 2026 r."}'))).dane["OdwolanieKIO"]
    assert kio["czynnosc_powod_id"] == 2 and kio["czynnosc_dzien"] == baza["czynnosc_dzien"]


def test_tylko_puste_pola_gdy_nadpisywanie_wylaczone(monkeypatch):
    baza = _odwolanie(_potok(Atrapa())).dane["OdwolanieKIO"]
    assert baza["czynnosc_powod_id"] is not None   # reguła coś znalazła
    monkeypatch.setenv("ROUTER_NADPISUJ", "0")
    kio = _odwolanie(_potok(Atrapa('{"kod": 9, "data": null}'))).dane["OdwolanieKIO"]
    assert kio["czynnosc_powod_id"] == baza["czynnosc_powod_id"]


def test_uklad_uzp_bez_zapytan_routera():
    a = Atrapa('{"kod": 9, "data": null}')
    strony = ("Prezes Krajowej Izby Odwoławczej\nOdwołujący: Fikcja sp. z o.o.\nZamawiający: Gmina Przykładowo\n"
              "ODWOŁANIE\nDziałając w imieniu wykonawcy, w oparciu o załączone pełnomocnictwo, wnoszę o:\n"
              "Zamawiający w dniu 3 marca 2026 roku unieważnił postępowanie.\n" + WYPELNIACZ,) + STRONY_PROZY[1:]
    w = _odwolanie(_potok(a), strony)
    assert a.router == 0 and w.audyt["router"]["proza"] is False


def test_router_wylaczony_jak_baza(monkeypatch):
    monkeypatch.setenv("ROUTER_PROZY", "0")
    a = Atrapa('{"kod": 9, "data": null}')
    w = _odwolanie(_potok(a))
    assert a.router == 0 and "router" not in w.audyt


def test_przelacznik_w_konfiguracji(tmp_path, monkeypatch):
    monkeypatch.delenv("ROUTER_PROZY", raising=False)
    k = tmp_path / "aplikacja.yaml"
    k.write_text("router_prozy: false\n", encoding="utf-8")
    assert router.wlaczony(k) is False
    k.write_text("router_prozy: true\n", encoding="utf-8")
    assert router.wlaczony(k) is True
    monkeypatch.setenv("ROUTER_PROZY", "0")
    assert router.wlaczony(k) is False


# ---------- kontrola: data poza oknem czynności, start fragmentu w 3. osobie ----------

def _z_data_ogloszenia(zdanie):
    return (STRONY_PROZY[0].replace("przekazał wykonawcom", zdanie + " Następnie przekazał wykonawcom"),) + STRONY_PROZY[1:]


@pytest.mark.parametrize("data", ["2 stycznia 2026 r.", "20 marca 2026 r."])
def test_data_daleko_przed_pismem_albo_po_nim_odrzucona(data):
    strony = _z_data_ogloszenia(f"Ustawa z dnia 2 stycznia 2026 r. i termin do dnia 20 marca 2026 r. nie mają znaczenia.")
    baza = _odwolanie(_potok(Atrapa()), strony).dane["OdwolanieKIO"]
    kio = _odwolanie(_potok(Atrapa('{"kod": 2, "data": "%s"}' % data)), strony).dane["OdwolanieKIO"]
    assert kio["czynnosc_powod_id"] == 2 and kio["czynnosc_dzien"] == baza["czynnosc_dzien"]


def test_fragment_od_zarzutu_w_trzeciej_osobie_po_dlugim_naglowku():
    naglowek = ("Odwołujący: Fikcja Serwis sp. z o.o., ul. Zmyślona 1, 00-001 Warszawa, reprezentowana przez pełnomocnika. "
                "Zamawiający: Gmina Przykładowo, ul. Rynek 1. Wartość zamówienia przekracza progi unijne. ") * 30
    tekst = naglowek + "Odwołujący zarzuca Zamawiającemu zaniechanie odrzucenia oferty wykonawcy Inny Przykład S.A. " + WYPELNIACZ
    assert "zaniechanie odrzucenia" in router.fragment(tekst, SPEC["czynnosc"]["fragment"])
