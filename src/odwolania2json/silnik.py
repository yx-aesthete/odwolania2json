"""Silnik ekstrakcji: wykonuje specyfikację klasy z YAML na tekście dokumentu.

Kod zna tylko ogólne klocki (sekcja, regex, etykieta, słownik, warunek, lista, normalizatory).
Co wyciągnąć i skąd, mówi wyłącznie plik `config/klasy/<klasa>.yaml`.

Specyfikacja liścia (pola):
    metody: [ {regex|etykieta|slownik|jesli|stala|llm: ..., w: <sekcja>}, ... ]  # pierwsza niepusta wygrywa
    normalizuj: [nazwa, ...]
    typ: str|int|float
Lista:      {lista: {sekcja: <nazwa>} | {regex: ..., rozdziel: ...}, element: {...}, max: N}
Obiekt:     zwykły słownik pól.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .normalizacja import zastosuj


_DATY_W_TEKSCIE = re.compile(
    r"\d{1,2}[-./]\d{1,2}[-./]\d{2,4}(?!\d)|\d{4}[-./]\d{1,2}[-./]\d{1,2}(?!\d)"
    r"|\d{1,2}[ \t]+(?:stycz|lut|marc|kwie|maj|czerw|lip|sierp|wrze|pa[źz]dz|listop|grud)\w*[ \t]+\d{4}", re.I)


def _bez_pl(v: Any) -> Any:
    """Klucz porównania odpowiedzi modelu z kandydatem z dokumentu: rachunek z PL i bez PL to ten sam numer
    (Z44: wartością zostaje zapis z dokumentu, z PL, gdy tam stoi; model może podać numer bez PL)."""
    return re.sub(r"^PL(?=\d{26}$)", "", v) if isinstance(v, str) else v


FLAGI = {"i": re.I, "s": re.S, "m": re.M, "x": re.X}


@dataclass(frozen=True)
class Kontekst:
    tekst: str          # tekst, w którym szukamy
    przesuniecie: int   # pozycja początku `tekst` w pełnym tekście dokumentu
    indeks: int | None = None  # numer elementu listy (do sekcji parowanych `indeks: true`)


@dataclass
class Dowod:
    pole: str
    wartosc: Any
    metoda: str
    cytat: str | None
    pozycja: int | None
    strona: int | None = None


@dataclass
class Wynik:
    dane: Any
    dowody: list[Dowod] = field(default_factory=list)


def _kompiluj(wzorzec: str, flagi: str | list[str] | None = None) -> re.Pattern:
    f = 0
    for z in (flagi or "i"):
        f |= FLAGI[z]
    return re.compile(wzorzec, f)


def _bez_bialych(t: str) -> tuple[str, list[int]]:
    """Tekst bez różnic w białych znakach i wielkości liter + mapa pozycji do oryginału."""
    znaki, mapa, spacja = [], [], False
    for i, z in enumerate(t):
        if z.isspace():
            if not spacja and znaki:
                znaki.append(" "); mapa.append(i)
            spacja = True
            continue
        spacja = False
        znaki.append(z.casefold()); mapa.append(i)
    return "".join(znaki).rstrip(), mapa


def znajdz_w_tekscie(wartosc: str, tekst: str, prog: float = 92.0) -> tuple[int, int] | None:
    """Pozycja (od, do) wartości w tekście: dosłownie (bez różnic w spacjach i wielkości liter),
    a gdy nie ma, najbliższy fragment z podobieństwem >= prog (OCR, łamanie linii)."""
    w, _ = _bez_bialych(wartosc)
    if not w:
        return None
    t, mapa = _bez_bialych(tekst)
    i = t.find(w)
    if i >= 0:
        return mapa[i], mapa[i + len(w) - 1] + 1
    if len(w) < 8:
        return None
    from rapidfuzz import fuzz
    al = fuzz.partial_ratio_alignment(w, t)
    if al is None or al.score < prog or al.dest_end <= al.dest_start:
        return None
    return mapa[al.dest_start], mapa[al.dest_end - 1] + 1


def _wartosc_dopasowania(m: re.Match) -> tuple[str, int]:
    if "v" in m.re.groupindex and m.group("v") is not None:
        return m.group("v"), m.start("v")
    if m.re.groups and m.group(1) is not None:
        return m.group(1), m.start(1)
    return m.group(0), m.start()


class Silnik:
    def __init__(self, klasa: dict, llm: Callable[[str, str], str | None] | None = None, siatka: bool = True):
        self.klasa = klasa
        self.siatka = siatka   # False: metody z `siatka: true` są pomijane (przełącznik `siatka_modelu`)
        self.sekcje: dict[str, dict] = klasa.get("sekcje", {}) or {}
        self.slowniki: dict[str, list[dict]] = klasa.get("slowniki", {}) or {}
        self.llm = llm
        self._pelny = Kontekst("", 0)

    # ---------- sekcje ----------
    def sekcja(self, nazwa: str, ktx: Kontekst) -> list[Kontekst]:
        """Wszystkie wystąpienia sekcji w kontekście (sekcja może leżeć w innej: `w`)."""
        spec = self.sekcje.get(nazwa)
        if spec is None:
            raise ValueError(f"nieznana sekcja: {nazwa}")
        if spec.get("globalna"):  # zawsze w całym dokumencie, także z wnętrza elementu listy
            ktx = self._pelny
        rodzice = self.sekcja(spec["w"], ktx) if spec.get("w") else [ktx]
        wynik: list[Kontekst] = []
        if spec.get("llm") and self.llm is not None and not any(
                _kompiluj(spec["od"], spec.get("flagi")).search(r.tekst) for r in rodzice):
            return self._sekcja_z_modelu(spec, rodzice)
        for r in rodzice:
            od = _kompiluj(spec["od"], spec.get("flagi"))
            koniec = [_kompiluj(d, spec.get("flagi")) for d in spec.get("do", [])]
            poprzedni_naglowek, poprzedni_start = None, 0
            for m in od.finditer(r.tekst):
                start = m.end() if not spec.get("z_naglowkiem") else m.start()
                stop = len(r.tekst)
                for k in koniec:
                    mk = k.search(r.tekst, m.end())
                    if mk:
                        stop = min(stop, mk.start())
                if spec.get("max_znakow"):
                    stop = min(stop, start + int(spec["max_znakow"]))
                naglowek = re.sub(r"\s+", " ", m.group(0)).strip().casefold()
                if spec.get("scal_powtorzone") and wynik and naglowek == poprzedni_naglowek:
                    # ten sam nagłówek (np. „Za Firma” przy każdym podpisie): jeden blok zamiast kilku
                    wynik[-1] = Kontekst(r.tekst[poprzedni_start:stop], r.przesuniecie + poprzedni_start)
                else:
                    wynik.append(Kontekst(r.tekst[start:stop], r.przesuniecie + start))
                    poprzedni_start = start
                poprzedni_naglowek = naglowek
                if not spec.get("wiele", False):
                    break
        return wynik

    def _sekcja_z_modelu(self, spec: dict, rodzice: list[Kontekst]) -> list[Kontekst]:
        """Kotwica sekcji od modelu, gdy reguła `od` nic nie znalazła: model przepisuje dosłownie początek bloku
        (np. nazwę strony), sekcja zaczyna się w miejscu, gdzie ten fragment jest w tekście. Brak w tekście = brak sekcji."""
        wynik = []
        for r in rodzice:
            kotwica = self.llm(spec["llm"], r.tekst[: int(spec.get("max_znakow_modelu", 6000))])
            poz = znajdz_w_tekscie(kotwica, r.tekst) if kotwica else None
            if poz is None:
                continue
            start, stop = poz[0], len(r.tekst)
            for d in spec.get("do", []):
                mk = _kompiluj(d, spec.get("flagi")).search(r.tekst, poz[1])
                if mk:
                    stop = min(stop, mk.start())
            stop = min(stop, start + int(spec.get("max_znakow_z_modelu", 600)))
            wynik.append(Kontekst(r.tekst[start:stop], r.przesuniecie + start))
        return wynik

    def _konteksty(self, metoda: dict, ktx: Kontekst) -> list[Kontekst]:
        """Sekcje z `w` (nazwa albo lista nazw: pierwsza niepusta). `indeks: true` = i-te wystąpienie
        sekcji w całym dokumencie, gdzie i to numer bieżącego elementu listy (np. podpisy i-tego mocodawcy)."""
        if not metoda.get("w"):
            return [ktx]
        nazwy = metoda["w"] if isinstance(metoda["w"], list) else [metoda["w"]]
        for n in nazwy:
            if metoda.get("indeks") and ktx.indeks is not None:
                wszystkie = self.sekcja(n, self._pelny)
                k = wszystkie[ktx.indeks:ktx.indeks + 1]
            else:
                k = self.sekcja(n, ktx)
            if k:
                return k
        return []

    # ---------- metody ----------
    def _metoda(self, metoda: dict, ktx: Kontekst, normalizuj: list[str] = ()) -> tuple[Any, str | None, int | None]:
        """Lista sekcji w `w`: próbuje kolejnych, aż któraś da wartość (po normalizacji)."""
        nazwy = metoda["w"] if isinstance(metoda.get("w"), list) else [metoda.get("w")]
        for n in nazwy:
            for k in self._konteksty({**metoda, "w": n}, ktx):
                v, cytat, poz = self._metoda_w(metoda, k, normalizuj)
                v = zastosuj(v, list(normalizuj))
                if v is not None:
                    return v, cytat, poz
        return None, None, None

    def _metoda_w(self, metoda: dict, k: Kontekst, normalizuj: list[str] = ()) -> tuple[Any, str | None, int | None]:
        if "regex" in metoda:
            wzorce = metoda["regex"] if isinstance(metoda["regex"], list) else [metoda["regex"]]
            ktory = int(metoda.get("ktory", 1))  # n-te dopasowanie (1 = pierwsze, -1 = ostatnie)
            for w in wzorce:
                wszystkie = list(_kompiluj(w, metoda.get("flagi")).finditer(k.tekst))
                m = None
                if wszystkie and (ktory == -1 or len(wszystkie) >= ktory):
                    m = wszystkie[-1] if ktory == -1 else wszystkie[ktory - 1]
                if m:
                    v, poz = _wartosc_dopasowania(m)
                    return v, m.group(0), k.przesuniecie + poz
            return None, None, None
        if "etykieta" in metoda:
            return self._etykieta(metoda, k)
        if "slownik" in metoda:
            return self._slownik(metoda, k)
        if "jesli" in metoda:
            m = _kompiluj(metoda["jesli"], metoda.get("flagi")).search(k.tekst)
            if m:
                return metoda.get("to", 1), m.group(0), k.przesuniecie + m.start()
            return metoda.get("inaczej"), None, None
        if "stala" in metoda:
            return metoda["stala"], None, None
        if "calosc" in metoda:
            t = k.tekst.strip()
            return (t or None), t[:200], k.przesuniecie
        if "llm" in metoda:
            if self.llm is None:
                return None, None, None
            tekst = k.tekst[: int(metoda.get("max_znakow", 6000))]
            pozycje = self.slowniki[metoda["z_slownika"]] if metoda.get("z_slownika") else None
            pytanie = metoda["llm"]
            if pozycje:   # pytanie zamknięte: lista pozycji słownika „id – opis” dopisana do pytania
                pytanie += "\n" + "\n".join(f"{p['id']} – {p['opis']}" for p in pozycje)
            v = self.llm(pytanie, tekst)
            if v is None:
                return None, None, None
            if pozycje:   # odpowiedź = numer pozycji, jej opis albo „numer – opis”; wszystko inne odrzucone
                p = _pozycja_slownika(v, pozycje)
                return (p[metoda.get("zwroc", "id")], None, None) if p else (None, None, None)
            if metoda.get("kandydaci"):
                # odpowiedź musi być równa (po normalizatorach pola) jednemu z trafień wzorca w tekście; wartością
                # pola jest zapis z dokumentu (model może podać „2026-03-05” przy „5 marca 2026 r.” albo rachunek
                # bez spacji), a wartość spoza dokumentu odpada
                cel = _bez_pl(zastosuj(v, list(normalizuj)))
                # `bez_dat: true`: kandydat leżący w dacie („30.03” z „30.03.2026”, „6” albo „2026” z „6 marca 2026”)
                # nie jest kandydatem (ta sama zasada co w normalizatorze kwoty: data nigdy nie jest kwotą, Z46)
                daty = [d.span() for d in _DATY_W_TEKSCIE.finditer(tekst)] if metoda.get("bez_dat") else []
                for m in _kompiluj(metoda["kandydaci"], metoda.get("flagi")).finditer(tekst):
                    if any(a < m.end() and m.start() < b for a, b in daty):
                        continue
                    if cel is not None and _bez_pl(zastosuj(m.group(0), list(normalizuj))) == cel:
                        return m.group(0), m.group(0), k.przesuniecie + m.start()
                return None, None, None
            if metoda.get("sprawdz") == "doslownie":   # tylko ten sam ciąg znaków (bez dopasowania przybliżonego)
                poz = znajdz_w_tekscie(v, tekst, prog=101.0)
                if poz is None:
                    return None, None, None
                return tekst[poz[0]:poz[1]], tekst[poz[0]:poz[1]], k.przesuniecie + poz[0]
            if metoda.get("sprawdz", "w_tekscie") == "w_tekscie":  # odpowiedź musi być w dokumencie
                poz = znajdz_w_tekscie(v, tekst)
                if poz is None:
                    return None, None, None
                return v, tekst[poz[0]:poz[1]], k.przesuniecie + poz[0]
            return v, None, None
        raise ValueError(f"nieznana metoda: {sorted(metoda)}")

    def _etykieta(self, metoda: dict, k: Kontekst) -> tuple[Any, str | None, int | None]:
        """Wartość po etykiecie: 'Etykieta: X', 'ETYKIETA ..... X' albo etykieta w linii, X w następnej."""
        etykiety = metoda["etykieta"] if isinstance(metoda["etykieta"], list) else [metoda["etykieta"]]
        linie_dalej = int(metoda.get("linie", 1))
        for e in etykiety:
            m = re.search(rf"(?im)^[ \t]*{e}[ \t]*(?:[:.·…]+[ \t]*)?(?P<reszta>[^\n]*)", k.tekst)
            if not m:
                continue
            reszta = m.group("reszta").strip()
            if reszta:
                return reszta, m.group(0), k.przesuniecie + m.start("reszta")
            dalej = k.tekst[m.end():].lstrip("\n")
            linie = dalej.split("\n")[:linie_dalej]
            v = "\n".join(linie).strip()
            if v:
                return v, m.group(0) + "\n" + v, k.przesuniecie + m.end()
        return None, None, None

    def _slownik(self, metoda: dict, k: Kontekst) -> tuple[Any, str | None, int | None]:
        """Pierwsza (najwcześniej w tekście) pozycja słownika, której wzorzec pasuje."""
        pozycje = self.slowniki[metoda["slownik"]]
        najlepszy = None
        for p in pozycje:
            for w in p.get("wzorce", []):
                m = _kompiluj(w, metoda.get("flagi")).search(k.tekst)
                if m and (najlepszy is None or m.start() < najlepszy[1].start()):
                    najlepszy = (p, m)
        if najlepszy is None:
            return None, None, None
        p, m = najlepszy
        return p[metoda.get("zwroc", "id")], m.group(0), k.przesuniecie + m.start()

    # ---------- drzewo wyniku ----------
    def _lisc(self, spec: dict, ktx: Kontekst, sciezka: str, dowody: list[Dowod]) -> Any:
        for i, metoda in enumerate(spec.get("metody", [])):
            if metoda.get("siatka") and not self.siatka:   # siatka modelu wyłączona: jakby metody nie było
                continue
            v, cytat, poz = self._metoda(metoda, ktx, spec.get("normalizuj", []) + metoda.get("normalizuj", []))
            if v is not None:
                v = _rzutuj(v, spec.get("typ"))
                rodzaj = next(iter(k for k in metoda if k not in ("w", "flagi", "normalizuj", "siatka")), "?")
                dowody.append(Dowod(sciezka, v, f"{rodzaj}#{i}", cytat, poz))
                return v
        return spec.get("domyslnie")

    def _lista(self, spec: dict, ktx: Kontekst, sciezka: str, dowody: list[Dowod]) -> list:
        ls = spec["lista"]
        # `warianty`: kilka sposobów znalezienia elementów (inny układ dokumentu = inny wariant); wygrywa pierwszy,
        # który daje elementy. Wariant nadpisuje klucze wspólne listy (w, regex, flagi, indeks, rozdziel, dodatkowo…).
        elementy: list[Kontekst] = []
        for wariant in ls.get("warianty") or [{}]:
            elementy = self._elementy_listy({**{k: v for k, v in ls.items() if k != "warianty"}, **wariant}, ktx)
            if elementy:
                break
        return self._buduj_liste(spec, ls, elementy, ktx, sciezka, dowody)

    def _elementy_listy(self, ls: dict, ktx: Kontekst) -> list[Kontekst]:
        """Fragmenty tekstu będące elementami listy: z sekcji, z trafień wyrażenia, z dodatkowej sekcji, po podziale i filtrze."""
        elementy: list[Kontekst] = []
        if "sekcja" in ls:
            elementy = self._konteksty({"w": ls["sekcja"], "indeks": ls.get("indeks")}, ktx)
        elif "w" in ls and "regex" not in ls:
            elementy = self._konteksty(ls, ktx)
        if not elementy and "regex" in ls:
            # lista sekcji w `w`: kolejne próby, aż któraś da elementy (nie tylko pierwsza istniejąca sekcja)
            nazwy = ls["w"] if isinstance(ls.get("w"), list) else [ls.get("w")]
            for nazwa in nazwy:
                konteksty = self._konteksty({**ls, "w": nazwa}, ktx) if not ls.get("sekcja") else [ktx]
                for k in konteksty:
                    for m in _kompiluj(ls["regex"], ls.get("flagi")).finditer(k.tekst):
                        v, poz = _wartosc_dopasowania(m)
                        elementy.append(Kontekst(v, k.przesuniecie + poz))
                    if elementy:
                        break
                if elementy:
                    break
        dod = ls.get("dodatkowo")  # dodatkowe elementy z innej sekcji (np. same nazwiska pod „udziela pełnomocnictwa:”)
        if dod:
            for k in self._konteksty(dod, ktx):
                for m in _kompiluj(dod["regex"], dod.get("flagi")).finditer(k.tekst):
                    v, poz = _wartosc_dopasowania(m)
                    elementy.append(Kontekst(v, k.przesuniecie + poz))
        if ls.get("rozdziel"):
            podzielone: list[Kontekst] = []
            for e in elementy:
                poz = 0
                for czesc in re.split(ls["rozdziel"], e.tekst):
                    i = e.tekst.find(czesc, poz)
                    if czesc.strip():
                        podzielone.append(Kontekst(czesc, e.przesuniecie + max(i, 0)))
                    poz = max(i, 0) + len(czesc)
            elementy = podzielone
        if ls.get("wymagaj"):
            elementy = [e for e in elementy if _kompiluj(ls["wymagaj"], ls.get("flagi")).search(e.tekst)]
        return elementy

    def _buduj_liste(self, spec: dict, ls: dict, elementy: list[Kontekst], ktx: Kontekst, sciezka: str,
                     dowody: list[Dowod]) -> list:
        wynik = []
        widziane = set()
        for e in elementy:
            e = Kontekst(e.tekst, e.przesuniecie, len(wynik))
            obj = self.zbuduj(spec["element"], e, f"{sciezka}[{len(wynik)}]", dowody)
            klucz = repr(obj.get(ls["klucz"]) if ls.get("klucz") and isinstance(obj, dict) else obj)
            if ls.get("unikalne", True) and klucz in widziane:
                continue
            widziane.add(klucz)
            if _niepusty(obj):
                wynik.append(obj)
            if spec.get("max") and len(wynik) >= int(spec["max"]):
                break
        if not wynik and spec.get("min_jeden", True):
            wynik.append(self.zbuduj(spec["element"], Kontekst("", ktx.przesuniecie), f"{sciezka}[0]", dowody))
        if len(wynik) == 1 and ls.get("tylko_gdy_wiele"):  # np. prowadzacy_postepowanie: null przy 1 zamawiającym
            wynik = [{k: (None if k in ls["tylko_gdy_wiele"] else v) for k, v in wynik[0].items()}]
        return wynik

    def zbuduj(self, spec: Any, ktx: Kontekst, sciezka: str, dowody: list[Dowod]) -> Any:
        if isinstance(spec, dict) and "metody" in spec:
            return self._lisc(spec, ktx, sciezka, dowody)
        if isinstance(spec, dict) and "lista" in spec:
            return self._lista(spec, ktx, sciezka, dowody)
        if isinstance(spec, dict) and "obiekt" in spec:  # obiekt w podsekcji: {obiekt: {...}, w: sekcja}
            konteksty = self._konteksty(spec, ktx)
            k = konteksty[0] if konteksty else Kontekst("", ktx.przesuniecie)
            return self.zbuduj(spec["obiekt"], k, sciezka, dowody)
        if isinstance(spec, dict):
            return {k: self.zbuduj(v, ktx, f"{sciezka}.{k}" if sciezka else k, dowody) for k, v in spec.items()}
        return spec  # stała dosłowna (np. null)

    def ekstrahuj(self, tekst: str) -> Wynik:
        dowody: list[Dowod] = []
        self._pelny = Kontekst(tekst, 0)
        dane = self.zbuduj(self.klasa["wynik"], self._pelny, "", dowody)
        return Wynik(dane, dowody)


def _pozycja_slownika(odpowiedz: str, pozycje: list[dict]) -> dict | None:
    """Pozycja listy zamkniętej wskazana odpowiedzią modelu: sam numer („9”, „9.”), sam opis albo linia listy
    „9 – opis” (numer i opis tej samej pozycji). Numer spoza listy, dwa numery, data, inny tekst: None."""
    def opis(s: str) -> str:
        return re.sub(r"\s+", " ", s).strip(" .").casefold()
    m = re.fullmatch(r"\s*(\d{1,3})\s*[.)]?\s*(?:[–—:-]\s*(?P<opis>\S.*?))?\s*", odpowiedz, flags=re.S)
    for p in pozycje:
        if m and int(m.group(1)) == p["id"] and (m.group("opis") is None or opis(m.group("opis")) == opis(str(p["opis"]))):
            return p
        if not m and opis(odpowiedz) == opis(str(p["opis"])):
            return p
    return None


def _niepusty(obj: Any) -> bool:
    if isinstance(obj, dict):
        return any(_niepusty(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_niepusty(v) for v in obj)
    return obj is not None


def _rzutuj(v: Any, typ: str | None) -> Any:
    try:
        if typ == "int":
            return int(v)
        if typ == "float":
            return float(v)
        if typ == "str":
            return str(v)
    except (TypeError, ValueError):
        return None
    return v
