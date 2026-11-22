"""Z35: stan „per dokument” klienta modelu nie przecieka między wątkami plików (CLI, PLIKI_WATKI)."""
import threading
import urllib.error

from odwolania2json.llm import KlientLLM, Wylacznik


def _klient(blad_w: str) -> KlientLLM:
    k = KlientLLM(base_url="http://x.example/v1", model="m", max_bledow=2, proby=(), wylacznik=Wylacznik(prog=100))

    def wyslij(cialo, naglowki):
        if blad_w in str(cialo):
            raise urllib.error.URLError("awaria")
        return {"choices": [{"message": {"content": "ok"}}]}
    k._wyslij_raz = wyslij
    return k


def test_bledy_jednego_dokumentu_nie_wylaczaja_modelu_w_drugim_watku():
    k = _klient("ZLY")
    start, wyniki = threading.Barrier(2), {}

    def dokument(nazwa: str, tekst: str):
        k.nowy_dokument()
        start.wait()
        odp = [k(f"pytanie {i}", f"{tekst} {i}") for i in range(4)]
        wyniki[nazwa] = (odp, k.aktywny)
        k.koniec_dokumentu()

    w = [threading.Thread(target=dokument, args=("zly", "ZLY")), threading.Thread(target=dokument, args=("dobry", "DOBRY"))]
    [t.start() for t in w]
    [t.join() for t in w]
    assert wyniki["dobry"] == (["ok"] * 4, True)          # drugi dokument dostaje model
    assert wyniki["zly"][0] == [None] * 4 and wyniki["zly"][1] is False
    assert k.bledy == 2 and k.wywolania == 4               # po limicie zły dokument już nie pyta
    assert "1 dokumentów bez modelu" in k.podsumowanie()


def test_klient_ocr_awaria_w_jednym_watku_drugi_dostaje_tekst():
    from PIL import Image
    k = KlientLLM(base_url="http://x.example/v1", model="ocr", max_bledow=2, proby=(), wylacznik=Wylacznik(prog=100))

    def wyslij(cialo, naglowki):
        if threading.current_thread().name == "zly":
            raise urllib.error.URLError("awaria")
        return {"choices": [{"message": {"content": "Tekst strony skanu"}}]}
    k._wyslij_raz = wyslij
    wyniki, start = {}, threading.Barrier(2)

    def strona():
        nazwa = threading.current_thread().name
        k.nowy_dokument()
        start.wait()
        out = []
        for kolor in ("white", "gray", "black"):
            try:
                out.append(k.przepisz_obraz(Image.new("RGB", (20, 20), kolor)))
            except Exception:
                out.append(None)
        wyniki[nazwa] = out
        k.koniec_dokumentu()

    w = [threading.Thread(target=strona, name=n) for n in ("zly", "dobry")]
    [t.start() for t in w]
    [t.join() for t in w]
    assert wyniki["dobry"] == ["Tekst strony skanu"] * 3
    assert wyniki["zly"] == [None] * 3 and not k.wylacznik.wylaczony
