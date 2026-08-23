Folder untuk file migrasi Alembic.

Cara membuat migrasi pertama:

    cd backend
    alembic revision --autogenerate -m "initial schema"
    alembic upgrade head

Catatan: pada mode dev, tabel otomatis dibuat via `Base.metadata.create_all`
saat aplikasi start, sehingga migrasi opsional sampai production.
