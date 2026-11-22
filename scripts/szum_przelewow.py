"""Zastępcza bramka szumu OCR: przelewy (trening + teksty OCR skanów) z nałożonym szumem; ile zostaje przelewem."""
import json, os, random, re, sys, logging
from pathlib import Path
os.environ["O2J_BEZ_ENV"] = "1"; os.environ["MODEL_TRYB"] = "brak"; os.environ["OCR"] = "0"
app = Path(sys.argv[1]); sys.path.insert(0, str(app / "src")); logging.disable(logging.CRITICAL)
from odwolania2json.potok import Potok
from odwolania2json.pdftext import wczytaj
S = Path(os.environ.get("SZUM_OCR_TXT", "/nieistnieje"))  # opcjonalnie katalog z tekstami OCR skanów (ocr_txt…)
potok = Potok(app / "config" / "klasy", uzyj_llm=False)
teksty = [wczytaj(p).tekst for p in sorted((app / "data/raw/uzp/dane").glob("przyklad_*/*.pdf")) if "przel" in p.name or "potwierdz" in p.name]
for d in ("ocr_txt", "ocr_txt_mistral_md"):
    for f in sorted((S / d).glob("potwierdzenia_*.json")) if (S / d).is_dir() else []:
        teksty.append("\n".join(json.load(open(f))["strony"]))
ZAM = {"0": "O", "1": "l", "5": "S", "8": "B"}
PL = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
def szum(t, r, poziom):
    t = "".join(ZAM[c] if c in ZAM and r.random() < poziom else c for c in t)          # cyfry jak litery
    if r.random() < 0.5: t = t.translate(PL)                                              # bez polskich znaków
    t = re.sub(r" ", lambda m: "" if r.random() < poziom else " ", t)                      # sklejone słowa
    linie = t.split("\n")
    if r.random() < 0.5 and linie:                                                         # zgubiona linia etykiety
        k = [i for i, l in enumerate(linie) if re.search(r"(?i)tytu|kwot|data|rachun|odbior|nadaw", l)]
        if k: linie.pop(r.choice(k))
    return "\n".join(linie)
wynik = {}
for poziom in (0.0, 0.05, 0.15):
    r, ok, razem = random.Random(7), 0, 0
    for t in teksty:
        for _ in range(5):
            razem += 1
            ok += potok.przetworz_tekst(szum(t, r, poziom)).klasa == "przelew"
    wynik[poziom] = f"{ok}/{razem}"
print(len(teksty), "przelewów;", wynik)
