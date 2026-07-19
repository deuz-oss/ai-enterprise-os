# AEP-008 — Repository & Project Standards

**Version:** 1.0 (Draft)  
**Status:** Core Engineering Standard

---

# 1. Purpose

Dokumen ini menetapkan standar struktur repository, organisasi proyek, dan artefak wajib untuk seluruh proyek dalam AI Engineering Playbook (AEP).

Tujuan utama:

* Konsistensi lintas proyek.
* Onboarding yang cepat.
* Kolaborasi yang efisien.
* Otomatisasi CI/CD.
* Kemudahan pemeliharaan.
* Kesiapan produksi.

Setiap repository harus memiliki struktur yang dapat dipahami tanpa bergantung pada pengetahuan individu.

---

# 2. Repository Principles

Seluruh repository mengikuti prinsip:

* Single Source of Truth.
* Convention Over Configuration.
* Documentation by Default.
* Automation by Default.
* Security by Default.
* Reproducibility.
* Discoverability.

---

# 3. Repository Types

Kategori repository:

* Product Repository
* Service Repository
* Shared Library
* SDK
* Infrastructure Repository
* AI Model Repository
* Prompt Repository
* Documentation Repository
* Design System Repository

Setiap repository harus memiliki satu tujuan utama.

---

# 4. Standard Repository Structure

Struktur minimum:

```text
repository/
├── .github/
│ ├── workflows/
│ ├── ISSUE_TEMPLATE/
│ └── PULL_REQUEST_TEMPLATE.md
├── docs/
├── src/
├── tests/
├── scripts/
├── infra/
├── examples/
├── .editorconfig
├── .gitignore
├── .env.example
├── LICENSE
├── README.md
├── CHANGELOG.md
├── CONTRIBUTING.md
├── CODEOWNERS
└── SECURITY.md
```

Dokumen atau folder yang tidak relevan untuk jenis repository tertentu dapat dihilangkan, tetapi alasannya harus jelas.

---

# 5. README Standard

README minimal memuat:

* Ringkasan proyek.
* Tujuan.
* Arsitektur singkat.
* Prasyarat.
* Cara instalasi.
* Cara menjalankan.
* Cara pengujian.
* Struktur proyek.
* Cara berkontribusi.
* Lisensi.

README adalah pintu masuk utama bagi engineer dan AI agent.

---

# 6. Documentation

Folder `docs/` digunakan untuk:

* ADR (Architecture Decision Record).
* PRD.
* Diagram arsitektur.
* API.
* Deployment.
* Operasional.
* Troubleshooting.

Dokumentasi harus menggunakan Markdown dan mengikuti standar AEP.

---

# 7. Source Code

Seluruh source code berada pada folder yang telah ditetapkan (misalnya `src/`).

Hindari:

* Menyimpan source code di root repository.
* Struktur folder yang tidak konsisten.
* Folder generik seperti `misc` atau `temp`.

---

# 8. Testing

Folder `tests/` mencakup:

* Unit Test.
* Integration Test.
* End-to-End Test (jika relevan).
* Test Fixtures.
* Test Utilities.

Pengujian tidak boleh bercampur dengan kode produksi kecuali konvensi bahasa/framework memang mengharuskannya.

---

# 9. Scripts

Folder `scripts/` digunakan untuk:

* Setup.
* Build.
* Migrasi.
* Utilitas.
* Otomatisasi.

Script harus idempotent bila memungkinkan dan terdokumentasi.

---

# 10. Infrastructure

Folder `infra/` berisi artefak infrastruktur seperti:

* Docker.
* Kubernetes.
* Terraform.
* Helm.
* Konfigurasi deployment.

Konfigurasi lingkungan produksi tidak boleh berisi secret.

---

# 11. Branch Strategy

Minimal:

* `main` untuk kode produksi.
* `develop` bila organisasi menggunakan model GitFlow.
* Feature branch.
* Hotfix branch.
* Release branch (opsional).

Branch harus memiliki nama yang konsisten, misalnya:

```text
feature/user-authentication
bugfix/payment-timeout
hotfix/login-error
```

---

# 12. Commit Standards

Gunakan format commit yang konsisten, misalnya:

```text
feat:
fix:
docs:
refactor:
test:
perf:
build:
ci:
chore:
```

Setiap commit harus mewakili satu perubahan logis.

---

# 13. Pull Request Standards

Setiap Pull Request wajib memuat:

* Ringkasan perubahan.
* Alasan perubahan.
* Dampak.
* Cara pengujian.
* Risiko.
* Referensi issue atau ADR bila ada.

PR yang besar sebaiknya dipecah menjadi beberapa perubahan yang lebih kecil.

---

# 14. CI/CD Requirements

Setiap repository harus memiliki pipeline otomatis untuk:

* Build.
* Lint.
* Format.
* Type checking (jika relevan).
* Unit test.
* Security scanning.
* Dependency scanning.

Rilis tidak boleh bergantung pada langkah manual yang tidak terdokumentasi.

---

# 15. Versioning

Gunakan Semantic Versioning:

```text
MAJOR.MINOR.PATCH
```

Perubahan yang memutus kompatibilitas harus menaikkan versi mayor.

---

# 16. Dependency Management

Semua dependency harus:

* Memiliki lisensi yang sesuai.
* Dipelihara.
* Ditinjau secara berkala.
* Diperbarui sesuai kebijakan organisasi.

Dependency yang tidak digunakan harus dihapus.

---

# 17. Security

Repository wajib memiliki:

* SECURITY.md.
* Kebijakan pelaporan kerentanan.
* Secret scanning.
* Dependency scanning.

Secret tidak boleh disimpan di repository.

---

# 18. AI Artifacts

Jika repository menggunakan AI, sediakan struktur yang jelas, misalnya:

```text
ai/
├── prompts/
├── evaluations/
├── datasets/
├── agents/
└── guardrails/
```

Prompt, evaluasi, dan konfigurasi AI diperlakukan sebagai artefak versi.

---

# 19. Code Ownership

Gunakan `CODEOWNERS` untuk menentukan penanggung jawab area kode tertentu.

Perubahan pada area kritis harus ditinjau oleh pemilik yang ditetapkan.

---

# 20. AI Coding Agent Rules

AI Coding Agent wajib:

* Mematuhi struktur repository.
* Tidak membuat folder baru tanpa alasan yang jelas.
* Memperbarui dokumentasi bila struktur berubah.
* Menambahkan pengujian yang relevan.
* Mengikuti standar commit dan PR proyek.

---

# 21. Repository Review Checklist

Reviewer memastikan:

* Struktur sesuai AEP-008.
* Dokumentasi lengkap.
* Pengujian tersedia.
* Pipeline otomatis berjalan.
* Tidak ada secret.
* Struktur folder konsisten.
* Kepemilikan kode jelas.

---

# 22. Production Readiness Checklist

Repository dianggap siap produksi apabila:

* Struktur sesuai standar.
* README lengkap.
* Dokumentasi tersedia.
* CI/CD aktif.
* Pengujian otomatis lulus.
* Security scan lulus.
* Dependency diperiksa.
* Versioning diterapkan.

---

# 23. Compliance

Seluruh repository organisasi wajib mematuhi AEP-008.

Pengecualian harus didokumentasikan melalui Architecture Decision Record (ADR).

---

# 24. Future Extensions

Standar ini akan diperluas menjadi:

* **AEP-008-GIT** — Git Workflow Standards.
* **AEP-008-CI** — Continuous Integration Standards.
* **AEP-008-CD** — Continuous Delivery Standards.
* **AEP-008-DOCS** — Repository Documentation Standards.
* **AEP-008-MONO** — Monorepo Standards.
* **AEP-008-OSS** — Open Source Repository Standards.
* **AEP-008-AI** — AI Repository Standards.
