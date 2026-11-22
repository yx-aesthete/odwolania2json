"""Diagnostyka klasyfikacji: punkty każdej klasy dla każdego PDF (trening, kontrolny, szablon)."""
import sys
from pathlib import Path

from odwolania2json.klasy import UstawieniaKlasyfikacji, rozpoznaj, wczytaj_klasy
from odwolania2json.pdftext import wczytaj

KORZEN = Path(__file__).resolve().parents[1]
klasy = wczytaj_klasy(KORZEN / "config/klasy")
ust = UstawieniaKlasyfikacji.z_pliku(KORZEN / "config/aplikacja.yaml")
for katalog in sys.argv[1:]:
    for pdf in sorted(Path(katalog).rglob("*.pdf")):
        r = rozpoznaj(wczytaj(pdf).tekst, klasy, ust)
        pkt = " ".join(f"{k[:5]}={v:g}" for k, v in r.punkty.items())
        print(f"{(r.klasa.nazwa if r.klasa else 'OBCY'):15} {r.pewnosc:13} {pkt:40} {pdf}")
