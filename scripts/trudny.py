"""Zestaw trudny dla porównania modeli: odwołania (trening UZP + kontrolny) z usuniętymi etykietami stron
(„Odwołujący:”, „Zamawiający:” i synonimy). Reguły tracą kotwice bloków, model musi je wskazać.
Użycie: PYTHONPATH=src python scripts/trudny.py   (model wg MODEL_TRYB / LLM_MODEL), wynik: F1 ścisły."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from odwolania2json.eval import Raport, porownaj, wczytaj_json, wczytaj_ustawienia
from odwolania2json.pdftext import wczytaj
from odwolania2json.potok import Potok

KORZEN = Path(__file__).resolve().parents[1]
ETYKIETY = re.compile(
    r"(?im)^[ \t]*(?:odwo[łl]uj[aą]c\w*(?:[ \t]*\([^)\n]*\))?|zamawiaj[aą]c\w*(?:[ \t]*\([^)\n]*\))?|wykonawc\w+[ \t]+wnosz[aą]c\w*[ \t]+odwo[łl]anie"
    r"|wykonawc\w+[ \t]+wsp[oó]lnie[^\n:]*)[ \t]*[:\-–]?[ \t]*(?=\n|(?-i:[A-ZŁŚŻŹĆ„\"]))")


def pary() -> list[tuple[Path, Path]]:
    wynik = [(p, p.with_name("odwolanie.json")) for p in sorted((KORZEN / "data/raw/uzp/dane").glob("przyklad_*/odwolanie.pdf"))]
    for pdf in sorted((KORZEN / "tests/kontrolny/input").glob("case*/*.pdf")):
        gold = KORZEN / "tests/kontrolny/oczekiwane" / pdf.parent.name / pdf.with_suffix(".json").name
        if gold.exists() and "OdwolanieKIO" in wczytaj_json(gold):
            wynik.append((pdf, gold))
    return wynik


def main() -> int:
    potok = Potok(KORZEN / "config/klasy")
    u = wczytaj_ustawienia(KORZEN / "config/ewaluacja.yaml", listy_po_tresci=True, scisle=True)
    raport = Raport()
    for pdf, gold in pary():
        dok = wczytaj(pdf)
        strony = tuple(ETYKIETY.sub("", s) for s in dok.strony)
        w = potok.przetworz_tekst("\n".join(strony), strony)
        porownaj(wczytaj_json(gold), w.dane or {}, u, "odwolanie", pdf.parent.name, raport)
    l = raport.ogolem
    f1 = 2 * l.tp / (2 * l.tp + l.fp + l.fn) if l.tp else 0.0
    model = getattr(potok.llm, "model", "same reguły")
    wyw = f"{potok.llm.wywolania} wywołań, {potok.llm.bledy} błędów" if potok.llm else "—"
    if "--pola" in sys.argv:
        for pole, lp in sorted(raport.per_pole.items(), key=lambda kv: kv[1].f1())[:12]:
            print(f"  {pole:55} F1 {lp.f1():.3f}  TP {lp.tp} FP {lp.fp} FN {lp.fn}")
    print(json.dumps({"model": model, "f1": round(f1, 4), "tp": l.tp, "fp": l.fp, "fn": l.fn, "wywolania": wyw}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
