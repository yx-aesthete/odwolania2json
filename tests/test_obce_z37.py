"""Z37: pisma spoza trzech klas mają rachunki, kwoty i słowa „przelew/rachunek”, ale nie są potwierdzeniem operacji.
Dowód pozytywny (`rozpoznanie.wymagane`) daje {} także wtedy, gdy model przy niskiej pewności wskazałby klasę.
Teksty syntetyczne, dane fikcyjne; obok przykładów ze zlecenia typy spoza listy (faktura, nota, umowa, wezwanie)."""
from pathlib import Path

import pytest

from odwolania2json.klasy import UstawieniaKlasyfikacji, rozpoznaj, wczytaj_klasy

KLASY = wczytaj_klasy(Path(__file__).resolve().parents[1] / "config" / "klasy")
UST = UstawieniaKlasyfikacji.z_pliku(Path(__file__).resolve().parents[1] / "config" / "aplikacja.yaml")
RACH = "PL61 1090 1014 0000 0712 1981 2874"

OBCE = {
    "odpis_krs": "KRAJOWY REJESTR SĄDOWY\nCentralna Informacja Krajowego Rejestru Sądowego\nOdpis aktualny z rejestru "
                 "przedsiębiorców\nNumer KRS: 0000123456\nDział 1\nNazwa: ALFA SP. Z O.O.\nKapitał zakładowy 5 000,00 zł\n"
                 "Dział 2 Organ uprawniony do reprezentacji: zarząd",
    "broszura": f"Bank Testowy – konto dla firm\nOtwórz rachunek {RACH} i wykonuj przelewy bez opłat.\nOpłata za "
                f"przelew 0,00 zł, karta 5,00 zł miesięcznie.\nZapraszamy do oddziałów.",
    "taryfa": "Taryfa opłat i prowizji Banku Testowego\nPrzelew krajowy w bankowości internetowej 1,50 zł\n"
              "Przelew natychmiastowy 5,00 zł\nProwadzenie rachunku 10,00 zł\nobowiązuje od 01.01.2026",
    "regulamin": "Regulamin świadczenia usług bankowości elektronicznej\n§ 1. Bank wykonuje przelew z rachunku "
                 f"Klienta {RACH} na podstawie dyspozycji.\n§ 2. Opłaty pobierane są zgodnie z tabelą opłat.",
    "oferta_kredytu": "Oferta kredytu obrotowego\nKwota kredytu 200 000,00 zł, oprocentowanie 7,5%, RRSO 8,1%.\n"
                      f"Środki wypłacane na rachunek {RACH}.",
    "swz_pouczenie": "Specyfikacja warunków zamówienia – rozdział XX. Pouczenie o środkach ochrony prawnej\n"
                     "Wpis od odwołania wynosi 7 500,00 zł i uiszcza się go przelewem na rachunek Urzędu Zamówień "
                     "Publicznych NBP O/O Warszawa 60 1010 1010 0081 3622 3100 0000.",
    "nadanie": "Potwierdzenie nadania przesyłki poleconej\nNadawca: Alfa sp. z o.o.\nAdresat: Krajowa Izba "
               "Odwoławcza, ul. Postępu 17A, 02-676 Warszawa\nOpłata 8,50 zł\nData nadania 03.03.2026",
    "faktura": f"FAKTURA VAT nr FV/12/2026\nData wystawienia 03.03.2026\nSprzedawca: Alfa sp. z o.o.\nNabywca: Beta S.A.\n"
               f"Do zapłaty 1 230,00 zł\nForma płatności: przelew na rachunek {RACH}, termin 14 dni",
    "nota": f"NOTA OBCIĄŻENIOWA nr 3/2026\nObciążamy Państwa kwotą 500,00 zł tytułem kary umownej.\n"
            f"Prosimy o przelew na rachunek {RACH} w terminie 7 dni.",
    "umowa": f"UMOWA nr 15/2026\n§ 5. Wynagrodzenie w kwocie 12 000,00 zł płatne przelewem na rachunek {RACH} "
             f"w terminie 30 dni od dnia doręczenia faktury.",
    "wezwanie_do_zaplaty": f"WEZWANIE DO ZAPŁATY\nWzywamy do zapłaty kwoty 2 500,00 zł na rachunek {RACH} "
                           "w terminie 7 dni od dnia otrzymania wezwania.",
}


@pytest.mark.parametrize("nazwa", sorted(OBCE))
def test_pismo_obce_nie_dostaje_klasy_nawet_gdy_model_chce(nazwa):
    r = rozpoznaj(OBCE[nazwa], KLASY, UST, wybor_modelu=lambda t, k: "przelew")
    assert r.klasa is None, (nazwa, r.punkty, r.trafienia)
