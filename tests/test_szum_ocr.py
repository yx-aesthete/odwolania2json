"""Odporność pól na zaszumiony odczyt OCR skanów (pisma kancelarii, wydruki bankowe).

Każdy test to jeden wzorzec szumu zmierzony na 129 wariantach prawdziwego OCR: tekst syntetyczny (dane fikcyjne)
z jednym zniekształceniem. Testy „strażnik” są zielone przed poprawkami i po nich (reguła nie może się rozszerzyć).
"""
import json
import os
from pathlib import Path

import pytest

from odwolania2json.potok import Potok

# O2J_APP: katalog innej kopii aplikacji (test mutacyjny: te same testy na wskazanej kopii; PYTHONPATH=<kopia>/src)
KORZEN = Path(os.environ.get("O2J_APP") or Path(__file__).resolve().parents[1])

ODWOLANIE = """Lubawa, dnia 14 maja 2031 roku
Prezes Krajowej Izby Odwoławczej
ul. Postępu 17A
02-676 Warszawa
Odwołujący: Borealis Instalacje sp. k.
ul. Modrzewiowa 7
11-222 Lubawa
KRS: 0000123456, NIP: 123-456-32-18, REGON: 123456785
reprezentowany przez pełnomocnika:
radca prawny Tomasz Wilczek
adres do korespondencji:
Kancelaria Radcy Prawnego Tomasz Wilczek
ul. Jesionowa 3, 11-222 Lubawa
tel. +48 55 000 00 01
e-mail: t.wilczek@wilczek-kancelaria.example
Zamawiający: Zakład Usług Komunalnych w Sosnowie Dolnym
ul. Lipowa 12
33-444 Sosnowo Dolne
e-mail: zamowienia@sosnowo-dolne.example
Dotyczy: postępowania o udzielenie zamówienia publicznego prowadzonego
w trybie przetargu nieograniczonego pn. „Remont sieci wodociągowej wraz z
wymianą przyłączy w miejscowości Sosnowo Dolne”, nr referencyjny: ZUK.271.4.2031,
ogłoszenie w Dzienniku Urzędowym Unii Europejskiej nr 2031/S
044-123456
Wpis od odwołania: 15 000 zł
O D W O Ł A N I E
od czynności i zaniechań Zamawiającego
Działając w imieniu Odwołującego – Borealis Instalacje sp. k. (dalej: „Odwołujący”), na podstawie
art. 505 ust. 1 w zw. z art. 513 pkt 1 i 2 ustawy z dnia 11 września 2019 r. – Prawo zamówień publicznych
(dalej: „Pzp”), wnoszę odwołanie wobec:
1. czynności Zamawiającego polegającej na odrzuceniu oferty Odwołującego, o której Odwołujący
został poinformowany w dniu 05.05.2031 r.;
2. zaniechania wezwania Odwołującego do złożenia wyjaśnień;
Zaskarżonym czynnościom zarzucam naruszenie:
1) art. 226 ust. 1 pkt 5 Pzp poprzez odrzucenie oferty zgodnej z warunkami zamówienia;
"""

PELNOMOCNICTWO = """Lubawa, dnia 10 maja 2031 roku
PEŁNOMOCNICTWO
Borealis Instalacje spółka akcyjna z siedzibą w Lubawa (11-222), ul. Modrzewiowa 7, wpisana do rejestru
przedsiębiorców Krajowego Rejestru Sądowego pod numerem KRS: 0000123456, NIP: 1234563218,
REGON: 123456785, reprezentowana przez: Marta Sowińska – Prezes Zarządu, Karol Bielik – Prokurent
(dalej: „Mocodawca”), niniejszym udziela pełnomocnictwa:
1. Tomasz Wilczek – radca prawny, nr wpisu OL-1234, PESEL: 80010112345,
2. Irena Dolna – adwokat, nr wpisu OL-777,
do reprezentowania Mocodawcy w sprawie dotyczącej środków ochrony prawnej w postępowaniu o
udzielenie zamówienia publicznego pn. „Remont sieci wodociągowej wraz z wymianą przyłączy”,
numer postępowania: ZUK.271.4.2031, w tym do wniesienia odwołania do Prezesa Krajowej Izby Odwoławczej.
Pełnomocnik jest upoważniony do udzielania dalszych pełnomocnictw substytucyjnych.
Za Mocodawcę:
Marta Sowińska – Prezes Zarządu
Borealis Instalacje spółka akcyjna
"""

PRZELEW = """Bank Testowy Spółka Akcyjna
Data wydruku: 2031-05-13 godz. 10:13
Potwierdzenie wykonania przelewu
Data operacji 2031-05-13
Rachunek nadawcy: 11 1111 1111 1111 1111 1111 1111
Nazwa nadawcy: BOREALIS INSTALACJE SP. K.
Rachunek odbiorcy: 22 2222 2222 2222 2222 2222 2222
Nazwa odbiorcy: Urząd Zamówień Publicznych
Tytuł: Wpis od odwołania, ZUK.271.4.2031, ZAKŁAD USŁUG KOMUNALNYCH
Kwota -15 000,00 PLN
Dokument jest wydrukiem komputerowym i nie wymaga dodatkowych podpisów oraz stempla bankowego.
"""


@pytest.fixture(scope="module")
def potok():
    return Potok(KORZEN / "config" / "klasy", uzyj_llm=False)


def _wynik(potok, tekst, klasa):
    w = potok.przetworz_tekst(tekst, (tekst,))
    assert w.klasa == klasa, w.audyt["klasyfikacja"]
    return w.dane


def _zamien(tekst, stare, nowe):
    assert stare in tekst, stare
    return tekst.replace(stare, nowe)


TYTUL = "Remont sieci wodociągowej wraz z wymianą przyłączy w miejscowości Sosnowo Dolne"


def test_teksty_bazowe_czytelne(potok):
    """Punkt odniesienia: teksty bez szumu dają komplet pól (żeby testy niżej mierzyły tylko szum)."""
    o = _wynik(potok, ODWOLANIE, "odwolanie")
    assert o["ZamowieniePubliczne"]["tytul"] == TYTUL
    assert o["Odwolujacy"][0]["nazwa"] == "Borealis Instalacje sp. k."
    assert o["Odwolujacy"][0]["pelnomocnik"]["imie_nazwisko"] == "Tomasz Wilczek"
    assert o["OdwolanieKIO"]["czynnosc_dzien"] == "2031-05-05"
    p = _wynik(potok, PELNOMOCNICTWO, "pelnomocnictwo")
    assert [x["imie_nazwisko"] for x in p["pelnomocnicy"]] == ["Tomasz Wilczek", "Irena Dolna"]
    assert [x["imie_nazwisko"] for x in p["mocodawca"][0]["podpisujacy"]] == ["Marta Sowińska", "Karol Bielik"]
    b = _wynik(potok, PRZELEW, "przelew")["przelew_bankowy"]
    assert b["kwota"] == 15000.0 and b["data_operacji"] == "2031-05-13"


# ---------- odwołanie ----------


@pytest.mark.parametrize("etykieta", [
    "reprezentowany przez petnomocnika:",    # ł -> t
    "reprezentowany przez. pełnomocnika:",   # zabłąkana kropka
    "Li  Ik  Now  Z  ł  m  ika:",            # linia zniszczona pieczęcią
])
def test_pelnomocnik_z_linii_tytulu_gdy_etykieta_nieczytelna(potok, etykieta):
    t = _zamien(ODWOLANIE, "reprezentowany przez pełnomocnika:", etykieta)
    assert _wynik(potok, t, "odwolanie")["Odwolujacy"][0]["pelnomocnik"]["imie_nazwisko"] == "Tomasz Wilczek"


@pytest.mark.parametrize("zepsute", ["sp. k. .(dalej:", "sp. k..(dalej:"])
def test_nazwa_odwolujacego_z_kropka_przed_nawiasem_dalej(potok, zepsute):
    t = _zamien(ODWOLANIE, "Odwołujący: Borealis Instalacje sp. k.\n", "Odwołujący:\n")   # nazwa tylko w zdaniu „w imieniu”
    t = _zamien(t, "sp. k. (dalej:", zepsute)
    assert _wynik(potok, t, "odwolanie")["Odwolujacy"][0]["nazwa"] == "Borealis Instalacje sp. k."


def test_nazwa_odwolujacego_gdy_slowo_odwolujacego_przekrecone(potok):
    t = _zamien(ODWOLANIE, "Odwołujący: Borealis Instalacje sp. k.\n", "Odwołujący:\n")
    t = _zamien(t, "w imieniu Odwołującego –", "w imieniu Odwotującego –")
    assert _wynik(potok, t, "odwolanie")["Odwolujacy"][0]["nazwa"] == "Borealis Instalacje sp. k."


@pytest.mark.parametrize("etykieta", ["Odwotujacy:", "„Odwołujący:", "Odwołuiacy:", ":  Odwolujący:"])
def test_blok_odwolujacego_gdy_etykieta_przekrecona(potok, etykieta):
    """Etykieta bloku z przekręconą literą albo z zabłąkanym znakiem na początku linii (dwukropek zostaje)."""
    t = _zamien(ODWOLANIE, "Odwołujący: Borealis", etykieta.rstrip("\n") + ("\n" if etykieta.endswith("\n") else " ") + "Borealis")
    o = _wynik(potok, t, "odwolanie")["Odwolujacy"][0]
    assert (o["krs"], o["nip"], o["regon"]) == ("0000123456", "1234563218", "123456785")


@pytest.mark.parametrize("etykieta", ["Zamawiaiacv:", "„Zamawiający:"])
def test_blok_zamawiajacego_gdy_etykieta_przekrecona(potok, etykieta):
    t = _zamien(ODWOLANIE, "Zamawiający: Zakład", etykieta + " Zakład")
    assert _wynik(potok, t, "odwolanie")["Zamawiajacy"][0]["nazwa"] == "Zakład Usług Komunalnych w Sosnowie Dolnym"


def test_blok_odwolujacego_konczy_sie_na_przekreconej_etykiecie_zamawiajacego(potok):
    """Etykieta „Zamawiający:” z przekręconymi literami kończy blok odwołującego: REGON zamawiającego nie trafia
    do odwołującego, który własnego REGON-u nie podał."""
    t = _zamien(ODWOLANIE, ", REGON: 123456785", "")
    t = _zamien(t, "Zamawiający: Zakład", "Zamawiaiacv: Zakład")
    t = _zamien(t, "33-444 Sosnowo Dolne\n", "33-444 Sosnowo Dolne\nREGON: 987654321\n")
    o = _wynik(potok, t, "odwolanie")
    assert o["Odwolujacy"][0]["regon"] is None
    assert o["Zamawiajacy"][0]["regon"] == "987654321"


def test_nazwa_kancelarii_bez_slowa_rodzajowego_gdy_etykieta_adresu_z_literowka(potok):
    """„adres do korespondencii:” (j -> i): nazwa pod etykietą nie ma słowa „kancelaria”, więc liczy się sama etykieta."""
    t = _zamien(ODWOLANIE, "adres do korespondencji:\nKancelaria Radcy Prawnego Tomasz Wilczek", "adres do korespondencii:\nBiuro Prawne Tomasz Wilczek")
    assert _wynik(potok, t, "odwolanie")["Odwolujacy"][0]["pelnomocnik"]["nazwa"] == "Biuro Prawne Tomasz Wilczek"


@pytest.mark.parametrize("etykieta", ["adres do korespondencii:", "dres do korespondencji", "a  d  r  e  s:"])
def test_kancelaria_gdy_etykieta_adresu_nieczytelna(potok, etykieta):
    t = _zamien(ODWOLANIE, "adres do korespondencji:", etykieta)
    assert _wynik(potok, t, "odwolanie")["Odwolujacy"][0]["pelnomocnik"]["nazwa"] == "Kancelaria Radcy Prawnego Tomasz Wilczek"


# ---------- pełnomocnictwo ----------


@pytest.mark.parametrize("stare, nowe", [
    ("1. Tomasz Wilczek – radca prawny", "1. Tomasz Wilczek * radca prawny"),  # myślnik jako gwiazdka
    ("1. Tomasz Wilczek – radca prawny", "I. Tomasz Wilczek – radca prawny"),  # numer pozycji jako litera
    ("1. Tomasz Wilczek – radca prawny", "1 . Tomasz Wilczek – radca prawny"),
])
def test_wyliczenie_pelnomocnikow_ze_zgubionym_myslnikiem_i_numerem(potok, stare, nowe):
    p = _wynik(potok, _zamien(PELNOMOCNICTWO, stare, nowe), "pelnomocnictwo")
    assert [x["imie_nazwisko"] for x in p["pelnomocnicy"]] == ["Tomasz Wilczek", "Irena Dolna"]


def test_pesel_po_kropce_zamiast_dwukropka(potok):
    p = _wynik(potok, _zamien(PELNOMOCNICTWO, "PESEL: 80010112345", "PESEL. 80010112345"), "pelnomocnictwo")
    assert p["pelnomocnicy"][0]["pesel"] == "80010112345"


@pytest.mark.parametrize("stare, nowe", [
    ("reprezentowana przez: Marta", "reprezentowana przcz: Marta"),              # przekręcone „przez”
    ("Karol Bielik – Prokurent", "Karol Bielik\nProkurent"),                      # myślnik zgubiony na końcu linii
    ("Marta Sowińska – Prezes Zarządu, Karol", "Marta Sowińska = Prezes Zarządu, Karol"),
])
def test_podpisujacy_z_klauzuli_reprezentacji_przy_szumie(potok, stare, nowe):
    t = _zamien(PELNOMOCNICTWO, "Za Mocodawcę:\nMarta Sowińska – Prezes Zarządu\n", "Za Mocodawcę:\n")
    p = _wynik(potok, _zamien(t, stare, nowe), "pelnomocnictwo")
    assert [x["imie_nazwisko"] for x in p["mocodawca"][0]["podpisujacy"]] == ["Marta Sowińska", "Karol Bielik"]


@pytest.mark.parametrize("stare, nowe, nazwa", [
    ("spółka akcyjna z siedzibą w Lubawa", "spółkaakcyjna z siedzibą w Lubawa", "Borealis Instalacje spółka akcyjna"),
    ("spółka akcyjna z siedzibą w Lubawa", "Sp. z 0.0. z siedzibą w Lubawa", "Borealis Instalacje Sp. z o.o."),
    ("spółka akcyjna z siedzibą w Lubawa", "Sp. z 0.o. z siedzibą w Lubawa", "Borealis Instalacje Sp. z o.o."),
])
def test_nazwa_mocodawcy_ze_sklejona_albo_przekrecona_forma_prawna(potok, stare, nowe, nazwa):
    p = _wynik(potok, _zamien(PELNOMOCNICTWO, stare, nowe), "pelnomocnictwo")
    assert p["mocodawca"][0]["data"]["nazwa"] == nazwa


def test_forma_prawna_nie_rusza_poprawnych_nazw():
    from odwolania2json.normalizacja import forma_prawna
    for n in ("Alfa Sp. z o.o.", "ALFA SP. Z O.O.", "Beta spółka akcyjna", "Gamma 0.0. Serwis", "Delta S.A.", "Zakład nr 10.0."):
        assert forma_prawna(n) == n
    assert forma_prawna("ALFA SP. Z 0.0.") == "ALFA SP. Z O.O."


# ---------- przelew ----------
@pytest.mark.parametrize("etykieta", ["Tytut:", "Tytut;"])
def test_tytul_przelewu_gdy_etykieta_przekrecona(potok, etykieta):
    b = _wynik(potok, _zamien(PRZELEW, "Tytuł:", etykieta), "przelew")["przelew_bankowy"]
    assert b["tytul"] == "Wpis od odwołania, ZUK.271.4.2031, ZAKŁAD USŁUG KOMUNALNYCH"


def test_kwota_z_kropka_dziesietna_w_wierszu_tabeli(potok):
    """Wydruk tabelaryczny: kwota bez etykiety w linii, przecinek dziesiętny odczytany jako kropka."""
    t = _zamien(PRZELEW, "Kwota -15 000,00 PLN\n", "")
    t = _zamien(t, "Data operacji 2031-05-13\n", "Data operacji PRZELEW ELIXIR -15 000.00 PLN\n2031-05-13 szczegóły\n")
    assert _wynik(potok, t, "przelew")["przelew_bankowy"]["kwota"] == 15000.0


# ---------- strażnicy: reguły szumu nie łapią poprawnych pism ----------
def test_straznik_wyliczenie_stron_przed_naglowkiem_nie_otwiera_bloku(potok):
    """„- Odwołujący – wykonawca” w piśmie przewodnim nad nagłówkiem to nie etykieta bloku (brak dwukropka)."""
    t = "W załączeniu odwołanie. Strony postępowania:\n- Odwołujący – wykonawca,\n- Zamawiający – zakład komunalny.\n" + ODWOLANIE
    o = _wynik(potok, t, "odwolanie")
    assert (o["Odwolujacy"][0]["krs"], o["Odwolujacy"][0]["nip"]) == ("0000123456", "1234563218")
    assert o["Zamawiajacy"][0]["nazwa"] == "Zakład Usług Komunalnych w Sosnowie Dolnym"


def test_straznik_etykieta_w_dopelniaczu_nie_otwiera_bloku_zamawiajacego(potok):
    """Linia „Zamawiającego: …” w bloku odwołującego to zwykłe zdanie, nie przekręcona etykieta „Zamawiający:”."""
    t = _zamien(ODWOLANIE, "tel. +48 55 000 00 01\n", "tel. +48 55 000 00 01\nZamawiającego: proszę zawiadomić przez ePUAP\n")
    assert _wynik(potok, t, "odwolanie")["Zamawiajacy"][0]["nazwa"] == "Zakład Usług Komunalnych w Sosnowie Dolnym"


def test_straznik_kancelaria_po_przecinkach_przed_linia_ze_slowem_wspolnicy(potok):
    """Kancelaria i adres w jednej linii po przecinkach wygrywają z późniejszą linią „Wspólnicy …” nad adresem."""
    t = _zamien(ODWOLANIE, "adres do korespondencji:\nKancelaria Radcy Prawnego Tomasz Wilczek\nul. Jesionowa 3, 11-222 Lubawa\n",
                "Kancelaria Radcy Prawnego Tomasz Wilczek, ul. Jesionowa 3, 11-222 Lubawa\nWspólnicy odpowiadający bez ograniczeń\nul. Inna 7, 00-001 Warszawa\n")
    assert _wynik(potok, t, "odwolanie")["Odwolujacy"][0]["pelnomocnik"]["nazwa"] == "Kancelaria Radcy Prawnego Tomasz Wilczek"


def test_straznik_tytul_zawodowy_po_dwoch_wyrazach_to_nie_pelnomocnik(potok):
    """W wyliczeniu pełnomocników dwa wyrazy z wielkiej litery, po których stoi tytuł zawodowy bez separatora
    („Krajowa Izba Radców Prawnych” na początku linii), nie są kolejnym pełnomocnikiem."""
    t = _zamien(PELNOMOCNICTWO, "1. Tomasz Wilczek – radca prawny, nr wpisu OL-1234, PESEL: 80010112345,\n",
                "1. Tomasz Wilczek – radca prawny, nr wpisu OL-1234, PESEL: 80010112345, lista prowadzona przez\nKrajowa Izba Radców Prawnych,\n")
    p = _wynik(potok, t, "pelnomocnictwo")
    assert [x["imie_nazwisko"] for x in p["pelnomocnicy"]] == ["Tomasz Wilczek", "Irena Dolna"]
