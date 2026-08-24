# Panduan Deployment Produksi

Target arsitektur: satu VPS (2 vCPU / 4 GB RAM cukup untuk mulai) menjalankan
Docker Compose dengan **Caddy** (TLS otomatis Let's Encrypt) → frontend statis
(nginx) + backend (uvicorn) → PostgreSQL & MinIO internal.

```
Internet ──> :80/:443 Caddy ──┬── /api/*  ──> backend:8000 (uvicorn)
                              └── lainnya    ──> frontend:80 (SPA)
backend ──> postgres (volume pgdata) ; minio (volume minio)
```

## 1. Prasyarat

1. VPS Ubuntu 22.04+/Debian 12 dengan Docker Engine + compose plugin:
   `curl -fsSL https://get.docker.com | sh`
2. DNS: A record `aeos.example.com` → IP publik VPS.
3. Port 80 & 443 terbuka; port database/storage TIDAK diekspos.
4. Repo di-clone ke server, mis. `/opt/ai-enterprise-os`.

## 2. Konfigurasi

```bash
cp .env.production.example .env.production
# WAJIB diisi: SECRET_KEY, ADMIN_PASSWORD, POSTGRES_PASSWORD,
# STORAGE_ACCESS_KEY/SECRET_KEY, PLATFORM_ADMIN_PASSWORD, DOMAIN, CORS_ORIGINS
nano .env.production
chmod 600 .env.production
```

Generate secret:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

`CORS_ORIGINS` harus persis `https://<DOMAIN>` (tanpa trailing slash).

## 3. Deploy pertama

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production build
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

Backend otomatis: `scripts/migrate.py` (alembic upgrade / stamp head) →
bootstrap (tenant default + admin dari env) → uvicorn.

Verifikasi:

```bash
curl -s https://<DOMAIN>/health/live          # {"status":"ok"}
docker compose -f docker-compose.prod.yml ps   # semua healthy/up
docker compose -f docker-compose.prod.yml logs -f backend
```

Login pertama di `https://<DOMAIN>` memakai `ADMIN_EMAIL`/`ADMIN_PASSWORD`.
Buat user tim lewat menu Pengguna; provisioning tenant baru via
`POST /api/v1/platform/tenants` (akun platform admin).

## 4. Update rilis

```bash
git pull
docker compose -f docker-compose.prod.yml --env-file .env.production build
docker compose -f docker-compose.prod.yml --env-file .env.production up -d
```

Entrypoint migrasi bersifat idempoten — versi lama yang belum pernah pakai
Alembic akan di-stamp `head` otomatis sebelum upgrade.

Rollback aplikasi (tanpa DB): checkout tag sebelumnya lalu ulangi build+up.
Rollback skema: `docker compose ... run --rm backend alembic downgrade <rev>`
(**backup dulu**).

## 5. Backup harian

Cron (sebagai root):

```cron
0 2 * * * cd /opt/ai-enterprise-os && POSTGRES_USER=... POSTGRES_DB=... STORAGE_BUCKET=... ./deploy/backup.sh >> /var/log/aeos-backup.log 2>&1
```

Isi folder backup per timestamp: `postgres.dump` (format custom,
`pg_restore`) + salinan bucket MinIO. Retensi default 14 hari
(`BACKUP_KEEP_DAYS`).

Uji restore berkala (disarangan bulanan):

```bash
./deploy/restore.sh /var/backups/aeos/<timestamp>
```

## 6. Catatan operasional

- **Skema**: sumber kebenaran = Alembic. Di production `create_all`
  sengaja dimatikan; bootstrap data awal dilindungi advisory lock agar aman
  untuk beberapa worker uvicorn.
- **File**: dokumen tersimpan di MinIO (bucket `documents`). Mode disk lokal
  tetap bisa dipakai (kosongkan `STORAGE_*`) dengan menambah volume untuk
  `<DATA_DIR>/uploads` pada service backend — tapi MinIO direkomendasikan.
- **AI/TTE**: fitur nonaktif sampai `AI_BASE_URL` / `ESIGN_PROVIDER=privy`
  diisi. Webhook TTE membutuhkan URL publik:
  `https://<DOMAIN>/api/v1/esign/webhook`.
- **Rate limit login / reset password**: belum ada (backlog keamanan).
