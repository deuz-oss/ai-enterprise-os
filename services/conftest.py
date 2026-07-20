from pathlib import Path
import sys


SERVICES_ROOT = Path(__file__).parent

for src_dir in SERVICES_ROOT.glob("*/src"):
    sys.path.insert(0, str(src_dir.resolve()))
