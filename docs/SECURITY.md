# Catatan Keamanan

Ringkasan lapisan keamanan aplikasi dan cara memverifikasinya.

## Lapisan isolasi multi-tenant

1. **Filter ORM otomatis** (`app/core/tenancy.py`) — setiap select disuntik
   `WHERE tenant_id = :current` via `with_loader_criteria`; setiap insert
   baru diinjeksi tenant dari konteks JWT.
2. **Row Level Security (PostgreSQL)** — lapisan kedua di database:
   policy `tenant_isolation` pada 20 tabel bisnis membandingkan
   `tenant_id` baris dengan `current_setting('app.current_tenant', true)`
   yang disetel **per transaksi** oleh listener SQLAlchemy (`set_config`).
   - Efektif hanya jika backend connect sebagai role **bukan pemilik tabel**
     → produksi memakai role `aeos_app` (dibuat `deploy/pg/init-roles.sh`);
     migrasi tetap berjalan sebagai role owner (`POSTGRES_USER`).
   - Platform admin & event pra-login menyet tenant kosong → RLS mengembalikan
     nol baris (sesuai desain).

### Verifikasi manual RLS (setelah deploy)

```bash
# Dari dalam container postgres, sebagai role aplikasi:
docker compose -f docker-compose.prod.yml exec postgres psql -U aeos_app -d aeos \
  -c "SELECT set_config('app.current_tenant','','true');
      SELECT count(*) FROM clients;"          # harus 0

docker compose ... psql -U aeos_app -d aeos \
  -c "SELECT set_config('app.current_tenant','<uuid-tenant>','true');
      SELECT count(*) FROM clients;"          # hanya milik tenant tsb
```

## Autentikasi

- **Rate limit login**: sliding window per proses — default 5 gagal /
  IP+email dan per IP dalam 300 detik → HTTP 429 + `Retry-After`.
  Batasan: counter in-process (tidak dibagi antar worker); untuk deployment
  besar pertimbangkan limiter terdistribusi (Redis).
- **Reset password v1** tanpa SMTP: admin membuat token satu kali pakai
  (`POST /auth/users/{id}/password-reset-token`, hash SHA-256 disimpan,
  TTL 30 menit) lalu meneruskannya ke user lewat kanal out-of-band;
  user menukar token di `POST /auth/reset-password` (rate limited per IP).
- **Ganti password mandiri**: `POST /auth/change-password` (wajib password lama).
- Semua event auth tercatat di jejak audit (`auth.login`,
  `auth.login_failed`, `auth.login_ratelimited`, `auth.password_changed`,
  `auth.password_reset_requested|completed`). Event pra-autentikasi yang
  emailnya tidak dikenal tidak berafiliasi tenant (by design).

## Kecualian dari RLS

`users`, `audit_logs`, `password_reset_tokens`, `tenants` tidak berpolicy
(kolom tenant nullable / data lintas tenant). Isolasinya tetap dijaga filter
ORM + guard role; akses langsung DB hanya untuk DBA.

## Backlog keamanan berikutnya

- Rate limiter terdistribusi (Redis) untuk multi-instance.
- Email SMTP nyata untuk reset password self-service.
- 2FA/TOTP untuk akun admin.
