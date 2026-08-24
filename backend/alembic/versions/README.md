Folder untuk file migrasi Alembic.

Migrasi baseline: `49123ed7cc98_baseline_skema_lengkap.py` (seluruh tabel Fase 1–6).

Cara pakai:

    cd backend
    alembic upgrade head                      # terapkan semua migrasi
    alembic downgrade base                    # kembalikan ke kosong

URL database diambil dari `ALEMBIC_DATABASE_URL`, lalu `DATABASE_URL`,
dan fallback ke SQLite lokal.

Cara membuat migrasi baru setelah mengubah model:

    cd backend
    alembic revision --autogenerate -m "deskripsi perubahan"
    # review hasilnya, lalu:
    alembic upgrade head

Catatan: pada mode dev, aplikasi tetap menjalankan `Base.metadata.create_all`
saat start (idempoten). Untuk production/PostgreSQL, gunakan `alembic upgrade head`.
