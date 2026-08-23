# Contributing

## Workflow

1. Create a feature branch from `main`.
2. Keep changes scoped to one concern.
3. Run `make lint` and `make test` before opening a PR.
4. Open a pull request with notes on any architecture impact.

## Engineering standards

- Backend: tambahkan modul domain di `backend/app/modules/<nama>/` mengikuti pola
  `models.py → schemas.py → service.py → router.py` (contoh: `presales/`).
- Frontend: satu halaman = satu file di `frontend/src/pages/`; komponen generik
  ditaruh di `src/components/`.
- Endpoint baru wajib berada di bawah `/api/v1` dan (kecuali auth) terlindungi JWT.
- Tambahkan test untuk setiap perubahan perilaku (`backend/tests/`).

## Commit quality

- Use descriptive commit messages.
- Avoid unrelated file churn.
- Update documentation whenever structure or operations change.
