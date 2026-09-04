# Configuration commune des tests
import sys
from pathlib import Path

# Ajoute la racine du projet au chemin Python
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
