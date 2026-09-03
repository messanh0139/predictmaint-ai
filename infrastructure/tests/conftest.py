# Configuration partagée par tous les tests : garantit que le package `src`
# est importable, même si pytest est lancé depuis un autre répertoire.
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
