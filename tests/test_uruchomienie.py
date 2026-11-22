"""Uruchomienie u UZP: instalacja z requirements.txt spoza katalogu aplikacji, start bez skryptów (run.py,
python -m), wyjście w stronie kodowej bez polskich liter, skrypty startowe Windows."""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

KORZEN = Path(__file__).resolve().parents[1]
SPRAWA = KORZEN / "tests/kontrolny/input/case06"
BEZ_MODELU = {"O2J_BEZ_ENV": "1", "MODEL_TRYB": "brak", "OCR": "0"}


def _env(**dodatkowe) -> dict:
    """Środowisko jak na czystym komputerze: bez PYTHONPATH i bez pakietu zainstalowanego z src/."""
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "PYTHONUTF8", "PYTHONIOENCODING")}
    return {**env, **BEZ_MODELU, **dodatkowe}


def _wejscie(tmp_path: Path) -> Path:
    wej = tmp_path / "input" / "sprawa"
    wej.mkdir(parents=True)
    for p in SPRAWA.glob("*.pdf"):
        (wej / p.name).write_bytes(p.read_bytes())
    (wej / "zepsuty żółw.pdf").write_text("to nie jest PDF", encoding="utf-8")  # log z polskimi znakami
    return tmp_path / "input"


def test_requirements_bez_instalacji_pakietu():
    linie = [l.strip() for l in (KORZEN / "requirements.txt").read_text(encoding="utf-8").splitlines()]
    assert not [l for l in linie if l.startswith("-e") or l == "."]  # pip -r spoza katalogu aplikacji nie padnie


@pytest.mark.skipif(not SPRAWA.exists(), reason="brak zbioru kontrolnego")
def test_run_py_z_innego_katalogu(tmp_path):
    wej = _wejscie(tmp_path)
    r = subprocess.run([sys.executable, str(KORZEN / "run.py"), "--input", str(wej), "--output", str(tmp_path / "out"),
                        "--audit", str(tmp_path / "audit")],
                       cwd=tmp_path, env=_env(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "out/sprawa/odwolanie_nr_6.json").read_text(encoding="utf-8") != "{}"


@pytest.mark.skipif(not SPRAWA.exists(), reason="brak zbioru kontrolnego")
def test_python_m_w_katalogu_aplikacji_bez_pythonpath(tmp_path):
    wej = _wejscie(tmp_path)
    r = subprocess.run([sys.executable, "-m", "odwolania2json", "--input", str(wej), "--output", str(tmp_path / "out"),
                        "--audit", str(tmp_path / "audit")],
                       cwd=KORZEN, env=_env(), capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    assert (tmp_path / "out/sprawa/odwolanie_nr_6.json").exists()


@pytest.mark.skipif(not SPRAWA.exists(), reason="brak zbioru kontrolnego")
@pytest.mark.parametrize("kodowanie", ["ascii", "cp1252"])
def test_wyjscie_bez_polskich_liter_nie_przerywa_przebiegu(tmp_path, kodowanie):
    """stdout/stderr przekierowane do pliku w stronie kodowej bez „ż”, „ł” (np. angielski Windows)."""
    wej = _wejscie(tmp_path)
    r = subprocess.run([sys.executable, str(KORZEN / "run.py"), "--input", str(wej), "--output", str(tmp_path / "out"),
                        "--audit", str(tmp_path / "audit")],
                       env=_env(PYTHONIOENCODING=kodowanie, PYTHONUTF8="0"), capture_output=True, timeout=120)
    assert r.returncode == 0, r.stderr.decode(kodowanie, "replace")
    log = r.stderr.decode(kodowanie)
    assert "nie da si\\u0119 odczyta\\u0107" in log and "Gotowe" in log
    assert "Traceback" not in log and "Logging error" not in log  # wcześniej: UnicodeEncodeError z print()
    wyniki = sorted(p.name for p in (tmp_path / "out/sprawa").glob("*.json"))
    assert len(wyniki) == len(list(SPRAWA.glob("*.pdf"))) + 1


@pytest.mark.parametrize("modul", ["odwolania2json.__main__", "odwolania2json.web"])
def test_stdout_ascii_polski_tekst_bez_wyjatku(modul):
    kod = (f"import sys; sys.path.insert(0, {str(KORZEN / 'src')!r}); import {modul} as m; "
           "sys.argv = ['x', '--help']\n"
           "try:\n    m.main()\nexcept SystemExit:\n    pass\n"
           "print('Zamawiający: Gmina Żółkiewka')")
    r = subprocess.run([sys.executable, "-c", kod], env=_env(PYTHONIOENCODING="ascii", PYTHONUTF8="0"),
                       capture_output=True, timeout=60)
    assert r.returncode == 0, r.stderr.decode("ascii", "replace")
    assert b"Zamawiaj\\u0105cy: Gmina \\u017b\\xf3\\u0142kiewka" in r.stdout


def test_pdftext_bez_print():
    kod = (KORZEN / "src/odwolania2json/pdftext.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*print\(", kod, re.M)


def test_run_sh_nie_wciaga_env_przez_powloke():
    skrypt = (KORZEN / "run.sh").read_text(encoding="utf-8")
    assert not re.search(r"^\s*[^#\n]*(?:\.|source)\s+\.?/?\.env", skrypt, re.M)


@pytest.mark.parametrize("nazwa", ["run.bat", "start.bat"])
def test_skrypty_windows(nazwa):
    dane = (KORZEN / nazwa).read_bytes()
    dane.decode("ascii")  # bez polskich liter: cmd.exe czyta plik w stronie kodowej OEM
    assert b"\r\n" in dane and b"\n" not in dane.replace(b"\r\n", b"")
    tekst = dane.decode("ascii").lower()
    assert "setlocal" in tekst and "exit /b" in tekst
    if nazwa == "run.bat":
        assert 'pushd "%~dp0"' in tekst
        assert 'set "pythonpath=%cd%\\src"' in tekst and 'set "pythonutf8=1"' in tekst
        assert tekst.index(".venv\\scripts\\python.exe") < tekst.index("py -3") < tekst.index('set "py=python"')
        assert '--input "%cd%\\input" --output "%cd%\\output"' in tekst
    else:
        assert 'call "%~dp0run.bat" %*' in tekst
