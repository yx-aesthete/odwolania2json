"""Ewaluator F1 pole po polu: wynik (output/) kontra referencja UZP.

Metoda UZP (Discord, 21.11 11:26):
- TP: wartość jest u nas i zgadza się z referencją (pola „długie” z config/ewaluacja.yaml:
  podobieństwo >= 0,8, reszta dokładnie po normalizacji),
- FP: wartość jest tylko u nas albo jest u obu, ale nieprawidłowa,
- FN: u nas brak, a w referencji jest,
- TN: brak u obu (do F1 się nie liczy, tylko raportujemy).
Tablice domyślnie dopasowywane po treści (`--lists best`, UZP: kolejność nie gra roli); `--lists order` po kolejności.

    python -m odwolania2json.eval --gold data/raw/uzp/dane --pred output [--sprawy 41-60]
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from rapidfuzz import fuzz

log = logging.getLogger("odwolania2json.eval")
KORZEN = Path(__file__).resolve().parents[2]
KLUCZ_KLASY = {"OdwolanieKIO": "odwolanie", "mocodawca": "pelnomocnictwo", "przelew_bankowy": "przelew"}


@dataclass(frozen=True)
class Ustawienia:
    prog: float = 0.8
    pola_dlugie: frozenset[str] = frozenset({
        "Odwolujacy[].pelnomocnik.nazwa", "przelew_bankowy.tytul", "Odwolujacy[].nazwa",
        "Zamawiajacy[].nazwa", "ZamowieniePubliczne.tytul"})
    aliasy: dict = field(default_factory=lambda: {"potwierdzenie_przelewu": "przelew"})
    listy_po_tresci: bool = False
    scisle: bool = False


def wczytaj_ustawienia(sciezka: Path, listy_po_tresci: bool = False, scisle: bool = False) -> Ustawienia:
    if not sciezka.exists():
        return Ustawienia(listy_po_tresci=listy_po_tresci, scisle=scisle)
    c = yaml.safe_load(sciezka.read_text(encoding="utf-8")) or {}
    return Ustawienia(
        prog=float(c.get("prog_podobienstwa", 0.8)),
        pola_dlugie=frozenset(c.get("pola_dlugie", [])),
        aliasy=dict(c.get("aliasy_plikow", {})),
        listy_po_tresci=listy_po_tresci,
        scisle=scisle,
    )


def wczytaj_json(sciezka: Path) -> dict:
    """Plik 0 B albo pusty = dokument obcy ({}). Zły JSON liczymy jako pusty i logujemy."""
    tekst = sciezka.read_text(encoding="utf-8").strip()
    if not tekst:
        return {}
    tekst = re.sub(r"//[^\n\"]*$", "", tekst, flags=re.M)  # komentarze w oczekiwane-json
    try:
        obj = json.loads(tekst)
    except json.JSONDecodeError as exc:
        log.warning("Zły JSON %s: %s (liczę jako pusty)", sciezka, exc)
        return {}
    return obj if isinstance(obj, dict) else {}


def splaszcz(obj, prefiks: str = "") -> dict[str, object]:
    wynik: dict[str, object] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            wynik.update(splaszcz(v, f"{prefiks}.{k}" if prefiks else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            wynik.update(splaszcz(v, f"{prefiks}[{i}]"))
    else:
        wynik[prefiks] = obj
    return wynik


def normalizuj(v, scisle: bool = False) -> str | None:
    """Liczby (int/float w JSON) -> postać kanoniczna (10000.0 == 10000). Napisy cyfr (KRS, rachunek)
    zostają napisami: bez utraty zer wiodących i precyzji. Tryb luźny dodatkowo: NFKC, bez cudzysłowów,
    spacje, wielkość liter. Tryb ścisły: napis bez zmian."""
    if v is None:
        return None
    if isinstance(v, bool):
        v = int(v)
    if isinstance(v, (int, float)):
        return str(int(v)) if float(v).is_integer() else f"{float(v):.2f}"
    s = str(v)
    if not scisle:
        s = unicodedata.normalize("NFKC", s)
        s = re.sub(r"[„”“\"'’`«»]", "", s)
        s = re.sub(r"\s+", " ", s).strip().casefold()
    return None if s.strip() in ("", "null", "None") else s


POLA_RACHUNKU = ("przelew_bankowy.z_rachunku", "przelew_bankowy.na_rachunek")


def bez_pl(v: str) -> str:
    """Rachunek bez prefiksu kraju: część referencji UZP błędnie zdejmuje PL (UZP na Discordzie 21.11), więc
    w ocenie rachunki porównujemy z pominięciem PL po obu stronach (aplikacja zwraca PL, gdy stoi w dokumencie)."""
    return re.sub(r"^(?i:pl)\s*", "", v)


def zgodne(sciezka: str, gv: str, pv: str, u: Ustawienia) -> bool:
    if gv == pv:
        return True
    if sciezka.endswith(POLA_RACHUNKU) and bez_pl(gv) == bez_pl(pv):
        return True
    if ogolne_pole(sciezka) in u.pola_dlugie:  # ścieżka pola, np. Odwolujacy[].nazwa (lista UZP z Discorda)
        return fuzz.ratio(gv, pv) / 100 >= u.prog
    return False


def ogolne_pole(sciezka: str) -> str:
    return re.sub(r"\[\d+\]", "[]", sciezka)


def _trafienia(g, p, u: Ustawienia) -> int:
    gs, ps = splaszcz(g), splaszcz(p)
    n = 0
    for k, gv in gs.items():
        a, b = normalizuj(gv, u.scisle), normalizuj(ps.get(k), u.scisle)
        n += int(a is not None and b is not None and zgodne(k, a, b, u))
    return n


def wyrownaj_listy(gold, pred, u: Ustawienia):
    """Dla --lists best: ustawia elementy list w wyniku w kolejności najlepiej pasującej do referencji."""
    if isinstance(gold, dict) and isinstance(pred, dict):
        return {k: wyrownaj_listy(gold.get(k), v, u) for k, v in pred.items()}
    if isinstance(gold, list) and isinstance(pred, list):
        wolne = list(pred)
        wynik = []
        for g in gold:
            if not wolne:
                break
            najlepszy = max(wolne, key=lambda p: _trafienia(g, p, u))
            wolne.remove(najlepszy)
            wynik.append(wyrownaj_listy(g, najlepszy, u))
        return wynik + wolne
    return pred


@dataclass
class Licznik:
    tp: int = 0
    fp: int = 0
    fn: int = 0
    tn: int = 0

    def f1(self) -> float:
        p = self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0
        r = self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0
        return 2 * p * r / (p + r) if p + r else 0.0

    def dodaj(self, inny: "Licznik") -> None:
        self.tp += inny.tp
        self.fp += inny.fp
        self.fn += inny.fn
        self.tn += inny.tn


@dataclass
class Raport:
    ogolem: Licznik = field(default_factory=Licznik)
    per_pole: dict[str, Licznik] = field(default_factory=lambda: defaultdict(Licznik))
    per_klasa: dict[str, Licznik] = field(default_factory=lambda: defaultdict(Licznik))
    bledy: list[tuple[str, str, object, object]] = field(default_factory=list)
    brak_pliku: list[str] = field(default_factory=list)
    zly_typ: list[tuple[str, str, str, str]] = field(default_factory=list)
    rachunki: int = 0        # rachunki w wynikach (z_rachunku, na_rachunek)
    rachunki_pl: int = 0     # w tym z prefiksem PL


def porownaj(gold: dict, pred: dict, u: Ustawienia, klasa: str, gdzie: str, raport: Raport) -> None:
    if u.listy_po_tresci:
        pred = wyrownaj_listy(gold, pred, u)
    g, p = splaszcz(gold), splaszcz(pred)
    for klucz in sorted(set(g) | set(p)):
        gv, pv = normalizuj(g.get(klucz), u.scisle), normalizuj(p.get(klucz), u.scisle)
        l = Licznik()
        g0, p0 = g.get(klucz), p.get(klucz)
        if klucz.endswith(POLA_RACHUNKU) and isinstance(p0, str) and p0:
            raport.rachunki += 1
            raport.rachunki_pl += p0.upper().startswith("PL")
        zly_typ = g0 is not None and p0 is not None and _typ(g0) != _typ(p0)
        if zly_typ:
            raport.zly_typ.append((gdzie, klucz, _typ(g0), _typ(p0)))
        if gv is None and pv is None:
            l.tn = 1
        elif gv is not None and pv is not None and not (u.scisle and zly_typ) and zgodne(klucz, gv, pv, u):
            # tryb ścisły: "100" zamiast 100 (albo odwrotnie) to błąd (FP), jak u automatu porównującego JSON
            l.tp = 1
        else:
            l.fp = int(pv is not None)
            l.fn = int(pv is None)
            raport.bledy.append((gdzie, klucz, g.get(klucz), p.get(klucz)))
        raport.ogolem.dodaj(l)
        raport.per_pole[f"{klasa}:{ogolne_pole(klucz)}"].dodaj(l)
        raport.per_klasa[klasa].dodaj(l)


def _typ(v) -> str:
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "liczba"
    return type(v).__name__


def klasa_z_json(obj: dict) -> str:
    return next((kl for k, kl in KLUCZ_KLASY.items() if k in obj), "obcy" if not obj else "nieznana")


def zakres_spraw(tekst: str | None) -> set[int] | None:
    if not tekst:
        return None
    wynik: set[int] = set()
    for czesc in tekst.split(","):
        a, _, b = czesc.partition("-")
        wynik.update(range(int(a), int(b or a) + 1))
    return wynik


def numer_sprawy(nazwa: str) -> int | None:
    m = re.search(r"(\d+)$", nazwa)
    return int(m.group(1)) if m else None


def ewaluuj(gold_dir: Path, pred_dir: Path, u: Ustawienia, sprawy: set[int] | None = None) -> Raport:
    raport = Raport()
    odwrotne = {v: k for k, v in u.aliasy.items()}
    for sprawa in sorted(d for d in gold_dir.iterdir() if d.is_dir()):
        if sprawy is not None and numer_sprawy(sprawa.name) not in sprawy:
            continue
        # zbiór dokumentów = PDF ∪ referencja ∪ wynik (nazwa referencji po aliasie: potwierdzenie_przelewu -> przelew)
        psprawa = pred_dir / sprawa.name
        nazwy = {u.aliasy.get(p.stem, p.stem) for p in sprawa.glob("*.pdf")}
        nazwy |= {p.stem for p in sprawa.glob("*.json")}
        nazwy |= {u.aliasy.get(p.stem, p.stem) for p in psprawa.glob("*.json")} if psprawa.is_dir() else set()
        for nazwa in sorted(nazwy):
            gplik = sprawa / f"{nazwa}.json"
            gold = wczytaj_json(gplik) if gplik.exists() else {}
            kandydaci = [psprawa / f"{nazwa}.json"] + ([psprawa / f"{odwrotne[nazwa]}.json"] if nazwa in odwrotne else [])
            pplik = next((k for k in kandydaci if k.exists()), None)
            if pplik is None:
                raport.brak_pliku.append(f"{sprawa.name}/{nazwa}.json")
            pred = wczytaj_json(pplik) if pplik else {}
            klasa = klasa_z_json(gold) if gold else klasa_z_json(pred)
            porownaj(gold, pred, u, klasa if gold else f"{klasa} (brak referencji)", f"{sprawa.name}/{nazwa}", raport)
    return raport


def tabela_md(raport: Raport) -> str:
    o = raport.ogolem
    w = [f"**F1 ogółem: {o.f1():.4f}** (TP {o.tp}, FP {o.fp}, FN {o.fn}, TN {o.tn})", "",
         "| Typ | F1 | TP | FP | FN |", "|---|---|---|---|---|"]
    w += [f"| {k} | {l.f1():.4f} | {l.tp} | {l.fp} | {l.fn} |" for k, l in sorted(raport.per_klasa.items())]
    w += ["", "| Pole | F1 | TP | FP | FN | TN |", "|---|---|---|---|---|---|"]
    for pole, l in sorted(raport.per_pole.items(), key=lambda kv: (kv[1].f1(), -(kv[1].fp + kv[1].fn))):
        if l.tp + l.fp + l.fn:
            w.append(f"| `{pole}` | {l.f1():.3f} | {l.tp} | {l.fp} | {l.fn} | {l.tn} |")
    return "\n".join(w)


def drukuj(raport: Raport, top: int) -> None:
    print(tabela_md(raport))
    if raport.zly_typ:
        print(f"\nZły typ wartości: {len(raport.zly_typ)} (np. {raport.zly_typ[:3]})")
    if raport.rachunki:
        print(f"\nRachunki w wynikach: {raport.rachunki}, w tym z PL: {raport.rachunki_pl} "
              "(porównanie z referencją bez PL po obu stronach)")
    if raport.brak_pliku:
        print(f"\nBrak pliku wyniku: {len(raport.brak_pliku)} (np. {raport.brak_pliku[:3]})")
    if top:
        print(f"\nPierwsze {top} błędów (sprawa, pole, oczekiwane, zwrócone):")
        for b in raport.bledy[:top]:
            print(f"  {b[0]:28s} {b[1]:38s} {b[2]!r:50.50s} | {b[3]!r:.50s}")
    print("\nNajczęstsze błędne pola:", Counter(ogolne_pole(b[1]) for b in raport.bledy).most_common(10))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="F1 pole po polu względem referencji UZP")
    ap.add_argument("--gold", type=Path, default=KORZEN / "data/raw/uzp/dane")
    ap.add_argument("--pred", type=Path, default=KORZEN / "output")
    ap.add_argument("--config", type=Path, default=KORZEN / "config/ewaluacja.yaml")
    ap.add_argument("--lists", choices=["order", "best"], default="best")
    ap.add_argument("--scisle", action="store_true", help="napisy bez normalizacji (poza progiem dla długich pól)")
    ap.add_argument("--sprawy", help="np. 1-40 (dev) albo 41-60 (holdout)")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--md", type=Path, help="zapisz tabelę Markdown (np. docs/WYNIKI.md)")
    a = ap.parse_args(argv)
    u = wczytaj_ustawienia(a.config, a.lists == "best", a.scisle)
    raport = ewaluuj(a.gold, a.pred, u, zakres_spraw(a.sprawy))
    drugi = ewaluuj(a.gold, a.pred, wczytaj_ustawienia(a.config, a.lists == "best", not a.scisle),
                    zakres_spraw(a.sprawy))
    tryb = "ścisły" if a.scisle else "luźny"
    print(f"F1 tryb {tryb}: {raport.ogolem.f1():.4f} | tryb {'luźny' if a.scisle else 'ścisły'}: "
          f"{drugi.ogolem.f1():.4f}\n")
    drukuj(raport, a.top)
    if a.md:
        a.md.write_text(f"Tryb {tryb}; drugi tryb F1 = {drugi.ogolem.f1():.4f}\n\n" + tabela_md(raport) + "\n",
                        encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
