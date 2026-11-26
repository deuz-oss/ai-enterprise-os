"""Demo lokal sekali jalan: backend + frontend + data contoh, tanpa Docker.

Jalankan dari root repo (Windows / macOS / Linux):

    python scripts/demo_local.py

Prasyarat: Python 3.12+ dan Node 20+. Skrip ini:
  1. membuat backend/.venv + memasang dependensi terkunci (sekali saja),
  2. membuat .env demo bila belum ada (SECRET_KEY acak, admin demo),
  3. menjalankan backend (:8000) dan frontend (:5173),
  4. mengisi akun admin, HR, dan satu karyawan demo yang siap absen.

Data tersimpan di folder data/ (SQLite, tidak masuk git). Hentikan dengan Ctrl+C.
Hanya memakai pustaka standar Python.
"""

from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
API = "http://127.0.0.1:8000/api/v1"
IS_WIN = os.name == "nt"
VENV_PY = BACKEND / ".venv" / ("Scripts/python.exe" if IS_WIN else "bin/python")

DEMO_ADMIN_EMAIL = "admin@demo-aeos.co.id"
DEMO_ADMIN_PASSWORD = "DemoAeos-2026!"
DEMO_PASSWORD = "DemoAeos-2026!"
DEMO_ACCOUNTS = {
    "hr": ("hr@demo-aeos.co.id", "Demo HR"),
    "karyawan": ("karyawan@demo-aeos.co.id", "Demo Karyawan"),
}


def log(msg: str) -> None:
    print(f"\n==> {msg}", flush=True)


def run(cmd: list[str], cwd: Path, **kw) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, **kw)


def ensure_backend_env() -> None:
    if VENV_PY.exists():
        return
    log("Menyiapkan backend (pertama kali, beberapa menit)")
    run([sys.executable, "-m", "venv", ".venv"], BACKEND)
    run([str(VENV_PY), "-m", "pip", "install", "-q", "-r", "requirements-dev.lock"], BACKEND)
    run([str(VENV_PY), "-m", "pip", "install", "-q", "--no-deps", "-e", "."], BACKEND)


def ensure_dotenv() -> dict[str, str]:
    env_file = ROOT / ".env"
    if not env_file.exists():
        log("Membuat .env demo")
        text = (ROOT / ".env.example").read_text(encoding="utf-8")
        repl = {
            "SECRET_KEY": secrets.token_hex(32),
            "ADMIN_EMAIL": DEMO_ADMIN_EMAIL,
            "ADMIN_PASSWORD": DEMO_ADMIN_PASSWORD,
        }
        lines = []
        for line in text.splitlines():
            key = line.split("=", 1)[0].strip()
            lines.append(f"{key}={repl[key]}" if key in repl and "=" in line else line)
        env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    values: dict[str, str] = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip('"')
    return values


def call(method: str, path: str, body=None, token: str | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(API + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except ValueError:
            return e.code, raw.decode(errors="replace")


def wait_backend(proc: subprocess.Popen) -> None:
    for _ in range(90):
        if proc.poll() is not None:
            sys.exit("Backend berhenti mendadak -- lihat pesan error di atas.")
        try:
            with urllib.request.urlopen("http://127.0.0.1:8000/health/live", timeout=2):
                return
        except OSError:
            time.sleep(1)
    sys.exit("Backend tidak merespons dalam 90 detik.")


def seed(admin_email: str, admin_password: str) -> None:
    log("Mengisi data contoh")
    status, body = call("POST", "/auth/login", {"email": admin_email, "password": admin_password})
    if status != 200:
        sys.exit(f"Login admin gagal ({status}). Cek ADMIN_EMAIL/ADMIN_PASSWORD di .env.")
    token = body["access_token"]

    for role, (email, name) in DEMO_ACCOUNTS.items():
        status, _ = call(
            "POST",
            "/auth/register",
            {"email": email, "full_name": name, "password": DEMO_PASSWORD, "role": role},
            token,
        )
        print(f"  akun {email}: {'dibuat' if status == 201 else 'sudah ada' if status == 409 else status}")

    _, employees = call("GET", "/employees", token=token)
    emp = next((e for e in employees if e["employee_no"] == "DEMO-001"), None)
    if emp is None:
        status, emp = call(
            "POST",
            "/employees",
            {
                "full_name": "Demo Karyawan",
                "employee_no": "DEMO-001",
                "employment_type": "internal",
                "join_date": "2026-01-06",
            },
            token,
        )
        if status not in (200, 201):
            sys.exit(f"Gagal membuat karyawan demo: {emp}")
    _, users = call("GET", "/auth/users", token=token)
    user = next(u for u in users if u["email"] == DEMO_ACCOUNTS["karyawan"][0])
    status, out = call(
        "PATCH",
        f"/employees/{emp['id']}",
        {"user_id": user["id"], "shift_start_time": "08:00", "shift_end_time": "17:00"},
        token,
    )
    if status != 200:
        sys.exit(f"Gagal menautkan karyawan ke akun: {out}")
    print("  karyawan DEMO-001 siap absen (tanpa batas lokasi)")


def main() -> int:
    if sys.version_info < (3, 12):
        sys.exit("Butuh Python 3.12+.")
    npm = shutil.which("npm")
    skip_frontend = "--no-frontend" in sys.argv
    if not npm and not skip_frontend:
        sys.exit("Node/npm tidak ditemukan. Pasang Node 20+ dari nodejs.org.")

    ensure_backend_env()
    env_values = ensure_dotenv()
    admin_email = env_values.get("ADMIN_EMAIL", DEMO_ADMIN_EMAIL)
    admin_password = env_values.get("ADMIN_PASSWORD", DEMO_ADMIN_PASSWORD)

    if not skip_frontend and not (FRONTEND / "node_modules").exists():
        log("Memasang dependensi frontend (pertama kali)")
        run([npm, "install", "--no-audit", "--no-fund"], FRONTEND)

    procs: list[subprocess.Popen] = []
    try:
        log("Menjalankan backend")
        backend = subprocess.Popen(
            [str(VENV_PY), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            cwd=BACKEND,
        )
        procs.append(backend)
        wait_backend(backend)
        seed(admin_email, admin_password)

        if not skip_frontend:
            log("Menjalankan frontend")
            procs.append(subprocess.Popen([npm, "run", "dev", "--", "--host", "127.0.0.1"], cwd=FRONTEND))

        print(
            f"""
==================== DEMO SIAP ====================
Buka di browser:  http://localhost:5173

Login admin    : {admin_email} / {admin_password}
Login HR       : {DEMO_ACCOUNTS['hr'][0]} / {DEMO_PASSWORD}
Login karyawan : {DEMO_ACCOUNTS['karyawan'][0]} / {DEMO_PASSWORD}

Coba absen: login sebagai karyawan -> menu portal "Saya" -> Absensi ->
Clock-in (izinkan kamera + lokasi di browser; harus lewat localhost).
Lihat hasilnya: login sebagai HR/admin -> menu Absensi.

Tekan Ctrl+C untuk berhenti.
===================================================
""",
            flush=True,
        )
        while all(p.poll() is None for p in procs):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
