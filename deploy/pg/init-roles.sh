#!/bin/bash
# Dijalankan otomatis oleh image postgres SAAT PERTAMA KALI volume diinisialisasi.
# Membuat role aplikasi terpisah dari pemilik skema agar Row Level Security
# benar-benar berlaku untuk backend (pemilik tabel melewati RLS).
set -e

APP_ROLE="${APP_DB_USER:-aeos_app}"
APP_PASS="${APP_DB_PASSWORD:-}"
OWNER_ROLE="${POSTGRES_USER:-aeos}"

if [ -z "$APP_PASS" ]; then
  echo "[init-roles] APP_DB_PASSWORD kosong — role $APP_ROLE dibuat TANPA password (ubah manual!)." >&2
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$ BEGIN
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${APP_ROLE}') THEN
        CREATE ROLE ${APP_ROLE} LOGIN;
      END IF;
    END \$\$;
EOSQL
else
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$ BEGIN
      IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${APP_ROLE}') THEN
        CREATE ROLE ${APP_ROLE} LOGIN PASSWORD '${APP_PASS}';
      ELSE
        ALTER ROLE ${APP_ROLE} WITH LOGIN PASSWORD '${APP_PASS}';
      END IF;
    END \$\$;
EOSQL
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${APP_ROLE};
  GRANT USAGE ON SCHEMA public TO ${APP_ROLE};
  GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ${APP_ROLE};
  GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ${APP_ROLE};
  ALTER DEFAULT PRIVILEGES FOR ROLE "${OWNER_ROLE}" IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ${APP_ROLE};
  ALTER DEFAULT PRIVILEGES FOR ROLE "${OWNER_ROLE}" IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO ${APP_ROLE};
EOSQL

echo "[init-roles] role ${APP_ROLE} siap."
