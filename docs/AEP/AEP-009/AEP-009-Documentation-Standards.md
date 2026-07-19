# AEP-009 — Documentation Standards

**Version:** 1.0 (Draft)  
**Status:** Core Engineering Standard

---

# 1. Purpose

Dokumen ini menetapkan standar dokumentasi untuk seluruh proyek di bawah AI Engineering Playbook (AEP).

Tujuan utama:

* Menjadikan dokumentasi sebagai sumber kebenaran (Single Source of Truth).
* Mempercepat onboarding engineer dan AI agent.
* Mendukung pemeliharaan jangka panjang.
* Meningkatkan keterlacakan keputusan teknis.
* Memastikan setiap perubahan terdokumentasi dengan baik.

Dokumentasi adalah bagian dari produk, bukan pekerjaan tambahan setelah implementasi selesai.

---

# 2. Documentation Principles

Seluruh dokumentasi mengikuti prinsip:

* Documentation by Default.
* Single Source of Truth.
* Keep It Current.
* Audience First.
* Searchable.
* Version Controlled.
* Reviewable.
* AI Readable.

---

# 3. Documentation Categories

Setiap proyek dapat memiliki kategori berikut:

* Product Documentation
* Architecture Documentation
* API Documentation
* Engineering Documentation
* Operations Documentation
* Security Documentation
* AI Documentation
* User Documentation
* Developer Documentation

Setiap dokumen harus memiliki tujuan yang jelas.

---

# 4. Required Documents

Minimal setiap proyek memiliki:

* README.md
* CHANGELOG.md
* CONTRIBUTING.md
* LICENSE
* SECURITY.md

Untuk proyek produksi juga direkomendasikan:

* Architecture Overview
* ADR (Architecture Decision Records)
* Deployment Guide
* Runbook
* Troubleshooting Guide

---

# 5. README Standard

README wajib memuat:

* Ringkasan proyek.
* Tujuan bisnis.
* Fitur utama.
* Arsitektur singkat.
* Teknologi yang digunakan.
* Cara instalasi.
* Cara menjalankan.
* Cara pengujian.
* Struktur proyek.
* Referensi dokumentasi lanjutan.

README harus dapat dipahami oleh engineer baru tanpa penjelasan tambahan.

---

# 6. Architecture Documentation

Dokumentasi arsitektur minimal mencakup:

* Diagram konteks.
* Diagram komponen.
* Diagram alur data.
* Batas domain.
* Integrasi eksternal.
* Keputusan desain utama.

Diagram harus disimpan dalam format yang dapat diperbarui (misalnya Mermaid atau PlantUML) selain gambar hasil render jika diperlukan.

---

# 7. API Documentation

Seluruh API harus memiliki dokumentasi yang mencakup:

* Endpoint.
* Parameter.
* Request.
* Response.
* Status Code.
* Authentication.
* Error Response.
* Contoh penggunaan.

OpenAPI menjadi kontrak resmi untuk layanan HTTP yang mendukungnya.

---

# 8. Architecture Decision Records (ADR)

Keputusan penting harus didokumentasikan sebagai ADR.

Minimal memuat:

* Konteks.
* Permasalahan.
* Alternatif.
* Keputusan.
* Konsekuensi.
* Tanggal.
* Status.

ADR tidak diubah untuk menulis ulang sejarah; gunakan ADR baru jika keputusan berubah.

---

# 9. Code Documentation

Dokumentasikan:

* API publik.
* Algoritma kompleks.
* Asumsi penting.
* Kontrak antarmuka.

Komentar digunakan untuk menjelaskan *mengapa*, bukan mengulang *apa* yang sudah jelas dari kode.

---

# 10. AI Documentation

Jika proyek menggunakan AI, dokumentasikan:

* Model yang digunakan.
* Prompt atau konfigurasi utama.
* Sumber konteks.
* Mekanisme evaluasi.
* Guardrails.
* Batasan sistem.
* Pertimbangan etika dan risiko.

---

# 11. Operations Documentation

Dokumentasi operasional mencakup:

* Deployment.
* Konfigurasi.
* Monitoring.
* Alerting.
* Backup.
* Recovery.
* Scaling.
* Incident Response.

Runbook harus dapat diikuti oleh engineer yang belum pernah mengoperasikan sistem tersebut.

---

# 12. Security Documentation

Dokumentasikan:

* Mekanisme autentikasi.
* Otorisasi.
* Pengelolaan secret.
* Kebijakan rotasi kredensial.
* Model ancaman (bila relevan).
* Prosedur pelaporan kerentanan.

Informasi sensitif tidak boleh dimasukkan ke dokumentasi publik.

---

# 13. Versioning

Dokumentasi harus memiliki:

* Nomor versi (bila sesuai).
* Tanggal pembaruan.
* Riwayat perubahan untuk dokumen penting.
* Status (Draft, Review, Approved, Deprecated).

Dokumentasi mengikuti perubahan produk.

---

# 14. Documentation Review

Dokumentasi ditinjau bersama perubahan kode.

Reviewer memastikan:

* Akurat.
* Mutakhir.
* Konsisten.
* Mudah dipahami.
* Tidak bertentangan dengan standar AEP.

---

# 15. AI Coding Agent Rules

AI Coding Agent wajib:

* Memperbarui dokumentasi yang terdampak.
* Menambahkan contoh penggunaan bila antarmuka berubah.
* Memperbarui diagram atau referensi jika struktur berubah.
* Menandai asumsi penting.
* Tidak menghasilkan dokumentasi yang bertentangan dengan implementasi.

---

# 16. Anti-Patterns

Tidak diperbolehkan:

* Dokumentasi yang tidak pernah diperbarui.
* README kosong.
* Diagram yang tidak sesuai implementasi.
* Dokumentasi hasil salin-tempel tanpa penyesuaian.
* Dokumentasi yang menggantikan kode yang jelas.
* Menyimpan keputusan penting hanya di percakapan atau pesan instan.

---

# 17. Documentation Review Checklist

Reviewer memastikan:

* Seluruh dokumen wajib tersedia.
* README lengkap.
* API terdokumentasi.
* ADR tersedia untuk keputusan penting.
* Dokumentasi AI diperbarui bila relevan.
* Tidak ada informasi sensitif.
* Tautan internal berfungsi.

---

# 18. Production Documentation Checklist

Sebelum rilis:

* README diperbarui.
* CHANGELOG diperbarui.
* Dokumentasi deployment selesai.
* Runbook tersedia.
* Troubleshooting guide tersedia.
* Dokumentasi keamanan diperbarui.
* Diagram arsitektur sesuai implementasi.
* API documentation sinkron dengan kode.

---

# 19. Compliance

Seluruh proyek wajib memenuhi standar dokumentasi AEP-009.

Pengecualian harus didokumentasikan melalui Architecture Decision Record (ADR).

---

# 20. Future Extensions

Standar ini akan diperluas menjadi:

* **AEP-009-ADR** — Architecture Decision Record Standards.
* **AEP-009-API** — API Documentation Standards.
* **AEP-009-RUNBOOK** — Operations Runbook Standards.
* **AEP-009-SEC** — Security Documentation Standards.
* **AEP-009-AI** — AI Documentation Standards.
* **AEP-009-DIAGRAM** — Diagram & Modeling Standards.
* **AEP-009-KNOWLEDGE** — Knowledge Base Standards.
