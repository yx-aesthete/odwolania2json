"""Rozszerzalność: nowa klasa = nowy plik YAML, bez zmiany kodu."""
import shutil
from pathlib import Path

from odwolania2json.potok import Potok

KORZEN = Path(__file__).resolve().parents[1]
TEKST = """Warszawa, dnia 3 lipca 2026 r.
Prezes Krajowej Izby Odwoławczej
sygn. akt: KIO 1234/26
Przystępujący:
Alfa Budowa sp. z o.o.
ul. Prosta 1, 00-001 Warszawa
KRS: 0000123456, NIP: 525-000-11-22
ZGŁOSZENIE PRZYSTĄPIENIA
do postępowania odwoławczego po stronie Zamawiającego
"""


def test_czwarta_klasa_tylko_z_yaml(tmp_path):
    klasy = tmp_path / "klasy"
    shutil.copytree(KORZEN / "config/klasy", klasy)
    shutil.copy(KORZEN / "config/klasy-demo/przystapienie.yaml", klasy)
    w = Potok(klasy, uzyj_llm=False).przetworz_tekst(TEKST)
    assert w.klasa == "przystapienie"
    assert w.dane["PrzystapienieKIO"] == {"sygnatura": "KIO 1234/26", "strona": "zamawiajacy", "data": "2026-07-03"}
    assert w.dane["Przystepujacy"][0] == {"nazwa": "Alfa Budowa sp. z o.o.", "krs": "0000123456", "nip": "5250001122"}


def test_bez_pliku_yaml_klasa_nie_istnieje():
    w = Potok(KORZEN / "config/klasy", uzyj_llm=False).przetworz_tekst(TEKST)
    assert w.klasa != "przystapienie"
