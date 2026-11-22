"""Klasyfikacja typu odporna na układ: tytuł z rozstrzelonymi literami, brak etykiet, pisma innych stron."""
from pathlib import Path

import pytest

from odwolania2json.klasy import UstawieniaKlasyfikacji, rozpoznaj, strefa_tytulu, wczytaj_klasy

KORZEN = Path(__file__).resolve().parents[1]
KLASY = wczytaj_klasy(KORZEN / "config/klasy")
UST = UstawieniaKlasyfikacji.z_pliku(KORZEN / "config/aplikacja.yaml")

PRZYPADKI = {
    "odwolanie": [
        "Warszawa, 3 marca 2026 r.\nDo Prezesa Krajowej Izby Odwoławczej\nWykonawca: Alfa sp. z o.o.\n"
        "Zamawiający – Gmina Beta\nO d w o ł a n i e\nod czynności zamawiającego\n"
        "Na podstawie art. 513 Pzp wnoszę odwołanie od czynności i zaniechań Zamawiającego.",
        "ODWOŁANIE OD CZYNNOŚCI ZAMAWIAJĄCEGO\nW imieniu wykonawcy Alfa S.A. wnoszę odwołanie. Zarzucam naruszenie art. 226 Pzp.",
        "Szanowni Państwo,\nniniejszym wnoszę odwołanie do Krajowej Izby Odwoławczej od czynności Zamawiającego "
        "polegającej na odrzuceniu oferty. Zarzucam Zamawiającemu naruszenie przepisów ustawy Prawo zamówień publicznych.",
    ],
    "pelnomocnictwo": [
        "Pełnomocnictwo\nAlfa sp. z o.o. udziela pełnomocnictwa radcy prawnemu Janowi Nowakowi do reprezentowania "
        "w postępowaniu odwoławczym przed Krajową Izbą Odwoławczą, w tym do wniesienia odwołania.",
        "P E Ł N O M O C N I C T W O\nMocodawca: Alfa S.A.\nUpoważniam adw. Annę Kowalską do działania w sprawie odwołania.",
        "UPOWAŻNIENIE\nZarząd spółki Alfa upoważnia Pana Jana Nowaka do reprezentowania spółki przed KIO.",
    ],
    "przelew": [
        "Potwierdzenie przelewu\nData operacji: 2026-03-02\nZ rachunku: PL61 1090 1014 0000 0712 1981 2874\n"
        "Na rachunek: 12 1010 1010 0000 0000 0000 0000\nKwota: 15 000,00 PLN\nTytuł: wpis od odwołania",
        "Bank potwierdza, że w dniu 2 marca 2026 wykonano przelew krajowy z rachunku nr 61 1090 1014 0000 0712 1981 2874 "
        "na rachunek Urzędu Zamówień Publicznych w kwocie 7 500,00 zł tytułem wpis od odwołania.",
        "Transfer confirmation\nOrdering party: Alfa sp. z o.o.\nBeneficiary: Urząd Zamówień Publicznych\n"
        "IBAN PL12 1010 1010 0000 0000 0000 0000\nAmount: 7500.00 PLN\nExecution date: 2026-03-02",
    ],
    None: [
        "ODPOWIEDŹ NA ODWOŁANIE\nZamawiający wnosi o oddalenie odwołania w całości. Odwołujący zarzuca naruszenie art. 226 Pzp.",
        "ZGŁOSZENIE PRZYSTĄPIENIA DO POSTĘPOWANIA ODWOŁAWCZEGO\nWykonawca przystępuje po stronie Zamawiającego. "
        "Odwołanie wniesione przez Alfa sp. z o.o.",
        "WYROK\nKrajowa Izba Odwoławcza po rozpoznaniu odwołania wniesionego przez wykonawcę Alfa oddala odwołanie.",
        "Lista obecności na spotkaniu zespołu, 3 marca 2026.",
    ],
}


@pytest.mark.parametrize("oczekiwana,tekst", [(k, t) for k, ts in PRZYPADKI.items() for t in ts])
def test_typ(oczekiwana, tekst):
    r = rozpoznaj(tekst, KLASY, UST)
    assert (r.klasa.nazwa if r.klasa else None) == oczekiwana, (r.punkty, r.trafienia)


def test_strefa_tytulu_bez_spacji():
    assert "ODWOŁANIE" in strefa_tytulu("Zamawiający:\nGmina X\nO D WO ŁANIE\ndotyczy", 3000)


def test_model_rozstrzyga_niska_pewnosc():
    tekst = "Spółka udziela Panu Janowi Kowalskiemu prawa do reprezentowania jej w postępowaniu."
    wywolano = []
    def model(t, klasy):
        wywolano.append(1)
        return "pelnomocnictwo"
    ust = UstawieniaKlasyfikacji(min_punkty=0, przewaga=99)
    r = rozpoznaj(tekst, KLASY, ust, wybor_modelu=model)
    assert wywolano and r.klasa.nazwa == "pelnomocnictwo" and r.pewnosc == "model"


def test_model_nie_przywraca_klasy_bez_wymaganych_cech():
    """Z37: broszura banku z rachunkiem i kwotą, bez daty operacji: model mówi „przelew”, wynik i tak {}."""
    tekst = ("Bank Testowy S.A. – oferta dla firm\nRachunek firmowy PL61 1090 1014 0000 0712 1981 2874\n"
             "Opłata za przelew 1,00 zł. Tytuł: oferta specjalna.")
    ust = UstawieniaKlasyfikacji(min_punkty=0, przewaga=99)
    r = rozpoznaj(tekst, KLASY, ust, wybor_modelu=lambda t, k: "przelew")
    assert r.klasa is None
