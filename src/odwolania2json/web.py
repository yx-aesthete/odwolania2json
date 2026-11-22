"""Prototyp WWW: wgraj PDF-y sprawy, zobacz rozpoznany typ, JSON w formacie UZP i cytat przy każdym polu.

    ./run.sh --web            # http://localhost:8000

Limity (strona publiczna woła model kluczem właściciela; zmienne środowiskowe nadpisują):
WEB_MAKS_PLIKOW (10), WEB_MAKS_MB (10 MB na całe wgranie), WEB_WGRAN_NA_GODZINE (20 z jednego adresu IP),
WEB_MAKS_WYWOLAN_DZIENNIE (400 wywołań modelu i OCR na dobę, potem same reguły), WEB_MAKS_STRON (20 stron OCR na plik).
Podgląd sprawy (/api/sprawa, strona główna): pliki leżą w katalogu tymczasowym najwyżej WEB_SPRAWA_MIN minut
(domyślnie 60) albo do zamknięcia sprawy, żeby można było pokazać stronę PDF z zaznaczonym cytatem.
Stare /api/przetworz (jedno zapytanie, pliki usuwane od razu) zostaje dla zgodności.
"""
from __future__ import annotations

import argparse
import logging
import os
import tempfile
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .potok import Potok, przetworz_bezpiecznie

KORZEN = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).parent / "static"
MAKS_PLIKOW = int(os.environ.get("WEB_MAKS_PLIKOW", "10"))
MAKS_BAJTOW = int(float(os.environ.get("WEB_MAKS_MB", "10")) * 1024 * 1024)
WGRAN_NA_GODZINE = int(os.environ.get("WEB_WGRAN_NA_GODZINE", "20"))
PRZYKLAD = KORZEN / "tests" / "kontrolny" / "input" / "case06"  # sprawa demonstracyjna (4 pliki, w tym obcy)
WEB_WATKI = max(1, int(os.environ.get("WEB_WATKI", "3")))  # ile plików jednego wgrania naraz
# Z33: strona jest publiczna, a model woła klucz właściciela. Sufit dzienny wywołań (model i OCR łącznie, licznik
# w pamięci, zerowany o północy); po nim podgląd działa dalej na samych regułach. Dłuższe PDF-y: OCR do WEB_MAKS_STRON.
MAKS_WYWOLAN_DZIENNIE = int(os.environ.get("WEB_MAKS_WYWOLAN_DZIENNIE", "400"))  # limity Scaleway wspólne z oceną UZP
MAKS_STRON = int(os.environ.get("WEB_MAKS_STRON", "20"))
UWAGA_SUFIT = "Dzienny limit modelu wyczerpany: wynik z reguł, skany nieodczytane."

log = logging.getLogger("odwolania2json.web")
OPIS_API = """Zamiana PDF-ów sprawy odwoławczej KIO na JSON w formacie UZP, z cytatem i stroną źródła przy każdym polu.

Integracja w trzech krokach:
1. `POST /api/sprawa` z plikami PDF (pole formularza `pliki`) zwraca `id` sprawy; z `?czekaj=true` od razu pełny wynik.
2. `GET /api/sprawa/{id}` zwraca stan każdego pliku (`oczekuje`, `przetwarzanie`, `gotowe`, `blad`), a dla gotowych:
   `klasa` (null = dokument obcy), `json` (format UZP), `audyt` (cytaty, strony, metody) i `polozenia` (prostokąty cytatów).
3. `GET /api/sprawa/{id}/zip` albo `GET /api/sprawa/{id}/plik/{nr}.json` zwraca pliki takie jak w `./output`.
"""
app = FastAPI(title="Odwołania2json", description=OPIS_API, version="1.0", docs_url="/docs", redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC), name="static")
_potok: Potok | None = None
_wgrania: dict[str, deque] = defaultdict(deque)
_blokada = threading.Lock()


def potok() -> Potok:
    global _potok
    if _potok is None:
        _potok = Potok(Path(os.environ.get("KLASY_DIR", KORZEN / "config" / "klasy")),
                       uzyj_llm=os.environ.get("BEZ_LLM") != "1")
    return _potok


def _adres(request: Request) -> str:
    """Adres klienta: za tunelem Cloudflare z nagłówka CF-Connecting-IP, inaczej z połączenia."""
    return request.headers.get("cf-connecting-ip") or (request.client.host if request.client else "?")


def _sprawdz_limit(adres: str) -> None:
    teraz = time.time()
    with _blokada:
        kolejka = _wgrania[adres]
        while kolejka and teraz - kolejka[0] > 3600:
            kolejka.popleft()
        if len(kolejka) >= WGRAN_NA_GODZINE:
            minuty = int((3600 - (teraz - kolejka[0])) // 60) + 1
            raise HTTPException(429, f"Limit {WGRAN_NA_GODZINE} wgrań na godzinę z jednego adresu. "
                                     f"Spróbuj ponownie za {minuty} min.")
        kolejka.append(teraz)


@app.get("/")
def strona() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/jak-to-dziala", include_in_schema=False)
def jak_to_dziala() -> FileResponse:
    return FileResponse(STATIC / "jak-to-dziala.html")


@app.get("/api/klasy")
def klasy() -> list[dict]:
    return [{"nazwa": k.nazwa, "opis": k.spec.get("opis", ""), "plik": k.zrodlo.name} for k in potok().klasy]


@app.get("/api/limity")
def limity() -> dict:
    from . import budzet
    return {"maks_plikow": MAKS_PLIKOW, "maks_mb": MAKS_BAJTOW // (1024 * 1024), "wgran_na_godzine": WGRAN_NA_GODZINE,
            "maks_stron_ocr": MAKS_STRON, **budzet.stan_sufitu()}


@app.post("/api/przetworz")
async def przetworz(request: Request, pliki: list[UploadFile] = File(...)) -> list[dict]:
    if len(pliki) > MAKS_PLIKOW:
        raise HTTPException(413, f"Najwyżej {MAKS_PLIKOW} plików naraz")
    _sprawdz_limit(_adres(request))
    wyniki: list[dict | None] = []
    do_przetworzenia: list[tuple[int, str, Path]] = []
    razem = 0
    with tempfile.TemporaryDirectory(prefix="odw-") as tmp:  # pliki znikają po przetworzeniu
        for i, plik in enumerate(pliki):
            nazwa = Path(plik.filename or f"plik_{i}.pdf").name
            if not nazwa.lower().endswith(".pdf"):
                wyniki.append({"plik": nazwa, "blad": "To nie jest PDF"})
                continue
            dane = await plik.read(MAKS_BAJTOW - razem + 1)
            razem += len(dane)
            if razem > MAKS_BAJTOW:
                raise HTTPException(413, f"Razem najwyżej {MAKS_BAJTOW // (1024 * 1024)} MB na jedno wgranie")
            sciezka = Path(tmp) / f"{i}.pdf"
            sciezka.write_bytes(dane)
            do_przetworzenia.append((len(wyniki), nazwa, sciezka))
            wyniki.append(None)

        def jeden(nazwa: str, sciezka: Path) -> dict:
            w = przetworz_bezpiecznie(potok(), sciezka, log)  # zepsuty plik: reguły albo {}, reszta idzie dalej
            if w.audyt.get("blad"):
                return {"plik": nazwa, "json_nazwa": Path(nazwa).with_suffix(".json").name, "klasa": None,
                        "json": {}, "audyt": w.audyt, "blad": "Nie udało się przetworzyć pliku (wynik: {})"}
            w.audyt["plik"] = nazwa
            return {"plik": nazwa, "json_nazwa": Path(nazwa).with_suffix(".json").name,
                    "klasa": w.klasa, "json": w.dane or {}, "audyt": w.audyt}

        def wszystkie() -> list[dict]:
            # pliki wgrania równolegle (skany czekają głównie na API OCR), żeby zmieścić się w limicie czasu
            # zapytania za tunelem; w osobnym wątku, żeby serwer odpowiadał innym
            with ThreadPoolExecutor(WEB_WATKI) as ex:
                return list(ex.map(lambda t: jeden(t[1], t[2]), do_przetworzenia))

        for (miejsce, _, _), wynik in zip(do_przetworzenia, await run_in_threadpool(wszystkie)):
            wyniki[miejsce] = wynik
    return wyniki


from . import podglad, sprawy  # noqa: E402

_rejestr = sprawy.Rejestr(potok, WEB_WATKI)


async def _wczytaj_pliki(pliki: list[UploadFile]) -> list[tuple[str, bytes | None, str | None]]:
    if len(pliki) > MAKS_PLIKOW:
        raise HTTPException(413, f"Najwyżej {MAKS_PLIKOW} plików naraz")
    wynik, razem = [], 0
    for i, plik in enumerate(pliki):
        nazwa = Path(plik.filename or f"plik_{i}.pdf").name
        if not nazwa.lower().endswith(".pdf"):
            wynik.append((nazwa, None, "To nie jest PDF"))
            continue
        dane = await plik.read(MAKS_BAJTOW - razem + 1)
        razem += len(dane)
        if razem > MAKS_BAJTOW:
            raise HTTPException(413, f"Razem najwyżej {MAKS_BAJTOW // (1024 * 1024)} MB na jedno wgranie")
        wynik.append((nazwa, dane, None))
    return wynik


def _sprawa(id_: str) -> sprawy.Sprawa:
    s = _rejestr.pobierz(id_)
    if s is None:
        raise HTTPException(404, "Nie ma takiej sprawy (wygasła albo została zamknięta). Wgraj pliki ponownie.")
    return s


def _plik(id_: str, nr: int) -> sprawy.PlikSprawy:
    s = _sprawa(id_)
    if not 0 <= nr < len(s.pliki):
        raise HTTPException(404, "Nie ma takiego pliku w sprawie")
    return s.pliki[nr]


@app.post("/api/sprawa", tags=["sprawa"], summary="Wgraj PDF-y sprawy")
async def nowa_sprawa(request: Request, pliki: list[UploadFile] = File(..., description="PDF-y jednej sprawy"),
                      czekaj: bool = Query(False, description="true: odpowiedź dopiero z gotowym wynikiem"),
                      nazwa: str | None = Form(None, description="katalog sprawy w ./output (domyślnie sprawa-<data>-<id>)")) -> dict:
    """Tworzy sprawę i przetwarza pliki w tle. Bez `czekaj` odpowiada od razu (stan `oczekuje`);
    postęp: `GET /api/sprawa/{id}`. Pliki leżą na serwerze najwyżej `WEB_SPRAWA_MIN` minut."""
    dane = await _wczytaj_pliki(pliki)
    _sprawdz_limit(_adres(request))
    s = await run_in_threadpool(_rejestr.utworz, dane, nazwa)
    if czekaj:
        await run_in_threadpool(_rejestr.czekaj, s)
    return s.opis()


@app.get("/api/przyklad", tags=["sprawa"], summary="Czy jest sprawa demonstracyjna")
def przyklad() -> dict:
    pliki = sorted(p.name for p in PRZYKLAD.glob("*.pdf")) if PRZYKLAD.is_dir() else []
    return {"dostepny": bool(pliki), "pliki": pliki}


@app.post("/api/sprawa/przyklad", tags=["sprawa"], summary="Uruchom sprawę demonstracyjną")
async def sprawa_przykladowa(request: Request) -> dict:
    """Ta sama ścieżka co wgranie, na plikach z `tests/kontrolny/input/case06` (3 pisma UZP i pismo obce)."""
    pliki = sorted(PRZYKLAD.glob("*.pdf")) if PRZYKLAD.is_dir() else []
    if not pliki:
        raise HTTPException(404, "Brak sprawy demonstracyjnej w tej instalacji")
    _sprawdz_limit(_adres(request))
    s = await run_in_threadpool(_rejestr.utworz, [(p.name, p.read_bytes(), None) for p in pliki], None)
    return s.opis()


@app.get("/api/sprawa/{id_}", tags=["sprawa"], summary="Stan i wyniki sprawy")
def stan_sprawy(id_: str) -> dict:
    return _sprawa(id_).opis()


@app.delete("/api/sprawa/{id_}", tags=["sprawa"], summary="Zamknij sprawę i usuń pliki z serwera")
def zamknij_sprawe(id_: str) -> dict:
    return {"usunieta": _rejestr.usun(id_)}


@app.get("/api/sprawa/{id_}/zip", tags=["pobieranie"], summary="ZIP z JSON-ami całej sprawy (jak ./output)")
def zip_sprawy(id_: str) -> Response:
    from .__main__ import tryb_obcych
    from .sprawa import wlaczone
    s = _sprawa(id_)
    if not s.gotowa:
        raise HTTPException(409, "Sprawa jest jeszcze przetwarzana")
    dane = sprawy.zip_sprawy(s, tryb_obcych(), wlaczone(KORZEN / "config" / "aplikacja.yaml"))
    return Response(dane, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="sprawa-{s.id[:8]}.zip"'})


@app.get("/api/sprawa/{id_}/plik/{nr}.json", tags=["pobieranie"], summary="JSON jednego pliku (jak ./output)")
def json_pliku(id_: str, nr: int) -> Response:
    from .__main__ import tryb_obcych
    p = _plik(id_, nr)
    if p.wynik is None:
        raise HTTPException(409, "Plik nie ma jeszcze wyniku")
    tresc = sprawy.json_pliku(p, tryb_obcych())
    if tresc is None:
        raise HTTPException(404, "Dla dokumentu obcego nie zapisujemy pliku (obcy: brak_pliku)")
    nazwa = p.json_nazwa.encode("ascii", "replace").decode()
    return Response(tresc, media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="{nazwa}"'})


@app.get("/api/sprawa/{id_}/plik/{nr}/strona/{strona}.png", tags=["podgląd"], summary="Obraz strony PDF")
async def strona_png(id_: str, nr: int, strona: int) -> Response:
    p = _plik(id_, nr)
    if p.sciezka is None or not p.sciezka.exists():
        raise HTTPException(404, "Brak pliku PDF")
    cache = p.sciezka.with_name(f"{nr}-s{strona}.png")
    if not cache.exists():
        try:
            cache.write_bytes(await run_in_threadpool(podglad.obraz_strony, p.sciezka, strona))
        except ValueError as e:
            raise HTTPException(404, str(e)) from e
    return Response(cache.read_bytes(), media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})


def main() -> None:
    from .__main__ import bezpieczne_wyjscie
    from .llm import wczytaj_env
    bezpieczne_wyjscie()
    wczytaj_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    a = ap.parse_args()
    from . import budzet
    budzet.ustaw_sufit_dzienny(MAKS_WYWOLAN_DZIENNIE)   # tylko serwer WWW; CLI (ocena UZP) bez sufitu
    os.environ.setdefault("OCR_MAKS_STRON", str(MAKS_STRON))
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run(app, host=a.host, port=a.port)


if __name__ == "__main__":
    main()
