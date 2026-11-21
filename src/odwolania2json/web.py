"""Prototyp WWW: wgraj PDF-y sprawy, zobacz rozpoznany typ, JSON w formacie UZP i cytat przy każdym polu.

    ./run.sh --web            # http://localhost:8000
"""
from __future__ import annotations

import argparse
import logging
import os
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .potok import Potok

KORZEN = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).parent / "static"
MAKS_PLIKOW = 20
MAKS_BAJTOW = 25 * 1024 * 1024

log = logging.getLogger("odwolania2json.web")
app = FastAPI(title="Odwołania2json", docs_url=None, redoc_url=None)
_potok: Potok | None = None


def potok() -> Potok:
    global _potok
    if _potok is None:
        _potok = Potok(Path(os.environ.get("KLASY_DIR", KORZEN / "config" / "klasy")),
                       uzyj_llm=os.environ.get("BEZ_LLM") != "1")
    return _potok


@app.get("/")
def strona() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/api/klasy")
def klasy() -> list[dict]:
    return [{"nazwa": k.nazwa, "opis": k.spec.get("opis", ""), "plik": k.zrodlo.name} for k in potok().klasy]


@app.post("/api/przetworz")
async def przetworz(pliki: list[UploadFile] = File(...)) -> list[dict]:
    if len(pliki) > MAKS_PLIKOW:
        raise HTTPException(413, f"Najwyżej {MAKS_PLIKOW} plików naraz")
    wyniki = []
    with tempfile.TemporaryDirectory(prefix="odw-") as tmp:
        for i, plik in enumerate(pliki):
            nazwa = Path(plik.filename or f"plik_{i}.pdf").name
            if not nazwa.lower().endswith(".pdf"):
                wyniki.append({"plik": nazwa, "blad": "To nie jest PDF"})
                continue
            dane = await plik.read(MAKS_BAJTOW + 1)
            if len(dane) > MAKS_BAJTOW:
                wyniki.append({"plik": nazwa, "blad": "Plik większy niż 25 MB"})
                continue
            sciezka = Path(tmp) / f"{i}.pdf"
            sciezka.write_bytes(dane)
            try:
                w = potok().przetworz(sciezka)
            except Exception:  # pokazujemy błąd jednego pliku, reszta idzie dalej
                log.exception("Błąd przetwarzania %s", nazwa)
                wyniki.append({"plik": nazwa, "blad": "Nie udało się przetworzyć pliku"})
                continue
            w.audyt["plik"] = nazwa
            wyniki.append({"plik": nazwa, "json_nazwa": Path(nazwa).with_suffix(".json").name,
                           "klasa": w.klasa, "json": w.dane, "audyt": w.audyt})
    return wyniki


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")))
    a = ap.parse_args()
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    uvicorn.run(app, host=a.host, port=a.port)


if __name__ == "__main__":
    main()
