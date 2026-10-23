import sys
from pathlib import Path

if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--speech-worker":
        from framecheck.speech import speech_worker
        raise SystemExit(speech_worker(sys.argv[2]))
    elif len(sys.argv) > 1 and sys.argv[1] == "--cli":
        from framecheck.cli import main
        raise SystemExit(main(sys.argv[2:]))
    elif len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from framecheck.selftest import run
        raise SystemExit(run(Path(sys.argv[2])))
    else:
        from framecheck.gui import main
        main()
