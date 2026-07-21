from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = REPO_ROOT / "docs" / "openapi"
SERVICES_DIR = REPO_ROOT / "services"


def _load_app(main_file: Path):
    module_name = f"openapi_{main_file.parent.parent.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, main_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module from {main_file}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    generated = []
    for service_dir in sorted(SERVICES_DIR.iterdir()):
        if not service_dir.is_dir():
            continue
        src_dirs = list((service_dir / "src").glob("*/main.py"))
        if not src_dirs:
            continue
        service_src = src_dirs[0].parent.parent
        if str(service_src) not in sys.path:
            sys.path.insert(0, str(service_src))
        app = _load_app(src_dirs[0])
        schema = app.openapi()
        target = OUTPUT_DIR / f"{service_dir.name}.openapi.json"
        target.write_text(json.dumps(schema, indent=2), encoding="utf-8")
        generated.append(str(target.relative_to(REPO_ROOT)))
    print(json.dumps({"status": "ok", "generated": generated}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
