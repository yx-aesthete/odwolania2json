"""Odwołanie w układzie pisma kancelarii (papier firmowy, blok „Odwołujący: / Zamawiający: / Dotyczy:”, lista
„wnoszę odwołanie wobec: 1. …”, zdanie o zachowaniu terminu, podpis pełnomocnika) — warianty, których nie było
w sprawach strojeniowych. Tekst syntetyczny, wszystkie dane fikcyjne."""
from pathlib import Path

import pytest

from odwolania2json.normalizacja import bez_tytulu_zawodowego
from odwolania2json.potok import Potok

KORZEN = Path(__file__).resolve().parents[1]
POTOK = Potok(KORZEN / "config/klasy", uzyj_llm=False)

PAPIER = "Kancelaria Radcy Prawnego Jan Testowy\n"
DATA = "Testowo, dnia 12 maja 2026 roku\n"
ADRESAT = "Prezes Krajowej Izby Odwoławczej\nul. Postępu 17A\n02-676 Warszawa\n"
ODWOLUJACY = ("Odwołujący: Alfa Budowa sp. z o.o.\nul. Zmyślona 1\n00-950 Testowo\n"
              "KRS: 9990001112, NIP: 999-111-22-33, REGON: 999111222\n")
PELNOMOCNIK = ("reprezentowany przez pełnomocnika:\nradca prawny Jan Testowy\nadres do korespondencji:\n"
               "Kancelaria Radcy Prawnego Jan Testowy\nul. Fikcyjna 2, 00-951 Testowo\ntel. +48 00 000 00 00\n"
               "e-mail: j.testowy@testowy-kancelaria.example\n")
ZAMAWIAJACY = ("Zamawiający: Gmina Przykładowo\nul. Urzędowa 3\n00-952 Przykładowo\nNIP: 9992223344\n"
               "e-mail: zamowienia@przykladowo.example\n")
DOTYCZY = ("Dotyczy: postępowania o udzielenie zamówienia publicznego prowadzonego w trybie przetargu\n"
           "nieograniczonego pn. „Budowa drogi gminnej w Przykładowie”, nr referencyjny: ZP.271.5.2026,\n"
           "ogłoszenie o zamówieniu nr 2026/BZP 00123456/01 opublikowane w Biuletynie Zamówień Publicznych\n")
TYTUL = "Wpis od odwołania: 10 000 zł\nO D W O Ł A N I E\nod czynności i zaniechań Zamawiającego\n"
WSTEP = ("Działając w imieniu Odwołującego – Alfa Budowa sp. z o.o. (dalej: „Odwołujący”), na podstawie art. 505 ust. 1\n"
         "w zw. z art. 513 pkt 1 i 2 ustawy z dnia 11 września 2019 r. – Prawo zamówień publicznych (dalej: „Pzp”),\n"
         "wnoszę odwołanie wobec:\n")
PUNKT1 = "czynności odrzucenia oferty Odwołującego, o której Zamawiający poinformował w dniu 4 maja 2026 r."
ZARZUTY = ("Zaskarżonym czynnościom i zaniechaniom Zamawiającego zarzucam naruszenie:\n"
           "1) art. 16 pkt 1 Pzp poprzez prowadzenie postępowania w sposób nie zapewniający uczciwej konkurencji;\n"
           "Wobec powyższego wnoszę o:\n1) uwzględnienie odwołania w całości;\n")
TERMIN = ("Zachowanie terminu i wymogów formalnych\n"
          "Informacja o zaskarżonej czynności została przekazana Odwołującemu w dniu 04.05.2026 r. Odwołanie zostało\n"
          "zatem wniesione z zachowaniem terminu określonego w art. 515 Pzp.\n")
OGON = ("U Z A S A D N I E N I E\nOdwołujący posiada interes we wniesieniu odwołania.\n"
        "Mając na uwadze powyższe, wnoszę jak na wstępie.\nradca prawny Jan Testowy – pełnomocnik Odwołującego\n")


def pismo(*, papier=PAPIER, data=DATA, odwolujacy=ODWOLUJACY, pelnomocnik=PELNOMOCNIK, zamawiajacy=ZAMAWIAJACY,
          dotyczy=DOTYCZY, wstep=WSTEP, punkt1=PUNKT1, miedzy="", termin=TERMIN, ogon=OGON,
          punkt2="2. określenia warunków udziału w postępowaniu w sposób nieproporcjonalny;\n") -> str:
    return (papier + data + ADRESAT + odwolujacy + pelnomocnik + zamawiajacy + dotyczy + TYTUL + wstep + miedzy
            + f"1. {punkt1};\n" + punkt2 + ZARZUTY + termin + ogon)


def wynik(tekst: str) -> dict:
    strony = tuple(tekst.split("\f"))
    w = POTOK.przetworz_tekst("\n".join(strony), strony)
    assert w.klasa == "odwolanie"
    return w.dane


def test_pismo_bazowe():
    d = wynik(pismo())
    o, z, zp = d["Odwolujacy"][0], d["Zamawiajacy"][0], d["ZamowieniePubliczne"]
    assert d["OdwolanieKIO"] == {"data": "2026-05-12", "czynnosc_dzien": "2026-05-04", "czynnosc_powod_id": 1,
                                 "czynnosc_opis": "Decyzja o odrzuceniu oferty", "miejscowosc": "Testowo"}
    assert (o["nazwa"], o["krs"], o["nip"], o["regon"], o["przez-pelnomocnika"]) == ("Alfa Budowa sp. z o.o.", "9990001112", "9991112233", "999111222", 1)
    assert o["pelnomocnik"] == {"imie_nazwisko": "Jan Testowy", "nazwa": "Kancelaria Radcy Prawnego Jan Testowy",
                                "mail": "j.testowy@testowy-kancelaria.example"}
    assert (z["nazwa"], z["nip"], z["prowadzacy_postepowanie"]) == ("Gmina Przykładowo", "9992223344", None)
    assert zp == {"numer_bzp": "2026/BZP00123456/01", "numer_postepowania": "ZP.271.5.2026", "numer_ted": None,
                  "tytul": "Budowa drogi gminnej w Przykładowie"}


# ---------- powód czynności: sformułowania rzeczownikowe po „wobec:” ----------
SFORMULOWANIA = [
    (1, "odrzucenia przez Zamawiającego oferty Odwołującego, o czym Odwołujący został zawiadomiony w dniu 4 maja 2026 r."),
    (4, "treści Specyfikacji Warunków Zamówienia (SWZ) zamieszczonej przez Zamawiającego na stronie postępowania w dniu 4 maja 2026 r."),
    (4, "warunków zamówienia określonych w Specyfikacji Warunków Zamówienia (SWZ) udostępnionej w dniu 4 maja 2026 r."),
    (4, "treści SWZ udostępnionej na stronie internetowej prowadzonego postępowania w dniu 4 maja 2026 r."),
    (5, "zmiany postanowień SWZ dokonanej przez Zamawiającego w dniu 4 maja 2026 r."),
    (5, "zmienionej treści SWZ opublikowanej przez Zamawiającego w dniu 4 maja 2026 r."),
    (6, "odpowiedzi i wyjaśnień do treści Specyfikacji Warunków Zamówienia (SWZ) udzielonych przez Zamawiającego w dniu 4 maja 2026 r."),
    (6, "odpowiedzi Zamawiającego na pytania wykonawców do treści SWZ, opublikowanych w dniu 4 maja 2026 r."),
    (6, "wyjaśnień do SWZ opublikowanych przez Zamawiającego w dniu 4 maja 2026 r."),
    (6, "odpowiedzi oraz wyjaśnień Zamawiającego do SWZ z dnia 4 maja 2026 r."),
    (6, "treści wyjaśnień SWZ, opublikowanych w dniu 4 maja 2026 r."),
    (7, "zaniechania przez Zamawiającego odrzucenia oferty wykonawcy Beta Serwis S.A., o czym Odwołujący powziął wiadomość w dniu 4 maja 2026 r."),
    (7, "zaniechania czynności odrzucenia oferty wykonawcy Beta Serwis S.A., o czym Odwołujący powziął wiadomość w dniu 4 maja 2026 r."),
    (7, "braku odrzucenia oferty wykonawcy Beta Serwis S.A., o czym Odwołujący powziął wiadomość w dniu 4 maja 2026 r."),
    (8, "zaniechania przez Zamawiającego wykluczenia wykonawcy Beta Serwis S.A. z postępowania, o czym Odwołujący powziął wiadomość w dniu 4 maja 2026 r."),
    (8, "zaniechania dokonania czynności wykluczenia wykonawcy Beta Serwis S.A., o czym Odwołujący powziął wiadomość w dniu 4 maja 2026 r."),
    (9, "unieważnienia przez Zamawiającego postępowania o udzielenie zamówienia, o czym poinformowano wykonawców w dniu 4 maja 2026 r."),
    (10, "zaniechania przez Zamawiającego unieważnienia postępowania, o czym Odwołujący powziął wiadomość w dniu 4 maja 2026 r."),
    (10, "braku unieważnienia postępowania obarczonego wadą, o czym Odwołujący powziął wiadomość w dniu 4 maja 2026 r."),
    (12, "projektu umowy stanowiącego załącznik nr 5 do SWZ, opublikowanego w dniu 4 maja 2026 r."),
]


@pytest.mark.parametrize("kod,punkt", SFORMULOWANIA)
def test_powod_sformulowania_po_wobec(kod, punkt):
    assert wynik(pismo(punkt1=punkt))["OdwolanieKIO"]["czynnosc_powod_id"] == kod


@pytest.mark.parametrize("kod,punkt", [
    (1, "czynności Zamawiającego polegającej na uznaniu, że oferta Odwołującego podlega odrzuceniu, o czym poinformowano w dniu 4 maja 2026 r."),
    (5, "zmiany treści dokumentów zamówienia dokonanej w dniu 4 maja 2026 r."),
    (2, "rozstrzygnięcia postępowania na korzyść wykonawcy Beta Serwis S.A., którego ofertę wybrano w dniu 4 maja 2026 r."),
])
def test_powod_zapas_rdzenie(kod, punkt):
    """Punkt 1 spoza słownika głównego: rozstrzyga rdzeń słowa (powód jest w referencji zawsze)."""
    o = wynik(pismo(punkt1=punkt))["OdwolanieKIO"]
    assert o["czynnosc_powod_id"] == kod and o["czynnosc_opis"]


@pytest.mark.parametrize("kod,punkt", [
    (5, "treści SWZ zmodyfikowanej przez Zamawiającego w dniu 4 maja 2026 r."),
    (11, "treści SWZ w zakresie opisu przedmiotu zamówienia, opublikowanej w dniu 4 maja 2026 r."),
    (12, "treści SWZ w zakresie projektowanych postanowień umowy, opublikowanej w dniu 4 maja 2026 r."),
])
def test_tresc_swz_nie_przeslania_wlasciwej_czynnosci(kod, punkt):
    """Samo „treści SWZ” nie jest wzorcem kodu 4 w słowniku głównym: wygrywa czynność nazwana dalej w punkcie."""
    assert wynik(pismo(punkt1=punkt))["OdwolanieKIO"]["czynnosc_powod_id"] == kod


def test_rdzen_w_punkcie_1_przed_dalszymi_punktami_listy():
    """Punkt 1 spoza słownika głównego, punkt 2 (inna czynność) w słowniku: rozstrzyga rdzeń słowa z punktu 1."""
    o = wynik(pismo(punkt1="czynności Zamawiającego polegającej na uznaniu, że oferta Odwołującego podlega odrzuceniu",
                    punkt2="2. dokonania oceny ofert w sposób sprzeczny z kryteriami określonymi w SWZ;\n"))["OdwolanieKIO"]
    assert (o["czynnosc_powod_id"], o["czynnosc_opis"]) == (1, "Decyzja o odrzuceniu oferty")


def test_powod_w_drugim_punkcie_listy():
    d = wynik(pismo(punkt1="zaniechania wezwania Odwołującego do uzupełnienia podmiotowych środków dowodowych",
                    punkt2="2. zaniechania odrzucenia oferty wykonawcy Beta Serwis S.A.;\n"))
    assert d["OdwolanieKIO"]["czynnosc_powod_id"] == 7


# ---------- dzień czynności ----------
STOPKA = ("Kancelaria Testowa Fikcyjny i Wspólnicy sp. k. | ul. Zmyślona 12/4, 00-950 Testowo | tel. +48 00 000 00 00\n"
          "KRS: 9990009998 | NIP: 999-000-11-22 | REGON: 999000111 | Sąd Rejonowy w Testowie, XII Wydział Gospodarczy KRS\n"
          "www.fikcyjny-kancelaria.example | sekretariat@fikcyjny-kancelaria.example | rachunek: 00 0000 0000 0000 0000\n1\n")


def test_koniec_strony_miedzy_wobec_a_punktem_1():
    """Stopka kancelarii, numer strony i nagłówek bieżący stoją między „wobec:” a punktem 1 (ponad 400 znaków)."""
    t = pismo(miedzy=STOPKA + "\fFikcyjny, Zmyślony i Partnerzy Kancelaria Radców Prawnych i Adwokatów sp. p.\n", termin="")
    o = wynik(t)["OdwolanieKIO"]
    assert (o["czynnosc_dzien"], o["czynnosc_powod_id"]) == ("2026-05-04", 1)


def test_dzien_czynnosci_ze_zdania_o_terminie_mimo_pieczeci_wplywu():
    """Resztka pieczęci wpływu (sama linia z datą, bez słowa WPŁYNĘŁO) przed punktem 1 nie jest dniem czynności."""
    o = wynik(pismo(miedzy="dnia 21.08.2026 L.dz. 199\n"))["OdwolanieKIO"]
    assert o["czynnosc_dzien"] == "2026-05-04"


def test_dzien_czynnosci_zapis_nietypowy_w_punkcie():
    o = wynik(pismo(punkt1="czynności odrzucenia oferty Odwołującego, o której Zamawiający poinformował w dniu 4 V 2026 r."))
    assert o["OdwolanieKIO"]["czynnosc_dzien"] == "2026-05-04"


# ---------- konsorcjum: dane lidera, nie partnera ----------
KONSORCJUM = ("Odwołujący: Konsorcjum wykonawców:\n1) Alfa Budowa sp. z o.o. (Lider Konsorcjum)\n"
              "ul. Zmyślona 1, 00-950 Testowo\nKRS: 9990001112\nNIP: 9991112233\n"
              "2) Gamma Instalacje S.A. (Partner Konsorcjum)\nul. Wymyślona 7, 00-953 Testowo\n"
              "KRS: 9990003334, NIP: 9994445566, REGON: 999777888\n")


def test_konsorcjum_identyfikatory_tylko_lidera():
    o = wynik(pismo(odwolujacy=KONSORCJUM))["Odwolujacy"]
    assert len(o) == 1
    assert (o[0]["nazwa"], o[0]["krs"], o[0]["nip"], o[0]["regon"]) == ("Alfa Budowa sp. z o.o.", "9990001112", "9991112233", None)
    assert o[0]["przez-pelnomocnika"] == 1
    assert o[0]["pelnomocnik"] == {"imie_nazwisko": "Jan Testowy", "nazwa": "Kancelaria Radcy Prawnego Jan Testowy",
                                   "mail": "j.testowy@testowy-kancelaria.example"}


def test_konsorcjum_lider_na_drugiej_pozycji_i_inne_zdanie_wstepne():
    blok = ("Odwołujący: Konsorcjum wykonawców:\n1) Gamma Instalacje S.A. (Partner Konsorcjum)\nul. Wymyślona 7, 00-953 Testowo\n"
            "KRS: 9990003334, NIP: 9994445566, REGON: 999777888\n2) Alfa Budowa sp. z o.o. (Lider Konsorcjum)\n"
            "ul. Zmyślona 1, 00-950 Testowo\nNIP: 9991112233\n")
    wstep = WSTEP.replace("Działając w imieniu Odwołującego – Alfa Budowa sp. z o.o. (dalej: „Odwołujący”)", "Działając w imieniu i na rzecz Odwołującego")
    o = wynik(pismo(odwolujacy=blok, wstep=wstep))["Odwolujacy"][0]
    assert (o["nazwa"], o["krs"], o["nip"], o["regon"]) == ("Alfa Budowa sp. z o.o.", None, "9991112233", None)
    assert o["pelnomocnik"]["imie_nazwisko"] == "Jan Testowy" and o["pelnomocnik"]["mail"] == "j.testowy@testowy-kancelaria.example"


def test_konsorcjum_etykieta_lidera_bez_danych_partnera():
    blok = ("Odwołujący: Wykonawcy wspólnie ubiegający się o udzielenie zamówienia (konsorcjum):\n"
            "1) Lider konsorcjum: Alfa Budowa sp. z o.o.\nul. Zmyślona 1, 00-950 Testowo\nKRS: 9990001112\n"
            "2) Partner konsorcjum: Gamma Instalacje S.A.\nul. Wymyślona 7, 00-953 Testowo\nKRS: 9990003334, NIP: 9994445566\n")
    o = wynik(pismo(odwolujacy=blok))["Odwolujacy"][0]
    assert (o["krs"], o["nip"], o["pelnomocnik"]["imie_nazwisko"]) == ("9990001112", None, "Jan Testowy")


# ---------- pełnomocnik bez czytelnych etykiet ----------
def test_pelnomocnik_bez_etykiety_reprezentacji():
    """Etykieta „reprezentowany przez pełnomocnika:” nieczytelna (skan): pełnomocnik to linia z tytułem zawodowym."""
    o = wynik(pismo(pelnomocnik=PELNOMOCNIK.replace("reprezentowany przez pełnomocnika:", "reprezentow z peł ika:")
                    .replace("adres do korespondencji:\n", "")))["Odwolujacy"][0]
    assert o["przez-pelnomocnika"] == 1
    assert o["pelnomocnik"] == {"imie_nazwisko": "Jan Testowy", "nazwa": "Kancelaria Radcy Prawnego Jan Testowy",
                                "mail": "j.testowy@testowy-kancelaria.example"}


def test_pelnomocnik_z_podpisu_gdy_w_bloku_brak_tytulu():
    blok = "przez:\nJan Testowy, Kancelaria Radcy Prawnego Jan Testowy, ul. Fikcyjna 2, 00-951 Testowo\n"
    o = wynik(pismo(pelnomocnik=blok))["Odwolujacy"][0]
    assert o["pelnomocnik"]["imie_nazwisko"] == "Jan Testowy"


def test_sam_skrot_tytulu_to_pelnomocnik():
    blok = PELNOMOCNIK.replace("reprezentowany przez pełnomocnika:\nradca prawny Jan Testowy", "adw. Jan Testowy")
    o = wynik(pismo(papier="", pelnomocnik=blok, ogon="U Z A S A D N I E N I E\nOdwołujący posiada interes.\n"))["Odwolujacy"][0]
    assert (o["przez-pelnomocnika"], o["pelnomocnik"]["imie_nazwisko"]) == (1, "Jan Testowy")


def test_kancelaria_pod_inna_etykieta_adresu():
    o = wynik(pismo(pelnomocnik=PELNOMOCNIK.replace("adres do korespondencji:", "adres korespondencyjny:")))["Odwolujacy"][0]
    assert o["pelnomocnik"]["nazwa"] == "Kancelaria Radcy Prawnego Jan Testowy"


@pytest.mark.parametrize("napis", ["adw. dr hab. Marek Dąbek", "aplikant radcowski Marek Dąbek", "mecenas Marek Dąbek",
                                   "prof. dr hab. Marek Dąbek", "LL.M. adw. Marek Dąbek"])
def test_tytuly_przed_nazwiskiem(napis):
    assert bez_tytulu_zawodowego(napis) == "Marek Dąbek"


# ---------- zamówienie ----------
def test_tytul_z_cudzyslowem_w_srodku():
    dot = DOTYCZY.replace("„Budowa drogi gminnej w Przykładowie”", "„Dostawa systemu „Alfa” wraz z wdrożeniem w jednostkach Zamawiającego”")
    assert wynik(pismo(dotyczy=dot))["ZamowieniePubliczne"]["tytul"] == "Dostawa systemu „Alfa” wraz z wdrożeniem w jednostkach Zamawiającego"


@pytest.mark.parametrize("ogloszenie,ted", [("ogłoszenie nr 2026/S 123-456789", "456789-2026"), ("ogłoszenie nr 456789-2026", "456789-2026")])
def test_ted_bez_nazwy_dziennika(ogloszenie, ted):
    dot = DOTYCZY.replace("ogłoszenie o zamówieniu nr 2026/BZP 00123456/01 opublikowane w Biuletynie Zamówień Publicznych", ogloszenie)
    zp = wynik(pismo(dotyczy=dot))["ZamowieniePubliczne"]
    assert (zp["numer_ted"], zp["numer_bzp"]) == (ted, None)


@pytest.mark.parametrize("etykieta", ["nr ref.: ZP.271.5.2026", "numer sprawy: ZP.271.5.2026", "sygnatura postępowania: ZP.271.5.2026",
                                      "numer referencyjny nadany przez Zamawiającego: ZP.271.5.2026"])
def test_numer_postepowania_inne_etykiety(etykieta):
    dot = DOTYCZY.replace("nr referencyjny: ZP.271.5.2026", etykieta)
    assert wynik(pismo(dotyczy=dot))["ZamowieniePubliczne"]["numer_postepowania"] == "ZP.271.5.2026"


# ---------- nagłówek i zdanie wstępne ----------
def test_data_ze_skrotem_dn():
    o = wynik(pismo(data="Nowe Testowo, dn. 12.05.2026 r.\n"))["OdwolanieKIO"]
    assert (o["data"], o["miejscowosc"]) == ("2026-05-12", "Nowe Testowo")


def test_nazwa_odwolujacego_przed_zwanego_dalej():
    wstep = WSTEP.replace("(dalej: „Odwołujący”)", "(zwanego dalej „Odwołującym”)")
    assert wynik(pismo(wstep=wstep))["Odwolujacy"][0]["nazwa"] == "Alfa Budowa sp. z o.o."


# ---------- etykiety stron nieczytelne albo inne ----------
def test_etykiety_stron_z_bledem_odczytu_skanu():
    """„Odwotujacy:”, „Zamawiaiacy:” (ł->t, j->i, ą->a w odczycie skanu), także z cudzysłowem przed etykietą."""
    t = pismo(odwolujacy=ODWOLUJACY.replace("Odwołujący: ", "„Odwotujacy:\n"), zamawiajacy=ZAMAWIAJACY.replace("Zamawiający: ", "Zamawiaiacy:\n"))
    d = wynik(t)
    o, z = d["Odwolujacy"][0], d["Zamawiajacy"][0]
    assert (o["krs"], o["nip"], o["regon"]) == ("9990001112", "9991112233", "999111222")
    assert o["pelnomocnik"]["imie_nazwisko"] == "Jan Testowy"
    assert (z["nazwa"], z["nip"]) == ("Gmina Przykładowo", "9992223344")


def test_blok_odwolujacego_pod_inna_etykieta():
    """Bez słowa „Odwołujący” w etykiecie: blok pod adresem Izby, do etykiety zamawiającego."""
    o = wynik(pismo(odwolujacy=ODWOLUJACY.replace("Odwołujący: ", "Skarżący:\n")))["Odwolujacy"][0]
    assert (o["nazwa"], o["krs"], o["nip"], o["regon"]) == ("Alfa Budowa sp. z o.o.", "9990001112", "9991112233", "999111222")
    assert o["pelnomocnik"] == {"imie_nazwisko": "Jan Testowy", "nazwa": "Kancelaria Radcy Prawnego Jan Testowy",
                                "mail": "j.testowy@testowy-kancelaria.example"}


# ---------- ślady formatowania w odczycie skanu modelem ----------
def test_odczyt_skanu_bez_kursywy_markdown():
    from odwolania2json.llm import bez_markdown
    t = ("*reprezentowany przez pełnomocnika:*\nradca prawny Jan Testowy\n_adres do korespondencji:_\n__Zamawiający:__ Gmina Przykładowo\n"
         "pn. *„Budowa drogi gminnej w Przykładowie”*, nr referencyjny: **ZP.271.5.2026**\n* punkt listy\ne-mail: j_testowy@testowy_kancelaria.example\n"
         "______________\n2 * 3 * 4")
    assert bez_markdown(t) == ("reprezentowany przez pełnomocnika:\nradca prawny Jan Testowy\nadres do korespondencji:\nZamawiający: Gmina Przykładowo\n"
                               "pn. „Budowa drogi gminnej w Przykładowie”, nr referencyjny: ZP.271.5.2026\n* punkt listy\ne-mail: j_testowy@testowy_kancelaria.example\n"
                               "______________\n2 * 3 * 4")


def test_pelnomocnik_mimo_kursywy_przy_etykiecie():
    """Gwiazdki kursywy zostały w tekście (odczyt spoza ścieżki OCR aplikacji): nazwisko z linii z tytułem zawodowym."""
    blok = PELNOMOCNIK.replace("reprezentowany przez pełnomocnika:", "*reprezentowany przez pełnomocnika:*").replace("adres do korespondencji:", "*adres do korespondencji:*")
    o = wynik(pismo(pelnomocnik=blok))["Odwolujacy"][0]
    assert o["pelnomocnik"]["imie_nazwisko"] == "Jan Testowy" and o["pelnomocnik"]["mail"] == "j.testowy@testowy-kancelaria.example"


# ---------- numeracja pozycji na liście członków konsorcjum ----------
def test_konsorcjum_pozycje_z_literami():
    blok = KONSORCJUM.replace("1) ", "a) ").replace("2) ", "b) ")
    o = wynik(pismo(odwolujacy=blok))["Odwolujacy"][0]
    assert (o["nazwa"], o["krs"], o["nip"], o["regon"]) == ("Alfa Budowa sp. z o.o.", "9990001112", "9991112233", None)


def test_bez_pelnomocnika_podpis_elektroniczny_zarzadu_nie_jest_pelnomocnikiem():
    # pismo wnoszone przez zarząd: osoba z podpisu elektronicznego nie jest pełnomocnikiem (referencja ma null)
    wstep = WSTEP.replace("Działając w imieniu Odwołującego – Alfa Budowa sp. z o.o. (dalej: „Odwołujący”)",
                          "Alfa Budowa sp. z o.o. (dalej: „Odwołujący”), działając")
    ogon = OGON.replace("radca prawny Jan Testowy – pełnomocnik Odwołującego\n", "")
    for blok in ("reprezentowany przez Prezesa Zarządu Adama Fikcyjnego\ne-mail: biuro@alfa-budowa.example\n",
                 "e-mail: biuro@alfa-budowa.example\n"):
        o = wynik(pismo(papier="", pelnomocnik=blok, wstep=wstep,
                        ogon=ogon + "Prezes Zarządu\nDokument podpisany przez Adam Fikcyjny\nData: 2026.05.12\n"))["Odwolujacy"][0]
        assert o["przez-pelnomocnika"] == 0
        assert o["pelnomocnik"] == {"imie_nazwisko": None, "nazwa": None, "mail": None}


def test_bez_pelnomocnika_kancelaria_tylko_w_tytule_zamowienia():
    # wykonawca bez pełnomocnika; słowa „kancelarię prawną” stoją tylko w tytule zamówienia (nagłówek pisma)
    dot = DOTYCZY.replace("Budowa drogi gminnej w Przykładowie", "Obsługa prawna urzędu przez kancelarię prawną")
    wstep = WSTEP.replace("Działając w imieniu Odwołującego – Alfa Budowa sp. z o.o. (dalej: „Odwołujący”)",
                          "Alfa Budowa sp. z o.o. (dalej: „Odwołujący”), działając")
    ogon = OGON.replace("radca prawny Jan Testowy – pełnomocnik Odwołującego\n", "Adam Fikcyjny – Prezes Zarządu\n")
    o = wynik(pismo(papier="", pelnomocnik="reprezentowana przez Prezesa Zarządu Adama Fikcyjnego\n", dotyczy=dot, wstep=wstep, ogon=ogon))["Odwolujacy"][0]
    assert o["przez-pelnomocnika"] == 0
    assert o["pelnomocnik"] == {"imie_nazwisko": None, "nazwa": None, "mail": None}
