# Development Guide

Panduan setup lingkungan pengembangan. Prasyarat: Python 3.12+ dan Node 20+.
Docker hanya diperlukan jika ingin memakai PostgreSQL + MinIO.

## Mode lokal (tanpa Docker)

1. Buka folder proyek ini di VS Code.
2. Buka terminal terintegrasi (`Ctrl+` `).

Backend:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
copy ..\.env.example .env         # lalu edit SECRET_KEY & ADMIN_PASSWORD
uvicorn app.main:app --reload     # http://localhost:8000/docs
```

Frontend (terminal kedua):

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173 (proxy /api → :8000)
```

Login pertama memakai `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

**Data lokal:** database SQLite tersimpan di `data/aeos.db`, dokumen upload di
`data/uploads/`. Folder `data/` tidak masuk git. Backup cukup dengan menyalin
folder `data/`.

Debugging: tekan `F5` (konfigurasi "Backend: FastAPI" sudah disiapkan).

## Mode Docker (PostgreSQL + MinIO)

```bash
cp .env.example .env    # isi POSTGRES_* & STORAGE_*
docker compose up -d --build
```

## Database

- Mode lokal: SQLite, tabel dibuat otomatis (`create_all`) saat start.
- Migrasi formal: `cd backend && alembic revision --autogenerate -m "..." && alembic upgrade head`.

## Kualitas kode

```bash
python -m ruff check backend   # lint
python -m mypy backend/app     # type check
python -m pytest -q            # unit test
cd frontend && npm run build   # build + type check TS
```

## Menambah modul domain baru

1. Copy folder `backend/app/modules/presales` sebagai template.
2. Sesuaikan `models.py`, `schemas.py`, `service.py`, `router.py`.
3. Daftarkan router di `backend/app/main.py`.
4. Import model di `backend/alembic/env.py` agar terdeteksi migrasi.
5. Tambahkan test di `backend/tests/`.

Konvensi lengkap: [FolderStructure](FolderStructure.md).
