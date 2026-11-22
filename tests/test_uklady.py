"""Ekstrakcja na układach spoza szablonu UZP (tekst syntetyczny, dane fikcyjne)."""
from pathlib import Path

from odwolania2json.potok import Potok

KORZEN = Path(__file__).resolve().parents[1]
POTOK = Potok(KORZEN / "config/klasy", uzyj_llm=False)

PELNOMOCNICTWO = """PEŁNOMOCNICTWO
Alfa Serwis sp. z o.o., ul. Długa 5, 00-001 Warszawa, wpisana do KRS pod nr 9991588139, NIP 999-986-98-77
niniejszym udziela pełnomocnictwa radcy prawnemu Jakubowi Zielińskiemu do reprezentowania przed Krajową Izbą Odwoławczą.
Za Alfa Serwis sp. z o.o.:
…………………………
Prezes Zarządu
Jan Nowak
…………………………
Członek Zarządu Anna Kowalska
"""


def test_pelnomocnictwo_funkcja_przed_nazwiskiem_i_celownik():
    w = POTOK.przetworz_tekst(PELNOMOCNICTWO)
    assert w.klasa == "pelnomocnictwo"
    m = w.dane["mocodawca"][0]
    assert m["data"]["nazwa"] == "Alfa Serwis sp. z o.o."
    assert m["data"]["krs"] == "9991588139" and m["data"]["nip"] == "9999869877"
    assert [p["imie_nazwisko"] for p in m["podpisujacy"]] == ["Jan Nowak", "Anna Kowalska"]
    assert w.dane["pelnomocnicy"][0]["imie_nazwisko"] == "Jakub Zieliński"


ODWOLANIE_BEZ_ETYKIET = """Kraków, 12 listopada 2026 r.
Do Prezesa Krajowej Izby Odwoławczej
Wnoszący odwołanie
Termex Instalacje sp. z o.o.
ul. Zabłocie 12, 30-701 Kraków
KRS 9991234565, NIP 9993456782, REGON 999123458
działający przez r. pr. Piotra Malinowskiego, e-mail: p.malinowski@kancelaria.example
Instytucja prowadząca postępowanie
Gmina Wieliczka Górna
Rynek Górny 1, 32-020 Wieliczka
NIP 9997654321, REGON 999765432
O D W O Ł A N I E
W imieniu wykonawcy Termex Instalacje sp. z o.o. wnoszę odwołanie od czynności Zamawiającego polegającej na:
1) odrzuceniu oferty Odwołującego, o czym poinformowano w dniu 7 listopada 2026 r.
Postępowanie pn. „Termomodernizacja szkoły podstawowej nr 2”, znak sprawy: ZP.271.15.2026.
"""


def test_odwolanie_inne_etykiety_stron():
    w = POTOK.przetworz_tekst(ODWOLANIE_BEZ_ETYKIET)
    assert w.klasa == "odwolanie"
    o, z = w.dane["Odwolujacy"][0], w.dane["Zamawiajacy"][0]
    assert (o["nazwa"], o["krs"], o["nip"], o["regon"]) == ("Termex Instalacje sp. z o.o.", "9991234565", "9993456782", "999123458")
    assert o["przez-pelnomocnika"] == 1 and o["pelnomocnik"]["imie_nazwisko"] == "Piotr Malinowski"
    assert (z["nazwa"], z["nip"], z["regon"]) == ("Gmina Wieliczka Górna", "9997654321", "999765432")


def test_tytul_przelewu_po_slowie_tytulem():
    t = ("Potwierdzenie wykonania przelewu\nData operacji 14.09.2026\nRachunek nadawcy PL45 9999 1884 4729 4055 7616 9871\n"
         "Rachunek odbiorcy PL65 9999 6897 6846 9788 0932 0819\nKwota 10 000,00 PLN\n"
         "Tytułem Wpis od odwołania IZP.271.33.2026\nIdentyfikator transakcji BS2609140001187\n")
    w = POTOK.przetworz_tekst(t)
    assert w.klasa == "przelew" and w.dane["przelew_bankowy"]["tytul"] == "Wpis od odwołania IZP.271.33.2026"


def test_scal_powtorzone_naglowki_sekcji():
    from odwolania2json.silnik import Kontekst, Silnik
    spec = {"sekcje": {"p": {"od": "(?m)^Za [^\\n]+$", "wiele": True, "scal_powtorzone": True}}, "wynik": {}}
    s = Silnik(spec)
    tekst = "Za Alfa sp. z o.o.\nJan Nowak\nZa Alfa sp. z o.o.\nAnna Kowalska\nZa Beta S.A.\nPiotr Lis"
    s._pelny = Kontekst(tekst, 0)
    bloki = s.sekcja("p", s._pelny)
    assert len(bloki) == 2 and "Anna Kowalska" in bloki[0].tekst and "Piotr Lis" in bloki[1].tekst


ODWOLANIE_SKAN = """Poznań, dnia 11 września 2026 roku
Prezes Krajowej Izby Odwoławczej
Odwołujący: Alfa Budownictwo sp. k.
ul. Długa 1, 00-001 Lublin
KRS: 9991022552, NIP: 999-295-65-50, REGON: 999913617
reprezentowany przez pełnomocnika:
radca prawny Anna Rybak
adres do korespondencji:
Kancelaria Radcy Prawnego Anna Rybak
ul. Polna 115, 40-175 Katowice
e-mail: a.rybak@kancelaria.example
Zamawiający: Muzeum Regionalne w Brzozowie
ul. Lipowa 107A/8
81-277 Brzozów
Dotyczy: postępowania pn. „Przebudowa drogi powiatowej”, nr referencyjny: DZP.260.99.2026
ODWOŁANIE
Działając w imieniu Odwołującego – Alfa Budownictwo sp. k. (dalej: „Odwołujący”), wnoszę odwołanie wobec:
WPŁYNĘŁO
dnia 21.08.2026 L.dz. 199
1. zaniechania odrzucenia oferty wykonawcy Beta S.A., o czym Odwołujący powiadomił w dniu 11/05/2026 r.;
2. określenia warunków udziału w postępowaniu.
"""


def test_odwolanie_uklad_skanow():
    w = POTOK.przetworz_tekst(ODWOLANIE_SKAN)
    o, z, k = w.dane["Odwolujacy"][0], w.dane["Zamawiajacy"][0], w.dane["OdwolanieKIO"]
    assert o["nazwa"] == "Alfa Budownictwo sp. k."
    assert o["pelnomocnik"]["nazwa"] == "Kancelaria Radcy Prawnego Anna Rybak"
    assert z["nazwa"] == "Muzeum Regionalne w Brzozowie" and z["nip"] is None
    assert (k["czynnosc_powod_id"], k["czynnosc_dzien"]) == (7, "2026-05-11")


PRZELEW_SKAN = """Bank Pomorski
Potwierdzenie transakcji
Opis
opłata skarbowa od pełnomocnictwa dla adwokat Sylwia Sikora
Kwota Data transakcji Numer referencyjny transakcji
34,00 PLN 20.05.2026 CEN7319670412925
Dane nadawcy
Nazwa i adres
NORDENIX AUTOMATYKA SP. Z O.O.
Numer rachunku
PL75 2170 0008 0889 2619 9999 9470
Dane odbiorcy
Nazwa i adres
Urząd Miasta Brzozowiec
Numer rachunku
61 1030 1508 1403 0456 9635 6736
"""


def test_wydruk_bankowy_tabela_i_dane_nadawcy():
    p = POTOK.przetworz_tekst(PRZELEW_SKAN)
    assert p.klasa == "przelew"
    b = p.dane["przelew_bankowy"]
    assert (b["kwota"], b["data_operacji"], b["numer_transakcji"]) == (34.0, "2026-05-20", "CEN7319670412925")
    assert b["z_rachunku"] == "PL75217000080889261999999470" and b["na_rachunek"] == "61103015081403045696356736"
    assert b["tytul"].startswith("opłata skarbowa od pełnomocnictwa")


PRZELEW_WARTOSC = """Bank Wielkopolski i Pomorza
Potwierdzenie transakcji
Opis
opłata skarbowa od pełnomocnictwa dla Cezary Marciniak w postępowaniu przed KIO w przetargu ZS.520.2026
CEN2608087095658
Wartość
100,00 zł
Data transakcji
25 lipca 2026
Numer transakcji
CEN2608087095658
Z rachunku: 96 6798 6857 5223 7021 2076 7677
Rachunek odbiorcy: 24 3499 1080 2892 9204 5720 5135
"""


def test_tytul_przelewu_konczy_sie_przed_etykieta_wartosc():
    w = POTOK.przetworz_tekst(PRZELEW_WARTOSC)
    assert w.klasa == "przelew"
    assert w.dane["przelew_bankowy"]["tytul"] == ("opłata skarbowa od pełnomocnictwa dla Cezary Marciniak w postępowaniu "
                                                 "przed KIO w przetargu ZS.520.2026 CEN2608087095658")
    w = POTOK.przetworz_tekst(PRZELEW_WARTOSC.replace("Wartość\n", "WARTOŚĆ ......... "))
    assert "WARTO" not in w.dane["przelew_bankowy"]["tytul"]


def test_przypisanie_podpisow_w_konsorcjum():
    from odwolania2json.przypisanie import przypisz
    tekst = ("Alfa sp. z o.o., KRS 9991234565, reprezentowana przez: Jan Nowak – Prezes Zarządu – Lider; "
             "Beta S.A., KRS 9997654321, reprezentowana przez: Anna Kowalska – Prezes Zarządu, udzielają pełnomocnictwa: …")
    dane = {"mocodawca": [{"data": {"nazwa": "Alfa sp. z o.o."}, "podpisujacy": [{"imie_nazwisko": "Anna Kowalska"},
                                                                                {"imie_nazwisko": "Jan Nowak"}]},
                          {"data": {"nazwa": "Beta S.A."}, "podpisujacy": [{"imie_nazwisko": None}]}]}
    spec = {"lista": "mocodawca", "pole_nazwy": "data.nazwa", "podlista": "podpisujacy", "pole": "imie_nazwisko",
            "do": "udziel\\w*\\s+pe[łl]nomocnictw"}
    w = przypisz(dane, tekst, spec)
    assert w["mocodawca"][0]["podpisujacy"] == [{"imie_nazwisko": "Jan Nowak"}]
    assert w["mocodawca"][1]["podpisujacy"] == [{"imie_nazwisko": "Anna Kowalska"}]
    jeden = {"mocodawca": [dane["mocodawca"][0]]}
    assert przypisz(jeden, tekst, spec) == jeden  # jeden mocodawca: bez zmian
