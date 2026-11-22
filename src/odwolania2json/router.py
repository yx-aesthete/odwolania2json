"""Router pism: układ generatora UZP albo pismo prozą (kancelaria).

Przełącznik `router_prozy` w config/aplikacja.yaml (zmienna ROUTER_PROZY=0/1 nadpisuje); wyłączony = wynik jak bez
routera. Ustawienia (sygnały układu, progi, fragment, polecenie) są w YAML klasy, sekcja `router_prozy`.

- Wykrywacz: pismo jest „prozą”, gdy jest długie (`min_stron` stron albo `min_znakow` znaków) i nie ma żadnego
  stałego zdania szablonu generatora UZP (`uklad_uzp`). Pismo w układzie UZP idzie dalej regułami, bez zapytań.
- TED (pismo prozą, gdy pole puste): numer „RRRR/S NNN-NNNNNN” albo „NNNNNN-RRRR” przy słowie
  TED / Dzienniku Urzędowym / Dz.U. S / OJ S / numerze publikacji ogłoszenia, w początku pisma -> „NNNNNN-RRRR”.
- Czynność w piśmie prozą: JEDNO zapytanie do modelu z fragmentem petitum i pierwszych zarzutów oraz zdaniami
  z datami; lista zamknięta kodów; data musi stać w tekście. Odpowiedź spoza listy albo data spoza tekstu = brak
  (zostaje wynik reguł). `nadpisuj: true` = poprawna odpowiedź modelu zastępuje wynik reguł.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from .normalizacja import data_iso

ZNACZNIK_POLECENIA = "ZASKARŻONA CZYNNOŚĆ"   # atrapy w testach rozpoznają po nim to pytanie


def wlaczony(konf_aplikacji: Path) -> bool:
    """`router_prozy` w aplikacja.yaml (domyślnie wyłączony); ROUTER_PROZY=0/1 nadpisuje."""
    z_env = os.environ.get("ROUTER_PROZY")
    if z_env in ("0", "1"):
        return z_env == "1"
    import yaml
    konf = (yaml.safe_load(konf_aplikacji.read_text(encoding="utf-8")) or {}) if konf_aplikacji.exists() else {}
    return bool(konf.get("router_prozy", False))


_POLSKIE = str.maketrans("ąćęłńóśźż", "acelnoszz")


def szkielet(tekst: str) -> str:
    """Tekst odporny na typowe błędy OCR: małe litery bez polskich znaków, i/j/l/1/| jako „i”, same litery
    rozdzielone pojedynczą spacją (zdanie szablonu rozpoznane mimo „odwolania”, „korespondencii”, łamania linii)."""
    t = tekst.lower().translate(_POLSKIE)
    t = re.sub(r"[ijl1|!]", "i", t)
    return " " + re.sub(r"[^a-z]+", " ", t).strip() + " "


def czy_proza(tekst: str, strony: tuple[str, ...], spec: dict) -> tuple[bool, dict]:
    """(czy pismo prozą, sygnały do audytu)."""
    okno = tekst[: int(spec.get("okno", 30000))]
    sz = szkielet(okno)
    trafienia = [f for f in spec.get("uklad_uzp", []) if szkielet(f) in sz]
    dlugie = len(strony) >= int(spec.get("min_stron", 4)) or len(tekst) >= int(spec.get("min_znakow", 8000))
    return (dlugie and not trafienia), {"strony": len(strony), "znaki": len(tekst), "uklad_uzp": len(trafienia)}


# ---------- TED ----------

def numer_ted(tekst: str, spec: dict) -> str | None:
    """Pierwszy numer TED w początku pisma (okno `okno` znaków) w postaci NNNNNN-RRRR (cyfry jak w dokumencie)."""
    okno = tekst[: int(spec.get("okno", 15000))]
    najlepszy: tuple[int, str] | None = None
    wyklucz = spec.get("wyklucz_przed")   # numer innego postępowania („w postępowaniu prowadzonym przez inny podmiot”)
    for w in spec.get("wzorce", []):
        for m in re.finditer(w, okno, flags=re.I | re.S):
            if wyklucz and re.search(wyklucz, okno[max(0, m.start() - 250):m.start()], flags=re.I):
                continue
            if najlepszy is None or m.start() < najlepszy[0]:
                najlepszy = (m.start(), f"{m.group('nr')}-{m.group('rok')}")
            break
    return najlepszy[1] if najlepszy else None


# ---------- fragment dla modelu ----------

def fragment(tekst: str, spec: dict) -> str:
    """Petitum i pierwsze zarzuty (od pierwszego znacznika początku, z limitem) + zdania z datami czynności."""
    t = re.sub(r"[ \t]+", " ", tekst)
    start = None
    okno_startu = int(spec.get("okno_startu", 20000))
    for w in spec.get("od", []):
        m = re.search(w, t[:okno_startu], flags=re.I)
        if m and (start is None or m.start() < start):
            start = m.start()
    start = max(0, (start if start is not None else 0) - int(spec.get("przed", 300)))
    limit = int(spec.get("max_znakow", 3500))
    czesc = t[start:start + limit]
    for w in spec.get("do", []):   # koniec: uzasadnienie / dalsza część pisma (nie wcześniej niż po `min_znakow`)
        m = re.search(w, czesc[int(spec.get("min_znakow", 800)):], flags=re.I)
        if m:
            czesc = czesc[: int(spec.get("min_znakow", 800)) + m.start()]
    zdania = []
    wz_daty = spec.get("zdanie_daty")
    if wz_daty:
        for z in re.split(r"(?<=[.;])\s+", t):
            if len(zdania) >= int(spec.get("max_zdan", 8)):
                break
            if re.search(wz_daty, z, flags=re.I) and z.strip() and z.strip() not in czesc:
                zdania.append(z.strip()[:400])
    if zdania:
        czesc += "\n[...]\nZDANIA Z DATAMI Z DALSZEJ CZĘŚCI PISMA:\n" + "\n".join(zdania)
    return czesc


# ---------- odpowiedź modelu ----------

def _w_oknie(iso: str, data_pisma: str | None, max_dni: int | None) -> bool:
    """Dzień czynności nie później niż data pisma i najwyżej `max_dni` dni przed nią (termin na odwołanie liczy się
    w dniach, więc data ustawy, dawnego ogłoszenia albo terminu po piśmie to nie dzień zaskarżonej czynności)."""
    if not data_pisma or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data_pisma):
        return True
    from datetime import date
    try:
        roznica = (date.fromisoformat(data_pisma) - date.fromisoformat(iso)).days
    except ValueError:
        return False
    return roznica >= 0 and (max_dni is None or roznica <= max_dni)


def _data_z_odpowiedzi(odp: Any, tekst: str, data_pisma: str | None, max_dni: int | None = None) -> str | None:
    """Data dosłownie z tekstu (po ujednoliceniu białych znaków) -> ISO; bez roku: rok pisma (data nie późniejsza
    niż data pisma). Data, której nie ma w tekście, albo poza oknem `max_dni` przed datą pisma: None."""
    if not isinstance(odp, str) or not odp.strip():
        return None
    v = re.sub(r"\s+", " ", odp).strip().rstrip(".").strip()
    plaski = re.sub(r"\s+", " ", tekst)
    if not v or v.casefold() not in plaski.casefold():
        return None
    iso = data_iso(v)
    if iso:
        return iso if _w_oknie(iso, data_pisma, max_dni) else None
    if data_pisma and re.fullmatch(r"\d{4}-\d{2}-\d{2}", data_pisma):
        rok = int(data_pisma[:4])
        for r in (rok, rok - 1):
            iso = data_iso(f"{v} {r}")
            if iso and _w_oknie(iso, data_pisma, max_dni):
                return iso
    return None


def czynnosc_z_modelu(llm, tekst: str, spec: dict, powody: list[dict], data_pisma: str | None
                      ) -> tuple[dict | None, str | None, str]:
    """(pozycja słownika albo None, data ISO albo None, fragment wysłany do modelu)."""
    frag = fragment(tekst, spec.get("fragment", {}))
    polecenie = spec["polecenie"]
    odp = llm.zapytaj_json(polecenie, frag, max_tokens=int(spec.get("max_tokens", 200)))
    if odp is None:
        return None, None, frag
    from .arbitraz import json_z_odpowiedzi
    obj = json_z_odpowiedzi(odp)
    if not isinstance(obj, dict):
        return None, None, frag
    kod = obj.get("kod")
    try:
        kod = int(str(kod).strip()) if kod is not None and str(kod).strip().isdigit() else None
    except ValueError:
        kod = None
    poz = next((p for p in powody if p["id"] == kod), None)
    max_dni = spec.get("max_dni_przed_pismem")
    data = (_data_z_odpowiedzi(obj.get("data"), frag, data_pisma, int(max_dni) if max_dni is not None else None)
            if poz is not None else None)
    return poz, data, frag


def zastosuj(dane: Any, tekst: str, strony: tuple[str, ...], spec: dict, powody: list[dict], llm
             ) -> tuple[Any, dict]:
    """Nowe dane (kopia) i wpis audytu routera."""
    if not isinstance(dane, dict):
        return dane, {}
    dane = json.loads(json.dumps(dane, ensure_ascii=False))
    proza, sygnaly = czy_proza(tekst, strony, spec.get("wykrywacz", {}))
    audyt: dict = {"proza": proza, **sygnaly}
    zp = dane.get("ZamowieniePubliczne")
    # układ UZP bez zmian: TED i czynność routera tylko w piśmie prozą
    if proza and isinstance(zp, dict) and not zp.get("numer_ted") and spec.get("ted"):
        ted = numer_ted(tekst, spec["ted"])
        if ted:
            zp["numer_ted"] = ted
            audyt["numer_ted"] = ted
    kio = dane.get("OdwolanieKIO")
    cz = spec.get("czynnosc")
    if proza and llm is not None and cz and isinstance(kio, dict):
        poz, data, _ = czynnosc_z_modelu(llm, tekst, cz, powody, kio.get("data"))
        z_env = os.environ.get("ROUTER_NADPISUJ")   # pomiar wariantów: 1 = nadpisuj, 0 = tylko puste pola
        nadpisuj = (z_env == "1") if z_env in ("0", "1") else bool(cz.get("nadpisuj", True))
        audyt["model_czynnosc"] = {"kod": poz["id"] if poz else None, "data": data}
        if poz is not None and (nadpisuj or kio.get("czynnosc_powod_id") is None):
            kio["czynnosc_powod_id"] = poz["id"]
            kio["czynnosc_opis"] = poz["opis"]
        if data is not None and (nadpisuj or kio.get("czynnosc_dzien") is None):
            kio["czynnosc_dzien"] = data
    return dane, audyt
