#!/usr/bin/env sh
# Backup harian: dump PostgreSQL + mirror bucket MinIO ke folder backup host.
# Pemakaian: ./deploy/backup.sh [folder_backup]
# Disarankan lewat cron (lihat docs/DEPLOYMENT.md).

set -eu

BACKUP_ROOT="${1:-/var/backups/aeos}"
STAMP="$(date +%Y%m%d-%H%M%S)"
DIR="${BACKUP_ROOT}/${STAMP}"
KEEP_DAYS="${BACKUP_KEEP_DAYS:-14}"

mkdir -p "$DIR"

echo "[backup] PostgreSQL -> $DIR/postgres.dump"
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-aeos}" -Fc "${POSTGRES_DB:-aeos}" > "$DIR/postgres.dump"

echo "[backup] MinIO bucket ${STORAGE_BUCKET:-documents} -> $DIR/minio/"
mkdir -p "$DIR/minio"
docker compose -f docker-compose.prod.yml exec -T minio sh -c \
  "mc alias set local http://127.0.0.1:9000 \"\$MINIO_ROOT_USER\" \"\$MINIO_ROOT_PASSWORD\" >/dev/null && \
   mc mirror --overwrite \"local/${STORAGE_BUCKET:-documents}\" /mirror/" || true
docker compose -f docker-compose.prod.yml cp minio:/mirror/. "$DIR/minio/"
docker compose -f docker-compose.prod.yml exec -T minio rm -rf /mirror || true

# Rotasi: hapus backup lebih tua dari KEEP_DAYS hari
find "$BACKUP_ROOT" -maxdepth 1 -type d -name '20*' -mtime +"$KEEP_DAYS" -exec rm -rf {} \; || true

echo "[backup] selesai: $DIR"
