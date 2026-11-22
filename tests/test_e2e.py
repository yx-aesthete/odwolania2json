"""E2E: CLI na szablonie UZP (nazwy ze spacjami, dokument obcy -> plik z {})."""
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

KORZEN = Path(__file__).resolve().parents[1]
SZABLON = KORZEN / "data/raw/uzp/szablon-aplikacja/input"


@pytest.mark.skipif(not SZABLON.exists(), reason="brak danych UZP (scripts/pobierz_dane.sh)")
def test_szablon_uzp(tmp_path):
    wej = tmp_path / "input"
    shutil.copytree(SZABLON, wej)
    wyj = tmp_path / "output"
    r = subprocess.run([sys.executable, "-m", "odwolania2json", "--input", str(wej), "--output", str(wyj),
                        "--audit", str(tmp_path / "audit"), "--bez-llm"],
                       cwd=KORZEN, env={"PYTHONPATH": str(KORZEN / "src"), "PATH": "", "O2J_BEZ_ENV": "1", "OCR": "0"}, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    negatyw = wyj / "case1" / "negatywny przyklad.json"
    assert negatyw.exists() and negatyw.read_text(encoding="utf-8") == "{}"
    assert (wyj / "case1" / "przyklad odwolanie.json").exists()


@pytest.mark.skipif(not SZABLON.exists(), reason="brak danych UZP (scripts/pobierz_dane.sh)")
def test_obcy_brak_pliku(tmp_path):
    wej = tmp_path / "input"
    shutil.copytree(SZABLON, wej)
    wyj = tmp_path / "output"
    r = subprocess.run([sys.executable, "-m", "odwolania2json", "--input", str(wej), "--output", str(wyj),
                        "--audit", str(tmp_path / "audit"), "--bez-llm"],
                       cwd=KORZEN, env={"PYTHONPATH": str(KORZEN / "src"), "PATH": "", "OBCY": "brak_pliku", "OCR": "0", "O2J_BEZ_ENV": "1"},
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "nie dopasowano typu" in r.stderr
    assert not (wyj / "case1" / "negatywny przyklad.json").exists()
