"""Stres-test klasyfikacji: typ po usunięciu linii tytułowych i/lub drugiej połowy tekstu. Uruchom: OCR=0 python scripts/stres_klasyfikacji.py"""
import glob, re, sys, collections
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from odwolania2json.klasy import UstawieniaKlasyfikacji, rozpoznaj, wczytaj_klasy
from odwolania2json.pdftext import wczytaj
K = wczytaj_klasy(Path("config/klasy")); U = UstawieniaKlasyfikacji.z_pliku(Path("config/aplikacja.yaml"))
def bez_tytulu(t):
    out=[]
    for l in t.splitlines():
        z=re.sub(r"\s+","",l); lit=[c for c in z if c.isalpha()]
        if z and len(z)<=70 and not re.search(r"[\d:@]",z) and lit and (all(c.isupper() for c in lit) or len(z)<=30): continue
        out.append(l)
    return "\n".join(out)
def tylko_pierwsza_polowa(t): return t[:len(t)//2]
wynik=collections.Counter(); zle=[]
for p in sorted(glob.glob("data/raw/uzp/dane/*/*.pdf"))+sorted(glob.glob("tests/kontrolny/input/*/*.pdf")):
    t=wczytaj(Path(p)).tekst
    r0=rozpoznaj(t,K,U); ok=r0.klasa.nazwa if r0.klasa else None
    if ok is None: continue
    for nazwa,f in [("bez_tytulu",bez_tytulu),("polowa",tylko_pierwsza_polowa),("bez_tytulu+polowa",lambda x: tylko_pierwsza_polowa(bez_tytulu(x)))]:
        r=rozpoznaj(f(t),K,U); k=r.klasa.nazwa if r.klasa else None
        wynik[(nazwa,ok,k==ok)]+=1
        if k!=ok: zle.append((nazwa,ok,k,r.punkty,p))
for k,v in sorted(wynik.items()): print(k,v)
for z in zle[:8]: print(z)
