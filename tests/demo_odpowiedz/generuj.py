"""Generator 3 przykładów klasy opisowej `odpowiedz_na_odwolanie` (config/klasy-demo/odpowiedz_na_odwolanie.yaml).

Dane fikcyjne: NIP i KRS z prefiksem 999 (NIP z poprawną sumą kontrolną), sygnatury KIO 999x/26, nazwy wymyślone.
Trzy różne układy: klasyczny, z tabelką stron i bez polskich znaków w tytule. Wynik (PDF + JSON) jest w repo.

    CHROME=/sciezka/chrome-headless-shell python tests/demo_odpowiedz/generuj.py
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

TU = Path(__file__).resolve().parent
CHROME = os.environ.get("CHROME", "chrome-headless-shell")
CSS = """body { font-family: 'Times New Roman', Times, serif; font-size: 11.5pt; line-height: 1.4; color: #111; }
h1 { font-size: 15pt; text-align: center; margin: 18px 0 4px; } p { margin: 6px 0; text-align: justify; }
.prawo { text-align: right; } td { padding: 3px 8px; vertical-align: top; } .podpis { margin-top: 40px; }"""


def nip(baza: str) -> str:
    d = [int(c) for c in baza]
    return baza + str(sum(a * b for a, b in zip(d, [6, 5, 7, 2, 3, 4, 5, 6, 7])) % 11)


SPRAWY = [
    dict(case="case01", plik="odpowiedz_na_odwolanie_nr_1", sygn="KIO 9991/26", data_txt="Warszawa, dnia 12 października 2026 r.",
         data="2026-10-12", zam="Gmina Miasto Zielonka Dolna", nip=nip("999104512"), odw="Budimex-Fikcja Konstrukcje sp. z o.o.",
         osoba="Agnieszka Wróblewska", wniosek="oddalenie", uklad="klasyczny"),
    dict(case="case02", plik="odpowiedz_na_odwolanie_nr_2", sygn="KIO 9992/26", data_txt="Kraków, 03.11.2026 r.",
         data="2026-11-03", zam="Szpital Wojewódzki im. Jana Kowalskiego w Krakowie", nip=nip("999220873"),
         odw="Konsorcjum MedTech-Fikcja S.A.", osoba="Tomasz Zielonka", wniosek="odrzucenie", uklad="tabela"),
    dict(case="case03", plik="odpowiedz_na_odwolanie_nr_3", sygn="KIO 9993/26", data_txt="Poznań, 2026-11-15",
         data="2026-11-15", zam="Zarząd Dróg Powiatowych w Lesznie Wymyślonym", nip=nip("999371046"),
         odw="Drogbud Fikcyjny Jan Nowakowski", osoba="Katarzyna Lis", wniosek="oddalenie", uklad="bez_ogonkow"),
]

WNIOSEK = {"oddalenie": "oddalenie odwołania w całości", "odrzucenie": "odrzucenie odwołania"}


def html(s: dict) -> str:
    strony = (f"<table><tr><td>Zamawiający:</td><td>{s['zam']}<br>NIP: {s['nip']}</td></tr>"
              f"<tr><td>Odwołujący:</td><td>{s['odw']}</td></tr></table>") if s["uklad"] == "tabela" else (
        f"<p><b>Zamawiający:</b> {s['zam']}, NIP {s['nip'][:3]}-{s['nip'][3:6]}-{s['nip'][6:8]}-{s['nip'][8:]}</p>"
        f"<p><b>Odwołujący:</b> {s['odw']}</p>")
    tytul = "ODPOWIEDZ NA ODWOLANIE" if s["uklad"] == "bez_ogonkow" else "ODPOWIEDŹ NA ODWOŁANIE"
    tresc = (
        f"<p class=prawo>{s['data_txt']}</p>"
        "<p>Krajowa Izba Odwoławcza<br>ul. Postępu 17a, 02-676 Warszawa</p>"
        f"<p>Sygn. akt: {s['sygn']}</p>{strony}"
        f"<h1>{tytul}</h1>"
        f"<p>Działając w imieniu Zamawiającego, w odpowiedzi na odwołanie wniesione przez {s['odw']} "
        f"w postępowaniu o udzielenie zamówienia publicznego, Zamawiający wnosi o {WNIOSEK[s['wniosek']]} "
        "oraz obciążenie Odwołującego kosztami postępowania odwoławczego.</p>"
        "<p><b>Uzasadnienie</b></p>"
        "<p>Zarzuty odwołania są niezasadne. Zamawiający dokonał badania i oceny ofert zgodnie z przepisami "
        "ustawy Prawo zamówień publicznych, a dokumenty złożone przez wykonawców zostały zweryfikowane "
        "z należytą starannością. Odwołujący nie wykazał, aby czynność Zamawiającego naruszała jego interes.</p>"
        f"<p class=podpis>W imieniu Zamawiającego:<br>{s['osoba']}<br>radca prawny</p>")
    return f"<!doctype html><html lang=pl><head><meta charset=utf-8><style>{CSS}</style></head><body>{tresc}</body></html>"


def referencja(s: dict) -> dict:
    return {"OdpowiedzNaOdwolanie": {"sygnatura": s["sygn"], "data": s["data"], "wniosek": s["wniosek"]},
            "Zamawiajacy": {"nazwa": s["zam"], "nip": s["nip"]},
            "Odwolujacy": {"nazwa": s["odw"]}, "pelnomocnik": s["osoba"]}


def main() -> None:
    for s in SPRAWY:
        pdf = TU / "input" / s["case"] / f"{s['plik']}.pdf"
        ref = TU / "oczekiwane" / s["case"] / f"{s['plik']}.json"
        pdf.parent.mkdir(parents=True, exist_ok=True)
        ref.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            h = Path(tmp) / "d.html"
            h.write_text(html(s), encoding="utf-8")
            subprocess.run([CHROME, "--headless", "--no-pdf-header-footer", "--disable-gpu",
                            f"--print-to-pdf={pdf}", h.as_uri()], check=True, capture_output=True)
        ref.write_text(json.dumps(referencja(s), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(pdf.relative_to(TU))


if __name__ == "__main__":
    main()
