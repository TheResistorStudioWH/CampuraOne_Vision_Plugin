"""Source launcher; requires Python 3.9+, no installation or downloads."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'src'))
from campura_vision.cli import main

if __name__ == '__main__':
    if len(sys.argv) == 1:
        sys.argv.extend(['serve', '--open'])
    main()
