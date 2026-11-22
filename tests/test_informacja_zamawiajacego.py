"""Pismo zamawiającego przekazujące kopię odwołania (art. 524 Pzp) nie jest odwołaniem, nawet z doklejoną kopią."""
from pathlib import Path

import pytest

from odwolania2json.klasy import rozpoznaj, wczytaj_klasy

KLASY = wczytaj_klasy(Path(__file__).resolve().parents[1] / "config" / "klasy")

ODWOLANIE = """Testowo, dnia 11 września 2026 r.
Prezes Krajowej Izby Odwoławczej
ul. Postępu 17A, 02-676 Warszawa
Odwołujący: Alfa Budowa sp. z o.o.
ul. Polna 1, 00-001 Testowo
KRS: 9990000001, NIP: 9990000002, REGON: 999000003
Zamawiający: Gmina Testowa
ul. Ratuszowa 1, 00-950 Testowo
ODWOŁANIE
Działając w imieniu Odwołującego, wnoszę odwołanie wobec czynności Zamawiającego polegającej na odrzuceniu oferty.
Zarzut nr 1: naruszenie art. 226 ust. 1 pkt 5 Pzp.
Kopia odwołania została przekazana Zamawiającemu przed upływem terminu do wniesienia odwołania.
"""

NAGLOWEK = """Gmina Testowa
ul. Ratuszowa 1, 00-950 Testowo
Testowo, dnia 14 września 2026 r.
Wykonawcy uczestniczący w postępowaniu
Dotyczy: postępowania nr ZP.271.14.2026
"""

PISMA = {
    "wezwanie": "Zamawiający informuje, że w dniu 11 września 2026 r. wykonawca Alfa Budowa sp. z o.o. wniósł odwołanie. "
                "Zamawiający wzywa wykonawców do przystąpienia do postępowania odwoławczego.",
    "zawiadomienie": "Zamawiający zawiadamia o wniesieniu odwołania. Wykonawca może zgłosić przystąpienie "
                     "w terminie 3 dni od dnia otrzymania kopii odwołania.",
    "wplynelo": "Informuję, iż w dniu 11.09.2026 r. wpłynęło odwołanie wykonawcy Alfa Budowa sp. z o.o. Kopia w załączeniu.",
    "zamieszcza": "Działając na podstawie art. 524 ustawy Prawo zamówień publicznych Zamawiający zamieszcza odwołania, "
                  "które zostały wniesione przez Wykonawców.",
    "udzial": "Jednocześnie Zamawiający wzywa Wykonawców do wzięcia udziału w postępowaniu toczącym się w wyniku "
              "wniesienia odwołania.",
    "przystapili": "Uczestnikami stają się wykonawcy, którzy przystąpili do postępowania w terminie 3 dni od dnia "
                   "otrzymania niniejszego wezwania.",
    "zgloszenie": "Zgłoszenie przystąpienia do postępowania odwoławczego doręcza się Prezesowi Izby.",
}


def _klasa(tekst: str):
    r = rozpoznaj(tekst, KLASY)
    return r.klasa.nazwa if r.klasa else None


def test_samo_odwolanie_zostaje_odwolaniem():
    assert _klasa(ODWOLANIE) == "odwolanie"


@pytest.mark.parametrize("nazwa", sorted(PISMA))
def test_pismo_zamawiajacego_z_kopia_odwolania_jest_obce(nazwa):
    assert _klasa(NAGLOWEK + PISMA[nazwa] + "\n" + ODWOLANIE) is None
