"""Start bez skryptów powłoki: `python run.py` (input/ -> output/), `python run.py --web` (podgląd w przeglądarce).

Działa z dowolnego katalogu i bez instalowania pakietu: dokłada src/ do ścieżki importu.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

if __name__ == "__main__":
    if sys.argv[1:2] == ["--web"]:
        from odwolania2json.web import main as web_main

        del sys.argv[1]
        web_main()
        sys.exit(0)
    from odwolania2json.__main__ import main

    sys.exit(main())
