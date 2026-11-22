"""Test odporności pełnomocnictw na nowe szablony: tekst generowany z referencji treningowych UZP w 4 układach
innych niż szablony UZP (tabela z etykietami, proza „My, niżej podpisani”, paragrafy, CEIDG). Referencja ta sama,
więc wynik mierzy przenoszenie reguł na nowy szablon tej samej rodziny.
Użycie: PYTHONPATH=src python scripts/szablony_pelnomocnictw.py [--pola] [--pokaz N]"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from odwolania2json.eval import Raport, porownaj, wczytaj_json, wczytaj_ustawienia
from odwolania2json.potok import Potok

KORZEN = Path(__file__).resolve().parents[1]
FUNKCJE = ["Prezes Zarządu", "Członek Zarządu", "Prokurent", "Wiceprezes Zarządu"]
ZAKRES = ("do reprezentowania Mocodawcy w postępowaniu odwoławczym przed Krajową Izbą Odwoławczą, w tym do wniesienia "
          "odwołania, składania pism i udzielania dalszych pełnomocnictw.")


def _id(d: dict) -> str:
    czesci = [f"KRS {d['krs']}" if d.get("krs") else "", f"NIP {d['nip']}" if d.get("nip") else ""]
    return ", ".join(c for c in czesci if c)


def _tytul(i: int) -> str:
    return ["adw.", "r. pr.", "adwokat", "radca prawny"][i % 4]


def szablon_tabela(g: dict, nr: int) -> str:
    w = [f"Warszawa, {nr % 27 + 1}.10.2026", "PEŁNOMOCNICTWO PROCESOWE"]
    for m in g["mocodawca"]:
        d = m["data"]
        w += ["Mocodawca", f"Nazwa: {d['nazwa']}", "Siedziba: ul. Testowa 1, 00-001 Warszawa"]
        w += [f"KRS: {d['krs']}"] if d.get("krs") else []
        w += [f"NIP: {d['nip']}"] if d.get("nip") else []
    w += ["Pełnomocnicy"] + [f"{i + 1}. {_tytul(i)} {p['imie_nazwisko']}" for i, p in enumerate(g["pelnomocnicy"])]
    w += ["Zakres umocowania", "Pełnomocnictwo obejmuje umocowanie " + ZAKRES]
    for m in g["mocodawca"]:
        w += [f"W imieniu {m['data']['nazwa']}:"]
        for j, p in enumerate(m["podpisujacy"]):
            w += ["……………………………", f"{p['imie_nazwisko']}, {FUNKCJE[j % 4]}"]
    return "\n".join(w)


def szablon_proza(g: dict, nr: int) -> str:
    moc = "; ".join(f"{m['data']['nazwa']} z siedzibą w Poznaniu, {_id(m['data'])}" for m in g["mocodawca"])
    pel = " oraz ".join(f"{_tytul(i)} {p['imie_nazwisko']}" for i, p in enumerate(g["pelnomocnicy"]))
    w = [f"Poznań, dnia {nr % 27 + 1} listopada 2026 r.", "Pełnomocnictwo",
         f"My, niżej podpisani, działając w imieniu {moc} (dalej: „Mocodawca”), niniejszym udzielamy pełnomocnictwa: {pel}, "
         + ZAKRES]
    for m in g["mocodawca"]:
        w += [f"Za {m['data']['nazwa']}:"]
        for j, p in enumerate(m["podpisujacy"]):
            w += ["................................", f"{FUNKCJE[j % 4]}", p["imie_nazwisko"]]
    return "\n".join(w)


def szablon_paragrafy(g: dict, nr: int) -> str:
    w = [f"Gdańsk, {nr % 27 + 1}.11.2026 r.", "P E Ł N O M O C N I C T W O"]
    for k, m in enumerate(g["mocodawca"], 1):
        w += [f"§ 1.{k} Mocodawcą jest {m['data']['nazwa']}, ul. Portowa 3, 80-001 Gdańsk, {_id(m['data'])}."]
    w += ["§ 2. Mocodawca ustanawia pełnomocnikami: " + ", ".join(f"{_tytul(i)} {p['imie_nazwisko']}" for i, p in enumerate(g["pelnomocnicy"])) + "."]
    w += ["§ 3. Pełnomocnictwo upoważnia " + ZAKRES, "Podpisy osób uprawnionych do reprezentacji Mocodawcy:"]
    for m in g["mocodawca"]:
        for j, p in enumerate(m["podpisujacy"]):
            w += ["_______________________", f"{FUNKCJE[j % 4]} – {p['imie_nazwisko']}"]
    return "\n".join(w)


SZABLONY = {"tabela": szablon_tabela, "proza": szablon_proza, "paragrafy": szablon_paragrafy}


def main() -> int:
    potok = Potok(KORZEN / "config/klasy")
    u = wczytaj_ustawienia(KORZEN / "config/ewaluacja.yaml", listy_po_tresci=True, scisle=True)
    pokaz = int(sys.argv[sys.argv.index("--pokaz") + 1]) if "--pokaz" in sys.argv else 0
    golds = sorted((KORZEN / "data/raw/uzp/dane").glob("przyklad_*/pelnomocnictwo.json"))
    for nazwa, f in SZABLONY.items():
        raport, zle_typy = Raport(), 0
        for nr, gp in enumerate(golds):
            g = wczytaj_json(gp)
            if not g or any(m["data"]["typ"] != "osoba_prawna" for m in g["mocodawca"]):
                continue
            tekst = f(g, nr)
            w = potok.przetworz_tekst(tekst)
            zle_typy += w.klasa != "pelnomocnictwo"
            porownaj(g, w.dane or {}, u, "pelnomocnictwo", gp.parent.name, raport)
            if pokaz and nr < pokaz:
                print(f"--- {nazwa} {gp.parent.name}\n{tekst}\n>>> {json.dumps(w.dane, ensure_ascii=False)}")
        l = raport.ogolem
        print(f"{nazwa:10} F1 {l.f1():.4f}  TP {l.tp} FP {l.fp} FN {l.fn}  zły typ {zle_typy}")
        if "--pola" in sys.argv:
            for pole, lp in sorted(raport.per_pole.items(), key=lambda kv: kv[1].f1())[:6]:
                if lp.f1() < 1:
                    print(f"    {pole:55} F1 {lp.f1():.3f}  TP {lp.tp} FP {lp.fp} FN {lp.fn}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
