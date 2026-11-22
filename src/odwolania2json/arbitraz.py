"""Arbitraż model ↔ reguły dla całego dokumentu (sekcja `model_dokumentu` w YAML klasy).

Model dostaje tekst dokumentu i zwraca JSON w formacie wyniku. Każda wartość z modelu jest sprawdzana w tekście:
- osoby (`imie_nazwisko`): rdzeń każdego członu występuje w tekście (mianownik „Cezary Zając” pasuje do „Cezarego Zająca”);
- nazwy: podobieństwo >= 0,85 do fragmentu tekstu;
- identyfikatory (cyfry): dokładnie w tekście (po zdjęciu spacji i kresek);
- wartości słownikowe (np. typ): z listy dozwolonych w YAML.
Wartość odrzucona przez walidator wraca do reguł (ta sama ścieżka). Listy z modelu zastępują listy z reguł tylko,
gdy model nie zgubił elementów. Pola spoza `pola` zostają z reguł.
"""
from __future__ import annotations

import copy
import os
import json
import re
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz

from .normalizacja import mianownik
from .silnik import Dowod, znajdz_w_tekscie


def _zwarte(t: str) -> str:
    return re.sub(r"[\s\-–]+", "", t).casefold()


def _rdzen_w_tekscie(wartosc: str, tekst: str) -> tuple[int, int] | None:
    """Każdy człon (>= 3 litery) ma rdzeń (bez 3 ostatnich liter, min. 3) w tekście; zwraca pozycję pierwszego."""
    tekst_cf = tekst.casefold()
    czlony = [c for c in re.split(r"[\s\-]+", wartosc) if len(c) >= 3]
    if not czlony:
        return None
    pozycje = []
    for c in czlony:
        rdzen = c[: max(3, len(c) - 3)].casefold()
        i = tekst_cf.find(rdzen)
        if i < 0:
            return None
        pozycje.append(i)
    od = min(pozycje)
    koniec = tekst.find("\n", od)
    return od, (koniec if koniec > 0 else min(len(tekst), od + 120))


def sprawdz(rodzaj: str, wartosc: Any, tekst: str, dozwolone: list | None = None) -> tuple[bool, tuple[int, int] | None]:
    if wartosc is None or wartosc == "":
        return False, None
    if rodzaj == "slownik":
        return (wartosc in (dozwolone or [])), None
    s = str(wartosc)
    if rodzaj == "cyfry":
        cyfry = re.sub(r"\D", "", s)
        if not cyfry:
            return False, None
        i = re.sub(r"[\s\-–]", "", tekst).find(cyfry)
        return i >= 0, None
    if rodzaj == "osoba":
        poz = _rdzen_w_tekscie(s, tekst)
        return poz is not None, poz
    poz = znajdz_w_tekscie(s, tekst, prog=85.0)  # nazwa
    return poz is not None, poz


@dataclass
class Arbitraz:
    spec: dict
    dowody: list[Dowod] = field(default_factory=list)
    odrzucone: int = 0

    @property
    def wlaczony(self) -> bool:
        """Flaga `wlaczony` w YAML; zmienna MODEL_ARBITRAZ=1/0 ją nadpisuje (pomiary bez edycji plików)."""
        z_env = os.environ.get("MODEL_ARBITRAZ")
        if z_env in ("0", "1"):
            return z_env == "1" and bool(self.spec)
        return bool(self.spec.get("wlaczony"))

    def polecenie(self) -> str:
        return str(self.spec["polecenie"]).strip()

    def scal(self, z_regul: Any, z_modelu: Any, tekst: str) -> Any:
        """Wynik z reguł poprawiony wartościami z modelu, które przeszły walidację."""
        if not isinstance(z_modelu, dict) or not isinstance(z_regul, dict):
            return z_regul
        wynik = copy.deepcopy(z_regul)
        for klucz, wartosc in z_modelu.items():
            if klucz in wynik:
                wynik[klucz] = self._scal_wezel(wynik[klucz], wartosc, klucz, tekst)
        return wynik

    def _rodzaj(self, sciezka: str) -> str | None:
        ogolna = re.sub(r"\[\d+\]", "[]", sciezka)
        return (self.spec.get("pola") or {}).get(ogolna)

    @staticmethod
    def _regula_pewniejsza(rodzaj: str, regula: Any, model: Any, tekst: str) -> bool:
        """Reguła zostaje, gdy jej wartość stoi dosłownie w dokumencie (np. imię w mianowniku: model nie ma czego
        poprawiać, a bywa, że zmienia płeć imienia) albo gdy model różni się tylko polskimi znakami."""
        if regula is None or rodzaj not in ("osoba", "nazwa"):
            return False
        r, m = str(regula), str(model)
        if _bez_znakow(r) == _bez_znakow(m) and r != m:
            return True
        if rodzaj == "osoba" and not _tylko_koncowki(r, m):
            return True  # model może zmienić tylko końcówki wyrazów z reguły, nie rdzeń ani liczbę wyrazów
        if not _dosłownie_w_tekscie(r, tekst):
            return False
        # osoba: dosłownie w tekście i już w mianowniku wg reguł odmiany („Cezaremu Zającowi” nie jest)
        return rodzaj == "nazwa" or mianownik(r) == r

    def _scal_wezel(self, regula: Any, model: Any, sciezka: str, tekst: str) -> Any:
        if isinstance(regula, list):
            if not isinstance(model, list) or len(model) < len([r for r in regula if _niepusty(r)]):
                return regula  # model zgubił elementy listy: zostają reguły
            odrzucone_przed, dowody_przed = self.odrzucone, len(self.dowody)
            wynik = []
            for i, m in enumerate(model):
                r = regula[i] if i < len(regula) else _pusty_jak(regula[0] if regula else m)
                wynik.append(self._scal_wezel(r, m, f"{sciezka}[{i}]", tekst))
            if self.odrzucone > odrzucone_przed:  # lista z modelu w całości albo wcale
                del self.dowody[dowody_przed:]
                return regula
            return [w for w in wynik if _niepusty(w)] or regula
        if isinstance(regula, dict):
            if not isinstance(model, dict):
                return regula
            return {k: (self._scal_wezel(v, model.get(k), f"{sciezka}.{k}", tekst) if k in model else v)
                    for k, v in regula.items()}
        rodzaj = self._rodzaj(sciezka)
        if rodzaj is None:
            return regula
        dozwolone = (self.spec.get("dozwolone") or {}).get(re.sub(r"\[\d+\]", "[]", sciezka))
        ok, poz = sprawdz(rodzaj, model, tekst, dozwolone)
        if not ok:
            if model not in (None, "") or regula is not None:
                self.odrzucone += 1  # model nie podał wartości albo ta nie przeszła walidacji
            return regula
        if self._regula_pewniejsza(rodzaj, regula, model, tekst):
            return regula
        wartosc = re.sub(r"\D", "", str(model)) if rodzaj == "cyfry" else model
        if wartosc != regula:
            cytat = tekst[poz[0]:poz[1]] if poz else None
            self.dowody.append(Dowod(sciezka, wartosc, "model#dokument", cytat, poz[0] if poz else None))
        return wartosc


_BEZ_ZNAKOW = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def _tylko_koncowki(regula: str, model: str) -> bool:
    """Ta sama liczba wyrazów, a każdy wyraz modelu ma wspólny rdzeń (min. 3 litery) z wyrazem reguły."""
    wr, wm = re.split(r"[\s\-]+", regula.strip()), re.split(r"[\s\-]+", model.strip())
    if len(wr) != len(wm):
        return False
    for a, b in zip(wr, wm):
        n = max(3, min(len(a), len(b)) - 3)
        if a[:n].casefold() != b[:n].casefold():
            return False
    return True


def _dosłownie_w_tekscie(wartosc: str, tekst: str) -> bool:
    return bool(wartosc) and _zwarte(wartosc) in _zwarte(tekst)


def _bez_znakow(t: str) -> str:
    return t.translate(_BEZ_ZNAKOW).casefold()


def _niepusty(obj: Any) -> bool:
    if isinstance(obj, dict):
        return any(_niepusty(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_niepusty(v) for v in obj)
    return obj is not None


def _pusty_jak(wzor: Any) -> Any:
    if isinstance(wzor, dict):
        return {k: _pusty_jak(v) for k, v in wzor.items()}
    if isinstance(wzor, list):
        return [_pusty_jak(wzor[0])] if wzor else []
    return None


def json_z_odpowiedzi(odp: str | None) -> Any:
    if not odp:
        return None
    t = re.sub(r"<think>.*?</think>", "", odp, flags=re.S)
    m = re.search(r"\{.*\}", t, flags=re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
