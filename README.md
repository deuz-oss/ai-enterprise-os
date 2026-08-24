# AI Enterprise OS

Sistem operasional end-to-end untuk perusahaan **outsourcing (manpower services)**:
pipeline calon klien → onboarding klien + dokumen legalitas → rekrutmen
(job order, kandidat, placement) → HRD → payrol & PPh21 → finance & akunting.

> Status: **Semua fase roadmap selesai** (MVP s/d AI Layer + platform:
> multi-tenant SaaS, TTE, BPJS, mobile app internal).
> Lihat [PRD](docs/02-product/PRD.md) & [roadmap](docs/02-product/FEATURE_ROADMAP.md).

## Quick start

### Mode lokal (tanpa Docker — direkomendasikan untuk mulai)

```bash
# 1. Buka folder ini di VS Code, lalu buka Terminal (Ctrl+`)

# 2. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
copy ..\.env.example .env         # lalu edit SECRET_KEY & ADMIN_PASSWORD
uvicorn app.main:app --reload     # http://localhost:8000/docs

# 3. Terminal baru — Frontend
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

Semua data tersimpan **di dalam folder proyek** pada `data/`:
- `data/aeos.db` — database SQLite
- `data/uploads/` — dokumen legalitas & CV yang di-upload

Tidak perlu Docker, PostgreSQL, maupun MinIO untuk memulai.

### Mode Docker (PostgreSQL + MinIO)

```bash
cp .env.example .env      # isi POSTGRES_* & STORAGE_* lalu docker compose up -d --build
docker compose up -d --build
docker compose ps         # backend :8000, frontend :3000, MinIO console :9001
```

Login pertama menggunakan `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

### Deployment produksi

Lihat [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) — compose produksi dengan
TLS otomatis (Caddy), migrasi idempoten, dan prosedur backup/restore.

## Perintah umum

| Perintah | Fungsi |
|----------|--------|
| `make dev` | Start seluruh stack via Docker Compose |
| `make down` | Stop stack |
| `make logs` | Streaming log |
| `make lint` | Ruff + mypy (backend) |
| `make test` | Pytest (backend) |
| `make fmt` | Format otomatis |

## Struktur repo

```
backend/    FastAPI modular monolith (module per domain bisnis)
frontend/   React SPA tunggal (admin & internal)
mobile/     Flutter app internal staff (butuh `flutter create .` untuk build)
deploy/     Caddyfile, skrip backup/restore produksi
docs/       PRD, vision, roadmap, standar engineering, panduan deployment
scripts/    Skrip operasional
```

Menambah modul domain baru: copy pola dari `backend/app/modules/presales`
(`models.py → schemas.py → service.py → router.py`), daftarkan router di
`backend/app/main.py`, tambahkan model ke `alembic/env.py` target metadata.

## Portal self-service karyawan

Karyawan dengan akun role `karyawan` (dibuat admin lewat menu Pengguna,
kemudian ditautkan HR di halaman Karyawan) mendapat akses **Portal Saya**:
profil & dokumen pribadi, kontrak kerja, slip gaji yang sudah difinalisasi,
rekap kehadiran, pengajuan cuti/izin (dengan approval HR), dan ganti password.
Endpoint-nya ada di modul `backend/app/modules/ess` (`/api/v1/me/*`) dan hanya
melayani data milik akun yang sedang login.
