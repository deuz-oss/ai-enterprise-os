"""Tes skrip benchmark (scripts/). Jalankan dari root repo dengan venv yang
punya pytest, httpx, aiohttp, numpy (mis. agent/.venv):

    agent/.venv/Scripts/python -m pytest scripts/tests -q
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # bench_common, bench_voice_latency, bench_avatar
sys.path.insert(0, str(HERE))  # fake_flashhead
