#!/usr/bin/env sh
# Restore dari satu folder hasil backup.sh.
# PEMAKAIAN: ./deploy/restore.sh <folder_backup>
# PERINGATAN: menimpa data yang ada saat ini. Jalankan saat insiden saja.

set -eu

DIR="${1:?Pemakaian: restore.sh <folder_backup>}"
[ -f "$DIR/postgres.dump" ] || { echo "postgres.dump tidak ditemukan di $DIR"; exit 1; }

echo "[restore] Menghentikan backend sementara..."
docker compose -f docker-compose.prod.yml stop backend

echo "[restore] PostgreSQL <- $DIR/postgres.dump"
docker compose -f docker-compose.prod.yml exec -T postgres sh -c \
  "pkill -f 'postgres:.*aeos' 2>/dev/null; exit 0" || true
sleep 3
docker compose -f docker-compose.prod.yml exec -T postgres \
  env PGUSER="${POSTGRES_USER:-aeos}" PGDATABASE="${POSTGRES_DB:-aeos}" \
  pg_restore --clean --if-exists -U "${POSTGRES_USER:-aeos}" -d "${POSTGRES_DB:-aeos}" \
  < "$DIR/postgres.dump"

if [ -d "$DIR/minio" ]; then
  echo "[restore] MinIO <- $DIR/minio/"
  docker compose -f docker-compose.prod.yml cp "$DIR/minio/." minio:/mirror/
  docker compose -f docker-compose.prod.yml exec -T minio sh -c \
    "mc alias set local http://127.0.0.1:9000 \"\$MINIO_ROOT_USER\" \"\$MINIO_ROOT_PASSWORD\" >/dev/null && \
     mc mirror --overwrite /mirror/ \"local/${STORAGE_BUCKET:-documents}\" && rm -rf /mirror"
fi

echo "[restore] Menjalankan migrasi & menyalakan kembali backend..."
docker compose -f docker-compose.prod.yml up -d backend
docker compose -f docker-compose.prod.yml exec -T backend python scripts/migrate.py

echo "[restore] selesai."
