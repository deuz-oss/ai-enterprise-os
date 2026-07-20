import sys
from pathlib import Path

SERVICES_ROOT = Path(__file__).parent

for src_dir in SERVICES_ROOT.glob("*/src"):
    sys.path.insert(0, str(src_dir.resolve()))
