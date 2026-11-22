"""Pełnomocnictwo pisane prozą (druga rodzina dokumentów: pismo na papierze firmowym, jedno zdanie komparycji,
pełnomocnicy w mianowniku z tytułem po nazwisku, podpisy obok siebie albo stempel e-podpisu). Tekst syntetyczny,
dane fikcyjne."""
from pathlib import Path

from odwolania2json.potok import Potok
from odwolania2json.silnik import Silnik

KORZEN = Path(__file__).resolve().parents[1]
POTOK = Potok(KORZEN / "config/klasy", uzyj_llm=False)

ZAKRES = ("do reprezentowania Mocodawcy w sprawie dotyczącej środków ochrony prawnej w postępowaniu o udzielenie\n"
          "zamówienia publicznego pn. „Dostawa mebli biurowych”, numer postępowania: ZP.1.2026, prowadzonym przez\n"
          "Zamawiającego – Gmina Testowa Dolna, w tym w szczególności do:\n"
          "– wniesienia odwołania oraz składania pism procesowych,\n"
          "– zastępowania Mocodawcy na rozprawach przed Krajową Izbą Odwoławczą,\n")


def _osoby(lista):
    return [o["imie_nazwisko"] for o in lista]


def test_reprezentanci_z_klauzuli_i_podpisy_obok_siebie():
    t = ("Borealis Technika S.A.\nBTS\nBorealis Technika S.A. | ul. Długa 5, 00-001 Warszawa\n"
         "Kielce, 02.06.2026 r.\nP E Ł N O M O C N I C T W O\n"
         "Borealis Technika spółka akcyjna z siedzibą w Kraków (30-001), ul. Krótka 7, wpisana do\n"
         "rejestru przedsiębiorców Krajowego Rejestru Sądowego pod numerem KRS: 9990000001, NIP:\n"
         "999-111-22-33, REGON: 999000111, reprezentowana przez: Jan Nowak – Prezes Zarządu, Anna\n"
         "Kowalska-Lis – Członek Zarządu (dalej: „Mocodawca”), niniejszym udziela pełnomocnictwa:\n"
         "Piotr Zieliński (adwokat, nr wpisu WA-101) oraz Ewa Wilk (radca prawny, nr\n"
         "wpisu KR-202, PESEL: 80010112345) oraz Adam Lis (radca prawny, nr wpisu PO-303),\n"
         + ZAKRES +
         "Za Mocodawcę:\nAnna Kowalska-Lis – Członek Zarządu Jan Nowak – Prezes Zarządu\n"
         "Borealis Technika S.A. · ul. Krótka 7, 30-001 Kraków\n")
    w = POTOK.przetworz_tekst(t)
    assert w.klasa == "pelnomocnictwo"
    m = w.dane["mocodawca"]
    assert len(m) == 1
    assert m[0]["data"] == {"imie_nazwisko": None, "krs": "9990000001", "nazwa": "Borealis Technika spółka akcyjna",
                            "nip": "9991112233", "typ": "osoba_prawna"}
    assert _osoby(m[0]["podpisujacy"]) == ["Jan Nowak", "Anna Kowalska-Lis"]   # kolejność z klauzuli
    assert w.dane["pelnomocnicy"] == [{"imie_nazwisko": "Piotr Zieliński", "pesel": None},
                                      {"imie_nazwisko": "Ewa Wilk", "pesel": "80010112345"},
                                      {"imie_nazwisko": "Adam Lis", "pesel": None}]


def test_konsorcjum_wspolny_blok_podpisow_i_lista_numerowana():
    t = ("Toruń, dnia 3 czerwca 2026 roku\nPEŁNOMOCNICTWO\n"
         "Wykonawcy wspólnie ubiegający się o udzielenie zamówienia (Konsorcjum):\n"
         "1) Alfa Systemy sp. k. z siedzibą w Łódź (90-001), ul. Długa 1, wpisana do rejestru przedsiębiorców\n"
         "Krajowego Rejestru Sądowego pod numerem KRS: 9990000002, NIP: 999-222-33-44, REGON: 999000222,\n"
         "reprezentowana przez: Maria Wrona – Prezes Zarządu\n– Lider Konsorcjum,\n"
         "2) Beta Budowa spółka z ograniczoną odpowiedzialnością z siedzibą w Kalisz (62-800), ul.\n"
         "Krótka 2, wpisana do rejestru przedsiębiorców Krajowego Rejestru Sądowego pod numerem\n"
         "KRS: 9990000003, NIP: 999-33-44-555, REGON: 999000333, reprezentowana przez: Tomasz\n"
         "Sowa – Prokurent – Partner Konsorcjum,\n"
         "(dalej łącznie: „Mocodawca”), niniejszym udzielają pełnomocnictwa:\n"
         "1. Olga Kruk – radca prawny, nr wpisu XX-1, PESEL: 90010112345,\n"
         "2. Karol Wrona – adwokat, nr wpisu WA-2,\n"
         + ZAKRES +
         "Za Mocodawcę:\nTomasz Sowa – Prokurent Maria Wrona – Prezes Zarządu\n"
         "Alfa Systemy sp. k.\nul. Długa 1, 90-001 Łódź\nNIP 999-222-33-44\n")
    w = POTOK.przetworz_tekst(t)
    m = w.dane["mocodawca"]
    assert [(x["data"]["nazwa"], x["data"]["krs"], x["data"]["nip"]) for x in m] == [
        ("Alfa Systemy sp. k.", "9990000002", "9992223344"),
        ("Beta Budowa spółka z ograniczoną odpowiedzialnością", "9990000003", "9993344555")]
    assert _osoby(m[0]["podpisujacy"]) == ["Maria Wrona"]     # z klauzuli tego mocodawcy, nie z kolejności podpisów
    assert _osoby(m[1]["podpisujacy"]) == ["Tomasz Sowa"]
    assert w.dane["pelnomocnicy"] == [{"imie_nazwisko": "Olga Kruk", "pesel": "90010112345"},
                                      {"imie_nazwisko": "Karol Wrona", "pesel": None}]


def test_slupek_nazwisk_bez_tytulow_i_stopka_kancelarii():
    t = ("K I S\nKANCELARIA RADCY PRAWNEGO IRENA SROKA\nul. Wąska 1, 26-001 Radom\n"
         "Radom, dnia 5 maja 2026 roku\nPEŁNOMOCNICTWO\n"
         "Gamma Serwis sp. z o.o. z siedzibą w Radom (26-002), ul. Lipowa 3, wpisana\n"
         "do rejestru przedsiębiorców Krajowego Rejestru Sądowego pod numerem KRS: 9990000004, NIP:\n"
         "9994445566, REGON: 999000444, reprezentowana przez: Paweł Dudek – Wiceprezes\n"
         "Zarządu (dalej: „Mocodawca”), niniejszym udziela pełnomocnictwa:\n"
         "Irena Sroka\nMarek Czyż\n"
         + ZAKRES +
         "Signature Not Verified\nDokument podpisany przez Paweł Dudek\nData: 2026.05.05 12:00:01 CEST\n"
         "■ Kancelaria Radcy Prawnego Jerzy Kos · ul. Lipowa 3, 26-002 Radom\n")
    w = POTOK.przetworz_tekst(t)
    assert w.dane["mocodawca"][0]["data"]["nazwa"] == "Gamma Serwis sp. z o.o."
    assert _osoby(w.dane["mocodawca"][0]["podpisujacy"]) == ["Paweł Dudek"]
    # nazwisko ze stopki kancelarii nie jest pełnomocnikiem
    assert w.dane["pelnomocnicy"] == [{"imie_nazwisko": "Irena Sroka", "pesel": None},
                                      {"imie_nazwisko": "Marek Czyż", "pesel": None}]


def test_stempel_epodpisu_bez_dwukropka_gdy_brak_klauzuli():
    t = ("PEŁNOMOCNICTWO\n"
         "Delta Usługi sp. z o.o., ul. Długa 5, 00-001 Warszawa, wpisana do KRS pod nr 9990000005, NIP 9995556677\n"
         "niniejszym udziela pełnomocnictwa radcy prawnemu Jakubowi Zielińskiemu do reprezentowania przed Krajową Izbą Odwoławczą.\n"
         "Signature Not Verified\nDokument podpisany przez Zofia Bąk\nData: 2026.06.01 08:15:30 CEST\n")
    w = POTOK.przetworz_tekst(t)
    assert _osoby(w.dane["mocodawca"][0]["podpisujacy"]) == ["Zofia Bąk"]
    assert _osoby(w.dane["pelnomocnicy"]) == ["Jakub Zieliński"]      # stary układ: tytuł przed nazwiskiem, celownik


def test_podpisy_obok_siebie_gdy_brak_klauzuli():
    t = ("PEŁNOMOCNICTWO\n"
         "Delta Usługi sp. z o.o., ul. Długa 5, 00-001 Warszawa, wpisana do KRS pod nr 9990000005, NIP 9995556677\n"
         "niniejszym udziela pełnomocnictwa adw. Jakub Zieliński do reprezentowania przed Krajową Izbą Odwoławczą.\n"
         "Za Mocodawcę:\nZofia Bąk – Prezes Zarządu Karol Wrona – Członek Zarządu\n")
    w = POTOK.przetworz_tekst(t)
    assert _osoby(w.dane["mocodawca"][0]["podpisujacy"]) == ["Zofia Bąk", "Karol Wrona"]


def test_nazwa_mocodawcy_zlamana_na_dwie_linie():
    t = ("Kielce, 02.06.2026 r.\nPEŁNOMOCNICTWO\n"
         "Przedsiębiorstwo Robót Inżynieryjnych i Drogowych Epsilon spółka z ograniczoną\n"
         "odpowiedzialnością z siedzibą w Kraków (30-001), ul. Krótka 7, wpisana do rejestru przedsiębiorców\n"
         "Krajowego Rejestru Sądowego pod numerem KRS: 9990000006, NIP: 9996667788, reprezentowana przez:\n"
         "Jan Nowak – Prezes Zarządu (dalej: „Mocodawca”), niniejszym udziela pełnomocnictwa:\n"
         "1.\nPiotr Zieliński – adwokat, nr wpisu WA-101,\n" + ZAKRES)
    w = POTOK.przetworz_tekst(t)
    m = w.dane["mocodawca"][0]
    assert m["data"]["nazwa"] == ("Przedsiębiorstwo Robót Inżynieryjnych i Drogowych Epsilon spółka z ograniczoną "
                                  "odpowiedzialnością")
    assert _osoby(m["podpisujacy"]) == ["Jan Nowak"]
    assert _osoby(w.dane["pelnomocnicy"]) == ["Piotr Zieliński"]


def test_silnik_warianty_listy_pierwszy_niepusty_wygrywa():
    klasa = {
        "sekcje": {"blok": {"od": "LISTA:", "do": ["KONIEC"]}},
        "wynik": {"osoby": {
            "lista": {"warianty": [{"w": "blok", "regex": r"\b[A-Z][a-z]+\b", "flagi": ["m"]},
                                   {"regex": r"osoba (\w+)"}]},
            "element": {"imie": {"metody": [{"calosc": True}]}}}},
    }
    s = Silnik(klasa)
    assert s.ekstrahuj("LISTA: Ala, Ola KONIEC osoba Ewa").dane == {"osoby": [{"imie": "Ala"}, {"imie": "Ola"}]}
    assert s.ekstrahuj("LISTA: 1, 2 KONIEC osoba Ewa").dane == {"osoby": [{"imie": "Ewa"}]}   # sekcja jest, ale pusta
    assert s.ekstrahuj("osoba Ewa").dane == {"osoby": [{"imie": "Ewa"}]}                      # sekcji nie ma


def test_podpis_po_zdaniu_o_dalszych_pelnomocnictwach_nie_jest_pelnomocnikiem():
    t = ("PEŁNOMOCNICTWO\n"
         "Delta Usługi sp. z o.o., ul. Długa 5, 00-001 Warszawa, wpisana do KRS pod nr 9990000005, NIP 9995556677\n"
         "niniejszym udziela pełnomocnictwa adw. Jakub Zieliński do reprezentowania przed Krajową Izbą Odwoławczą.\n"
         "Pełnomocnik jest upoważniony do udzielania pełnomocnictw\n"
         "Zofia Bąk – Prezes Zarządu\n")
    w = POTOK.przetworz_tekst(t)
    assert _osoby(w.dane["pelnomocnicy"]) == ["Jakub Zieliński"]


def test_reprezentant_przed_nazwiskiem_i_pelnomocnicy_w_celowniku_z_forma_grzecznosciowa():
    # funkcja przed nazwiskiem w dopełniaczu, pod podpisem tylko „(podpis Prezesa Zarządu)”; pełnomocnicy w celowniku
    t = ("Lublin, 3 marca 2026 r.\nPEŁNOMOCNICTWO\n"
         "Delta Instalacje sp. z o.o. z siedzibą w Lublinie (ul. Krótka 3, 20-001 Lublin), wpisana do rejestru\n"
         "przedsiębiorców KRS pod numerem KRS 9990000011, NIP 999 000 00 22, REGON 999000033, reprezentowana przez\n"
         "Prezesa Zarządu Pana Jana Dąbka, uprawnionego do samodzielnej reprezentacji, niniejszym udziela pełnomocnictwa:\n"
         " 1) radcy prawnemu Panu Michałowi Kwiatkowi (nr wpisu LU-1),\n"
         "2) adwokat Pani Joannie Kos (nr wpisu LU/Adw/2),\n"
         + ZAKRES +
         " ............................................\n (podpis Prezesa Zarządu)\n")
    w = POTOK.przetworz_tekst(t)
    assert w.klasa == "pelnomocnictwo"
    m = w.dane["mocodawca"]
    assert len(m) == 1
    assert m[0]["data"]["nazwa"] == "Delta Instalacje sp. z o.o."
    assert _osoby(m[0]["podpisujacy"]) == ["Jan Dąbek"]
    assert _osoby(w.dane["pelnomocnicy"]) == ["Michał Kwiatek", "Joanna Kos"]


def test_konsorcjum_jdg_bez_nazwiska_pod_podpisem_i_reprezentanci_w_dopelniaczu():
    t = ("Opole, 5 maja 2026 r.\nPEŁNOMOCNICTWO\n"
         "My, niżej podpisani, działając w imieniu wykonawców wspólnie ubiegających się o udzielenie\n"
         "zamówienia pn. „Budowa kładki” (ZP.2.2026):\n"
         " 1) Zofia Mak, prowadząca działalność gospodarczą pod firmą MAK-SERWIS Zofia Mak, NIP\n"
         "9990000033, REGON 999000044,\n"
         "2) Gamma Stal sp. z o.o., KRS 9990000055, NIP 9990000066, reprezentowana przez\n"
         "Piotra Kubka – Prezesa Zarządu oraz Ewę Lis – Członka Zarządu,\n"
         "ustanawiamy pełnomocnikiem radcę prawnego Adama Kruka, uprawnionego do samodzielnego działania,\n"
         "w celu reprezentowania wykonawców przed Krajową Izbą Odwoławczą.\n"
         "za MAK-SERWIS:\n..............................\n(podpis właściciela)\n"
         "za Gamma Stal sp. z o.o.:\n..............................\n(podpisy członków Zarządu)\n")
    w = POTOK.przetworz_tekst(t)
    assert w.klasa == "pelnomocnictwo"
    m = w.dane["mocodawca"]
    assert len(m) == 2
    assert m[0]["data"] == {"imie_nazwisko": "Zofia Mak", "krs": None, "nazwa": "MAK-SERWIS Zofia Mak",
                            "nip": "9990000033", "typ": "osoba_fizyczna"}
    assert _osoby(m[0]["podpisujacy"]) == ["Zofia Mak"]          # sama przedsiębiorczyni, nie „podpis właściciela”
    assert m[1]["data"]["nazwa"] == "Gamma Stal sp. z o.o."
    assert _osoby(m[1]["podpisujacy"]) == ["Piotr Kubek", "Ewa Lis"]
    assert _osoby(w.dane["pelnomocnicy"]) == ["Adam Kruk"]
