import sys
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from framecheck.selftest import run
        raise SystemExit(run(Path(sys.argv[2])))
    else:
        from framecheck.gui import main
        main()
