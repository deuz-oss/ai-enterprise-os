# Folder Structure

```
ai-enterprise-os/
├── backend/                     # FastAPI modular monolith
│   ├── app/
│   │   ├── main.py              # App factory, router registry
│   │   ├── core/
│   │   │   ├── config.py        # Settings via env (pydantic-settings)
│   │   │   ├── database.py      # Engine, session, Base, get_db
│   │   │   ├── security.py      # Password hash, JWT, get_current_user
│   │   │   ├── storage.py       # MinIO/S3 client helper
│   │   │   └── bootstrap.py     # Seed admin awal
│   │   └── modules/
│   │       ├── auth/            # User, register/login (JWT)
│   │       ├── presales/        # Lead pipeline + aktivitas + funnel
│   │       ├── clients/         # Klien + dokumen legalitas
│   │       ├── recruitment/     # Job order, kandidat, placement
│   │       └── dashboard/       # Ringkasan angka lintas modul
│   ├── alembic/                 # Migrasi DB
│   ├── tests/                   # Pytest per modul
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/                    # React SPA (Vite + Tailwind)
│   └── src/
│       ├── api/                 # HTTP client + endpoint helpers
│       ├── components/          # Layout, tabel generik, form kecil
│       └── pages/               # Login, Dashboard, Leads, Clients,
│                                # JobOrders, Candidates
├── docs/                        # PRD, vision, roadmap, standar
├── scripts/                     # Skrip operasional
├── data/                        # Data runtime lokal (gitignored):
│                                #   data/aeos.db  → SQLite (mode lokal)
│                                #   data/uploads/ → dokumen & CV ter-upload
├── .vscode/                     # Konfigurasi VS Code (debug, ekstensi)
├── docker-compose.yml           # postgres, minio, backend, frontend
├── Makefile
└── pyproject.toml               # Konfigurasi tooling root (ruff/mypy/pytest)
```

## Konvensi

- Modul backend **hanya** diakses lintas modul melalui `service.py`.
- Endpoint selalu berawalan `/api/v1/<modul>` dan (kecuali auth/health) memerlukan JWT.
- Nama tabel: bentuk jamak snake_case (`legal_documents`, `job_orders`).
- Frontend: satu halaman = satu file di `src/pages`, komponen UI generik dipakai ulang.
