"""Klasa opisowa: nowy typ dokumentu opisany w YAML samymi słowami, bez wyrażeń regularnych.

    nazwa: odpowiedz_na_odwolanie
    opis: Odpowiedź zamawiającego na odwołanie do KIO
    rozpoznanie:
      tytul: [odpowiedź na odwołanie]            # frazy tytułu (zwykły tekst)
      slowa: [wnosi o oddalenie odwołania]       # frazy z treści
    pola:
      OdpowiedzNaOdwolanie:
        sygnatura: sygnatura akt sprawy, np. KIO 1234/26
        data: {opis: data pisma, typ: data}
        wniosek: {opis: czego żąda zamawiający, wybor: [oddalenie, odrzucenie, umorzenie]}

Rozpoznanie: frazy z list zamieniają się na wzorce (dowolne białe znaki, litery z ogonkami i bez, tytuł bez spacji).
Ekstrakcja: jedno pytanie do modelu z opisami pól; każda wartość przechodzi walidację, że występuje w tekście
(tekst: podobieństwo >= 0,85, cyfry: dokładnie, osoba: rdzenie członów, data i kwota: zapis z dokumentu),
a wartość z `wybor` musi być z listy. Odrzucona wartość = null. Bez modelu wszystkie pola są null.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .arbitraz import json_z_odpowiedzi, sprawdz
from .normalizacja import DATA_WZORCE, data_iso, jedna_linia, kwota
from .silnik import Dowod, Wynik, znajdz_w_tekscie

# Wagi fraz podanych listą (słownik `wzorzec: waga` działa jak dotąd).
WAGI_FRAZ = {"tytul": 5.0, "slowa": 2.0, "ujemne": 3.0, "tytul_ujemne": 6.0}
PROG_FRAZ = 5.0
TYPY = ("tekst", "osoba", "cyfry", "data", "kwota")
_OGONKI = {"ą": "a", "ć": "c", "ę": "e", "ł": "l", "ń": "n", "ó": "o", "ś": "s", "ź": "z", "ż": "z"}


def czy_opisowa(spec: dict) -> bool:
    return "pola" in spec and "wynik" not in spec


def wzorzec_frazy(fraza: str, tytul: bool = False) -> str:
    """Fraza zwykłym tekstem -> wzorzec: słowa dosłownie, między nimi dowolne białe znaki (w tytule: brak spacji,
    bo strefa tytułu jest zwarta), polska litera pasuje też bez ogonka (PDF bez polskich znaków)."""
    def slowo(s: str) -> str:
        return "".join(f"[{z}{_OGONKI[z]}]" if z in _OGONKI else re.escape(z) for z in s.lower())
    return ("" if tytul else r"\s+").join(slowo(s) for s in fraza.split())


def rozpoznanie_z_fraz(rozp: dict) -> dict:
    """Listy fraz w `rozpoznanie` -> słowniki wzorców z domyślnymi wagami; słowniki zostają bez zmian."""
    wynik = dict(rozp)
    for klucz, waga in WAGI_FRAZ.items():
        if isinstance(rozp.get(klucz), list):
            wynik[klucz] = {wzorzec_frazy(str(f), klucz.startswith("tytul")): waga for f in rozp[klucz]}
    if any(isinstance(rozp.get(k), list) for k in WAGI_FRAZ):
        wynik.setdefault("prog", PROG_FRAZ)
    return wynik


@dataclass(frozen=True)
class Pole:
    sciezka: tuple[str, ...]
    opis: str
    typ: str = "tekst"
    wybor: tuple[str, ...] = ()


def _czy_lisc(v: Any) -> bool:
    return isinstance(v, str) or (isinstance(v, dict) and "opis" in v)


def pola(spec: dict, prefiks: tuple[str, ...] = ()) -> list[Pole]:
    wynik: list[Pole] = []
    for nazwa, v in spec.items():
        sciezka = (*prefiks, str(nazwa))
        if isinstance(v, str):
            wynik.append(Pole(sciezka, v))
        elif _czy_lisc(v):
            typ = str(v.get("typ", "tekst"))
            if typ not in TYPY:
                raise ValueError(f"pole {'.'.join(sciezka)}: nieznany typ {typ!r} (dozwolone: {', '.join(TYPY)})")
            wynik.append(Pole(sciezka, str(v["opis"]), typ, tuple(str(w) for w in v.get("wybor") or ())))
        elif isinstance(v, dict):
            wynik.extend(pola(v, sciezka))
        else:
            raise ValueError(f"pole {'.'.join(sciezka)}: podaj opis (tekst) albo {{opis, typ}}")
    return wynik


def _szablon(spec: dict) -> dict:
    return {k: (None if _czy_lisc(v) else _szablon(v)) for k, v in spec.items()}


def polecenie(spec: dict) -> str:
    opisy = "\n".join(
        f"- {'.'.join(p.sciezka)}: {p.opis}"
        + (f" (jedna z wartości: {', '.join(p.wybor)})" if p.wybor else "")
        + (" (zapis dosłownie jak w dokumencie)" if p.typ in ("data", "kwota") else "")
        for p in pola(spec["pola"]))
    return (f"Dokument: {spec.get('opis', spec.get('nazwa', ''))}.\n"
            f"Wypisz dane jako JSON dokładnie w tym formacie:\n{json.dumps(_szablon(spec['pola']), ensure_ascii=False)}\n"
            f"Opis pól:\n{opisy}\n"
            "Wartości przepisuj dosłownie z dokumentu. Brakujące: null.")


def _wez(obj: Any, sciezka: tuple[str, ...]) -> Any:
    for k in sciezka:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(k)
    return obj


def _data(v: str, tekst: str) -> tuple[str | None, tuple[int, int] | None]:
    """Data zapisana tak jak w dokumencie albo (gdy model ją przeliczył) data w tekście o tej samej wartości."""
    poz = znajdz_w_tekscie(v, tekst)
    if poz is not None:
        return data_iso(tekst[poz[0]:poz[1]]) or data_iso(v), poz
    iso = data_iso(v)
    for wz in DATA_WZORCE:
        for m in wz.finditer(tekst):
            if iso and data_iso(m.group(0)) == iso:
                return iso, (m.start(), m.end())
    return None, None


def sprawdz_pole(pole: Pole, wartosc: Any, tekst: str) -> tuple[Any, tuple[int, int] | None]:
    """Wartość po walidacji (albo None) i jej pozycja w tekście."""
    if wartosc is None or isinstance(wartosc, (dict, list)) or str(wartosc).strip() == "":
        return None, None
    v = str(wartosc).strip()
    if pole.wybor:
        trafione = next((w for w in pole.wybor if w.casefold() == v.casefold()), None)
        return trafione, None
    if pole.typ == "data":
        return _data(v, tekst)
    if pole.typ == "kwota":
        poz = znajdz_w_tekscie(v, tekst)
        return (kwota(v), poz) if poz is not None else (None, None)
    if pole.typ == "cyfry":
        ok, _ = sprawdz("cyfry", v, tekst)
        return (re.sub(r"\D", "", v), None) if ok else (None, None)
    ok, poz = sprawdz("osoba" if pole.typ == "osoba" else "nazwa", v, tekst)
    return (jedna_linia(v), poz) if ok else (None, None)


def _wstaw(spec: dict, prefiks: tuple[str, ...], wartosci: dict) -> dict:
    return {k: (wartosci.get((*prefiks, k)) if _czy_lisc(v) else _wstaw(v, (*prefiks, k), wartosci))
            for k, v in spec.items()}


def ekstrahuj(spec: dict, tekst: str, llm: Any) -> Wynik:
    """Jedno pytanie do modelu z opisami pól, potem walidacja każdej wartości w tekście dokumentu."""
    if llm is None:
        return Wynik(_szablon(spec["pola"]), [])
    tekst_modelu = tekst[: int(spec.get("max_znakow", 12000))]
    odp = json_z_odpowiedzi(llm.zapytaj_json(polecenie(spec), tekst_modelu))
    wartosci: dict[tuple[str, ...], Any] = {}
    dowody: list[Dowod] = []
    for p in pola(spec["pola"]):
        v, poz = sprawdz_pole(p, _wez(odp, p.sciezka), tekst)
        if v is None:
            continue
        wartosci[p.sciezka] = v
        dowody.append(Dowod(".".join(p.sciezka), v, "model#opis", tekst[poz[0]:poz[1]] if poz else None,
                            poz[0] if poz else None))
    return Wynik(_wstaw(spec["pola"], (), wartosci), dowody)
