"""Arbitraż szeroki model ↔ reguły (sekcja `model_szeroki` w YAML klasy, domyślnie wyłączona).

Model dostaje dokument i zwraca cały JSON pól miękkich (nazwy, osoby, tytuł, mail). Reguły są drugim kandydatem
i walidatorem. Na każdym polu z `pola`:
- kandydat modelu przechodzi tylko wtedy, gdy występuje w tekście:
  `doslownie` (nazwa, tytuł, mail): ten sam ciąg znaków, różnice tylko w białych znakach;
  `osoba` (imię i nazwisko): ta sama liczba wyrazów, każdy wyraz ma wspólny rdzeń z kolejnym wyrazem tekstu
  i różni się od niego tylko końcówką (np. „Cezary Zając” do „Cezaremu Zającowi”);
  `slownik` (np. typ): wartość z listy `dozwolone`;
- inaczej wygrywa reguła.
Pól spoza `pola` (identyfikatory, kwoty, daty, przelew) model nie zmienia: zostają z reguł.
Elementy list są dopasowywane po treści; model może dodać element tylko w liście z `dodawaj` i tylko taki,
którego pole kluczowe przeszło walidację (identyfikatory nowego elementu zostają puste).
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from typing import Any

from rapidfuzz import fuzz

from .normalizacja import mianownik
from .silnik import Dowod, znajdz_w_tekscie

_WYRAZ = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*")
MAX_KONCOWKA = 4      # ile liter końcówki może się różnić (Zającowi -> Zając, Dąbka -> Dąbek)
MIN_RDZEN = 3
PROG_DOPASOWANIA = 60.0


def _bez_bialych(t: str) -> str:
    return re.sub(r"\s+", "", t)


def doslownie_w_tekscie(wartosc: str, tekst: str) -> bool:
    w = _bez_bialych(wartosc)
    return bool(w) and w in _bez_bialych(tekst)


def _ten_sam_rdzen(a: str, b: str) -> bool:
    """Wyrazy różnią się tylko końcówką: wspólny początek >= MIN_RDZEN i reszta każdego <= MAX_KONCOWKA."""
    a, b = a.casefold(), b.casefold()
    if a == b:
        return True
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n >= MIN_RDZEN and len(a) - n <= MAX_KONCOWKA and len(b) - n <= MAX_KONCOWKA


def _czlony_zgodne(a: str, b: str) -> bool:
    ca, cb = a.split("-"), b.split("-")
    return len(ca) == len(cb) and all(_ten_sam_rdzen(x, y) for x, y in zip(ca, cb))


def osoba_w_tekscie(wartosc: str, tekst: str, formy_zalezne: str | None = None) -> tuple[int, int] | None:
    """Pozycja ciągu wyrazów tekstu zgodnego z wartością co do rdzeni (ta sama liczba wyrazów, ta sama kolejność
    albo odwrotna „Nazwisko Imię”). Nic nie dodaje i nie usuwa. Zmiana końcówek przechodzi tylko wtedy, gdy tuż
    przed nazwiskiem stoi słowo formy zależnej (`formy_zalezne`, np. „radcy prawnemu”, „Panu”); bez niego
    wartość musi być w tekście dosłownie (z dokładnością do wielkości liter)."""
    szukane = _WYRAZ.findall(wartosc)
    if not szukane or len(szukane) != len(wartosc.split()):
        return None
    wyrazy = list(_WYRAZ.finditer(tekst))
    n = len(szukane)
    for i in range(len(wyrazy) - n + 1):
        okno = wyrazy[i:i + n]
        teksty = [m.group(0) for m in okno]
        for kolejne in (teksty, teksty[::-1] if n == 2 else None):
            if kolejne is None or not all(_czlony_zgodne(s, t) for s, t in zip(szukane, kolejne)):
                continue
            od, do = okno[0].start(), okno[-1].end()
            if all(s.casefold() == t.casefold() for s, t in zip(szukane, kolejne)):
                return od, do
            przed = tekst[max(0, od - 80):od]
            if formy_zalezne and re.search(rf"(?:{formy_zalezne})\s*$", przed, flags=re.I):
                return od, do
    return None


_BEZ_ZNAKOW = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")


def _tylko_znaki(a: str, b: str) -> bool:
    return a != b and a.translate(_BEZ_ZNAKOW).casefold() == b.translate(_BEZ_ZNAKOW).casefold()


def _ogolna(sciezka: str) -> str:
    return re.sub(r"\[\d+\]", "[]", sciezka)


def _niepusty(obj: Any) -> bool:
    if isinstance(obj, dict):
        return any(_niepusty(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_niepusty(v) for v in obj)
    return obj not in (None, "")


def _pusty_jak(wzor: Any) -> Any:
    if isinstance(wzor, dict):
        return {k: _pusty_jak(v) for k, v in wzor.items()}
    if isinstance(wzor, list):
        return [_pusty_jak(wzor[0])] if wzor else []
    return None


@dataclass
class ArbitrazSzeroki:
    spec: dict
    dowody: list[Dowod] = field(default_factory=list)
    zmiany: int = 0

    @property
    def wlaczony(self) -> bool:
        return bool(self.spec.get("wlaczony"))

    def polecenie(self) -> str:
        return str(self.spec["polecenie"]).strip()

    def _rodzaj(self, sciezka: str) -> str | None:
        return (self.spec.get("pola") or {}).get(_ogolna(sciezka))

    def _lista(self, sciezka: str) -> dict:
        return (self.spec.get("listy") or {}).get(_ogolna(sciezka)) or {}

    def scal(self, z_regul: Any, z_modelu: Any, tekst: str) -> Any:
        if not isinstance(z_modelu, dict) or not isinstance(z_regul, dict):
            return z_regul
        return self._dict(z_regul, z_modelu, "", tekst)

    # --- węzły ---
    def _dict(self, regula: dict, model: Any, sciezka: str, tekst: str) -> dict:
        if not isinstance(model, dict):
            return copy.deepcopy(regula)
        wynik = {}
        for k, v in regula.items():
            p = f"{sciezka}.{k}" if sciezka else k
            wynik[k] = self._wezel(v, model.get(k), p, tekst) if k in model else copy.deepcopy(v)
        return wynik

    def _wezel(self, regula: Any, model: Any, sciezka: str, tekst: str) -> Any:
        if isinstance(regula, list):
            return self._lista_scal(regula, model, sciezka, tekst)
        if isinstance(regula, dict):
            return self._dict(regula, model, sciezka, tekst)
        return self._lisc(regula, model, sciezka, tekst)

    def _lisc(self, regula: Any, model: Any, sciezka: str, tekst: str) -> Any:
        rodzaj = self._rodzaj(sciezka)
        if rodzaj is None or model in (None, "") or isinstance(model, (dict, list)):
            return regula
        poz = self.sprawdz(rodzaj, model, tekst, sciezka)
        if poz is False or (regula is not None and _tylko_znaki(str(regula), str(model))):
            return regula   # odrzucony albo różni się od reguły tylko polskimi znakami (Jeleń -> Jelen)
        if (rodzaj == "osoba" and regula not in (None, "") and osoba_w_tekscie(str(regula), tekst)
                and mianownik(str(regula)) == str(regula) and not osoba_w_tekscie(str(model), tekst)):
            # reguła stoi w tekście dosłownie, model tylko po zmianie końcówek: forma bywa dwuznaczna
            # („Radcy Prawnego Aleksandra Rybak”), a mianownik w tekście wygrywa (Z22 pkt 3)
            return regula
        wartosc = str(model).strip() if rodzaj != "slownik" else model
        if wartosc != regula:
            self.zmiany += 1
            cytat = tekst[poz[0]:poz[1]] if isinstance(poz, tuple) else None
            self.dowody.append(Dowod(sciezka, wartosc, "model#szeroki", cytat, poz[0] if isinstance(poz, tuple) else None))
        return wartosc

    def sprawdz(self, rodzaj: str, wartosc: Any, tekst: str, sciezka: str = "") -> tuple[int, int] | bool:
        """Pozycja w tekście (albo True dla słownika), gdy kandydat modelu przechodzi; False, gdy nie."""
        if rodzaj == "slownik":
            dozwolone = (self.spec.get("dozwolone") or {}).get(_ogolna(sciezka)) or []
            return wartosc in dozwolone
        s = str(wartosc).strip()
        if not s:
            return False
        if rodzaj == "osoba":
            return osoba_w_tekscie(s, tekst, self.spec.get("formy_zalezne")) or False
        if doslownie_w_tekscie(s, tekst):
            return znajdz_w_tekscie(s, tekst, prog=100.0) or True
        return False

    # --- listy ---
    def _klucz_elementu(self, el: Any, sciezka: str) -> str:
        """Tekst elementu do dopasowania: wartości pól miękkich (wg `pola`) w elemencie."""
        czesci: list[str] = []

        def zbierz(o: Any, p: str) -> None:
            if isinstance(o, dict):
                for k, v in o.items():
                    zbierz(v, f"{p}.{k}")
            elif isinstance(o, list):
                for x in o:
                    zbierz(x, f"{p}[]")
            elif o not in (None, "") and self._rodzaj(p) in ("osoba", "doslownie"):
                czesci.append(str(o))
        zbierz(el, f"{sciezka}[]")
        return " ".join(czesci).casefold()

    def _lista_scal(self, regula: list, model: Any, sciezka: str, tekst: str) -> list:
        if not isinstance(model, list) or not model:
            return copy.deepcopy(regula)
        ust = self._lista(sciezka)
        wolne = [i for i, r in enumerate(regula) if _niepusty(r)]
        przypisane: dict[int, Any] = {}
        dodane: list[Any] = []
        for m in model:
            if not _niepusty(m):
                continue
            km = self._klucz_elementu(m, sciezka)
            najlepszy, wynik_najl = None, 0.0
            for i in wolne:
                kr = self._klucz_elementu(regula[i], sciezka)
                s = fuzz.token_set_ratio(km, kr) if km and kr else 0.0
                if s > wynik_najl:
                    najlepszy, wynik_najl = i, s
            if najlepszy is None and len(wolne) == 1 and len(model) == 1:
                najlepszy, wynik_najl = wolne[0], PROG_DOPASOWANIA   # jeden element po obu stronach
            if najlepszy is not None and wynik_najl >= PROG_DOPASOWANIA:
                wolne.remove(najlepszy)
                przypisane[najlepszy] = self._wezel(regula[najlepszy], m, f"{sciezka}[{najlepszy}]", tekst)
            elif ust.get("dodawaj") and regula:
                nowy = self._nowy_element(regula[0], m, f"{sciezka}[{len(regula) + len(dodane)}]", tekst,
                                          ust.get("klucz"))
                if nowy is not None:
                    dodane.append(nowy)
        if ust.get("zastepuj") and (przypisane or dodane):
            # lista modelu w całości (elementy po walidacji); elementy tylko z reguł odpadają
            wynik = [przypisane[i] for i in sorted(przypisane)] + dodane
        else:
            wynik = [przypisane.get(i, copy.deepcopy(r)) for i, r in enumerate(regula)]
            if dodane:
                wynik = [w for w in wynik if _niepusty(w)] + dodane
        if ust.get("identyfikatory"):
            wynik = self._identyfikatory(wynik, ust, tekst)
        return wynik or copy.deepcopy(regula)

    def _identyfikatory(self, lista: list, ust: dict, tekst: str) -> list:
        """Brakujące identyfikatory elementu regułą (regex z YAML) w tekście tuż za jego polem kluczowym, do
        pola kluczowego następnego elementu. Model wskazuje tylko miejsce; wartość daje reguła."""
        klucz = ust.get("klucz")
        if not klucz:
            return lista

        def pobierz(el: Any, sc: str) -> Any:
            for k in sc.split("."):
                el = el.get(k) if isinstance(el, dict) else None
            return el

        pozycje = []
        for el in lista:
            v = pobierz(el, klucz)
            poz = znajdz_w_tekscie(v, tekst, prog=100.0) if isinstance(v, str) and v else None
            pozycje.append(poz[0] if poz else -1)
        zajete = {str(pobierz(el, sc)) for el in lista for sc in ust["identyfikatory"] if pobierz(el, sc)}
        okno = int(ust.get("okno", 300))
        wynik = []
        for n, el in enumerate(lista):
            el = copy.deepcopy(el)
            od = pozycje[n]
            if od >= 0:
                nastepne = [p for p in pozycje if p > od]
                do = min([od + okno] + nastepne)
                fragment = tekst[od:do]
                for sc, wzor in ust["identyfikatory"].items():
                    if pobierz(el, sc) not in (None, ""):
                        continue
                    m = re.search(wzor, fragment)
                    if not m:
                        continue
                    v = re.sub(r"\D", "", m.group("v"))
                    if v in zajete:
                        continue
                    cel = el
                    *droga, ostatni = sc.split(".")
                    for k in droga:
                        cel = cel.get(k) if isinstance(cel, dict) else None
                    if isinstance(cel, dict) and ostatni in cel:
                        cel[ostatni] = v
                        zajete.add(v)
                        self.dowody.append(Dowod(sc, v, "regex#kotwica_modelu", m.group(0), od + m.start()))
            wynik.append(el)
        return wynik

    def _nowy_element(self, wzor: Any, model: Any, sciezka: str, tekst: str, klucz: str | None) -> Any:
        """Element spoza reguł: tylko gdy pole kluczowe (np. `data.nazwa`) przeszło walidację."""
        pusty = _pusty_jak(wzor)
        przed = self.zmiany
        nowy = self._wezel(pusty, model, sciezka, tekst)
        if self.zmiany == przed:
            return None
        if klucz:
            wartosc: Any = nowy
            for k in klucz.split("."):
                wartosc = wartosc.get(k) if isinstance(wartosc, dict) else None
            if wartosc in (None, ""):
                return None
        return nowy
