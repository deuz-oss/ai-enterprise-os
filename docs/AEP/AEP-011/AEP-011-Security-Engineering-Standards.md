# AEP-011 — Security Engineering Standards

**Version:** 1.0 (Draft)  
**Status:** Core Engineering Standard

---

# 1. Purpose

Dokumen ini menetapkan standar keamanan untuk seluruh proyek di bawah AI Engineering Playbook (AEP).

Tujuan utama:

* Melindungi data.
* Mengurangi risiko keamanan.
* Membangun sistem yang aman sejak awal.
* Mendukung kepatuhan terhadap regulasi.
* Menjamin keamanan sistem AI maupun non-AI.

Security merupakan tanggung jawab seluruh tim engineering.

---

# 2. Security Principles

Seluruh sistem mengikuti prinsip:

* Security by Design.
* Secure by Default.
* Least Privilege.
* Defense in Depth.
* Zero Trust.
* Fail Secure.
* Privacy by Design.
* Continuous Verification.

---

# 3. Secure Software Development Lifecycle (SSDLC)

Keamanan diterapkan pada setiap tahap:

```text id="ssdlcflow"
Requirements
↓
Architecture
↓
Implementation
↓
Testing
↓
Deployment
↓
Operations
↓
Continuous Improvement
```

Tidak ada tahap yang boleh mengabaikan keamanan.

---

# 4. Identity & Access Management

Seluruh sistem wajib:

* Authentication yang kuat.
* Authorization berbasis peran atau kebijakan.
* Session management yang aman.
* Audit terhadap perubahan hak akses.

Hak akses diberikan berdasarkan kebutuhan pekerjaan.

---

# 5. Secrets Management

Secret meliputi:

* Password.
* API Key.
* Token.
* Certificate.
* Encryption Key.

Aturan:

* Jangan simpan secret di source code.
* Jangan simpan secret di repository.
* Gunakan Secret Manager atau mekanisme yang setara.
* Lakukan rotasi secret secara berkala.

---

# 6. Data Protection

Data harus diklasifikasikan sesuai tingkat sensitivitas.

Minimal:

* Public.
* Internal.
* Confidential.
* Restricted.

Proteksi diterapkan sesuai klasifikasi.

---

# 7. Encryption

Wajib:

* Enkripsi data saat transit.
* Enkripsi data saat disimpan jika diperlukan oleh tingkat risiko atau regulasi.
* Pengelolaan kunci yang aman.
* Rotasi kunci sesuai kebijakan.

Jangan membuat algoritma kriptografi sendiri.

---

# 8. Input Validation

Seluruh input eksternal wajib divalidasi.

Lindungi dari:

* Injection.
* Path traversal.
* Invalid format.
* Oversized payload.

Validasi dilakukan di sisi server, meskipun frontend juga melakukan validasi.

---

# 9. Dependency Security

Seluruh dependency harus:

* Dipindai secara berkala.
* Memiliki lisensi yang sesuai.
* Tidak memiliki kerentanan kritis yang belum ditangani.
* Diperbarui sesuai kebijakan organisasi.

---

# 10. Logging & Auditing

Seluruh sistem harus memiliki:

* Audit log untuk aktivitas penting.
* Structured logging.
* Korelasi request.
* Retensi log sesuai kebijakan.

Jangan mencatat password, token, atau informasi sensitif lain dalam log.

---

# 11. API Security

Seluruh API wajib:

* Menggunakan autentikasi yang sesuai.
* Memvalidasi otorisasi.
* Menggunakan HTTPS.
* Memiliki rate limiting bila diperlukan.
* Mengembalikan pesan kesalahan yang aman.

---

# 12. Infrastructure Security

Lingkungan infrastruktur harus:

* Menggunakan konfigurasi yang terdokumentasi.
* Menerapkan prinsip least privilege.
* Memisahkan lingkungan development, staging, dan production.
* Memiliki proses patch management.

---

# 13. Secure Configuration

Konfigurasi produksi harus:

* Menonaktifkan mode debug.
* Menggunakan konfigurasi yang terdokumentasi.
* Memiliki baseline keamanan.
* Diverifikasi sebelum rilis.

---

# 14. AI Security

Untuk sistem AI:

* Lindungi prompt produksi.
* Validasi sumber konteks.
* Terapkan guardrails.
* Pantau prompt injection.
* Evaluasi kebocoran data.
* Dokumentasikan batasan model.

---

# 15. Incident Response

Organisasi harus memiliki prosedur untuk:

* Deteksi.
* Analisis.
* Isolasi.
* Pemulihan.
* Post-incident review.

Setiap insiden menjadi masukan untuk peningkatan sistem.

---

# 16. Vulnerability Management

Kerentanan harus:

* Dicatat.
* Dinilai tingkat risikonya.
* Diprioritaskan.
* Diperbaiki.
* Diverifikasi setelah perbaikan.

---

# 17. AI Coding Agent Rules

AI Coding Agent wajib:

* Tidak menghasilkan hardcoded secret.
* Menggunakan praktik keamanan yang sesuai dengan AEP.
* Menyarankan validasi input.
* Menggunakan library kriptografi yang tepercaya.
* Menambahkan pengujian keamanan bila relevan.
* Menandai asumsi keamanan yang dibuat.

---

# 18. Security Review Checklist

Reviewer memastikan:

* Tidak ada secret di repository.
* Validasi input memadai.
* Hak akses sesuai kebutuhan.
* Dependency telah diperiksa.
* Logging tidak membocorkan data sensitif.
* Konfigurasi produksi aman.
* Kepatuhan terhadap AEP-011.

---

# 19. Production Security Checklist

Sebelum rilis:

* Security scan lulus.
* Dependency scan lulus.
* Secret scan lulus.
* Konfigurasi diverifikasi.
* HTTPS diterapkan.
* Audit logging aktif.
* Backup dan recovery diverifikasi.
* Risiko residual didokumentasikan.

---

# 20. Compliance

Seluruh proyek wajib mematuhi AEP-011.

Pengecualian hanya diperbolehkan melalui Architecture Decision Record (ADR) dan persetujuan governance yang berlaku.

---

# 21. Future Extensions

Standar ini akan diperluas menjadi:

* **AEP-011-APPSEC** — Application Security Standards.
* **AEP-011-INFRA** — Infrastructure Security Standards.
* **AEP-011-IDENTITY** — Identity & Access Management Standards.
* **AEP-011-SECRETS** — Secrets Management Standards.
* **AEP-011-AISEC** — AI Security Standards.
* **AEP-011-THREAT** — Threat Modeling Standards.
* **AEP-011-INCIDENT** — Incident Response Standards.
