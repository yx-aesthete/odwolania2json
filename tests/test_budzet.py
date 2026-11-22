"""Budżet czasu przebiegu (Z32): po wyczerpaniu bez modelu i OCR, pliki i tak powstają."""
import json

from odwolania2json import budzet
from odwolania2json.__main__ import kolejnosc
from odwolania2json.llm import KlientLLM


def test_budzet_limit_i_wyczerpanie():
    budzet.start(100)
    try:
        assert 99 < budzet.pozostalo() <= 100
        assert budzet.limit(35) == 35 and not budzet.wyczerpany()
        budzet.start(0.0001)
        import time
        time.sleep(0.01)
        assert budzet.wyczerpany() and budzet.limit(35) == 1.0
    finally:
        budzet.zatrzymaj()
    assert budzet.pozostalo() == float("inf")


def test_klient_po_budzecie_nie_pyta_i_nie_liczy_bledu(monkeypatch):
    k = KlientLLM(base_url="http://127.0.0.1:9", api_key="k", model="m")
    wyslane = []
    monkeypatch.setattr(k, "_wyslij_raz", lambda c, n: wyslane.append(1))
    budzet.start(-1)  # bez limitu
    budzet.zatrzymaj()
    budzet.start(0.0001)
    try:
        import time
        time.sleep(0.01)
        assert not k.aktywny
        assert k("Pytanie?", "tekst") is None
        assert wyslane == [] and k.bledy == 0
    finally:
        budzet.zatrzymaj()


def test_kolejnosc_tekstowe_przed_skanami(tmp_path):
    from pypdf import PdfWriter
    pusty = tmp_path / "a_skan.pdf"
    w = PdfWriter()
    w.add_blank_page(100, 100)
    w.write(str(pusty))
    import shutil
    from pathlib import Path
    tekstowy = next((Path(__file__).parent / "kontrolny/input").rglob("*.pdf"))
    t = tmp_path / "z_tekst.pdf"
    shutil.copy(tekstowy, t)
    assert kolejnosc([pusty, t]) == [t, pusty]   # tekst przed skanem


def test_ogranicznik_limit_rownoleglosci_i_429():
    import threading
    import time
    from odwolania2json.llm import Ogranicznik
    o = Ogranicznik(2)
    naraz, maks, blok = [0], [0], threading.Lock()

    def praca():
        with o:
            with blok:
                naraz[0] += 1
                maks[0] = max(maks[0], naraz[0])
            time.sleep(0.05)
            with blok:
                naraz[0] -= 1
    w = [threading.Thread(target=praca) for _ in range(6)]
    [t.start() for t in w]
    [t.join() for t in w]
    assert maks[0] == 2
    o.zmniejsz()
    assert o.pojemnosc == 1
    o.zmniejsz()
    assert o.pojemnosc == 1
