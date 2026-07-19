# AEP-007-PROMPT — AI Interaction & Prompt Engineering Standards

**Version:** 1.0 (Draft)  
**Status:** AI Engineering Standard  
**Parent:** AEP-007 — Universal Coding Standards

---

# 1. Purpose

Dokumen ini menetapkan standar komunikasi antara manusia, AI Coding Agent, AI Review Agent, AI Architect, dan AI Assistant dalam seluruh proyek di bawah AI Engineering Playbook (AEP).

Tujuan utama:

* Menghasilkan output AI yang konsisten.
* Mengurangi ambiguitas.
* Meningkatkan akurasi.
* Mempermudah otomatisasi.
* Menjamin keterlacakan keputusan.

Prompt diperlakukan sebagai artefak engineering yang memiliki nilai, versi, dan siklus hidup.

---

# 2. AI Interaction Philosophy

Seluruh interaksi dengan AI mengikuti prinsip:

* Clarity Before Cleverness.
* Context Before Instruction.
* Constraints Before Freedom.
* Reproducibility Over Creativity.
* Verification Before Acceptance.
* Human Accountability.
* Documentation by Default.

AI adalah kolaborator engineering, bukan sumber kebenaran mutlak.

---

# 3. Prompt Lifecycle

Setiap prompt memiliki siklus hidup:

```text
Draft
↓
Review
↓
Approved
↓
Versioned
↓
Production
↓
Monitoring
↓
Improvement
```

Prompt yang digunakan dalam produksi wajib memiliki versi dan riwayat perubahan.

---

# 4. Prompt Structure Standard

Prompt enterprise mengikuti urutan berikut:

1. Objective
2. Context
3. Role
4. Inputs
5. Constraints
6. Expected Output
7. Acceptance Criteria
8. Examples (bila diperlukan)

Contoh:

```text
Objective:
Implementasikan endpoint login.

Context:
Aplikasi menggunakan FastAPI, PostgreSQL, JWT, dan AEP-007-FASTAPI.

Role:
Senior Backend Engineer.

Constraints:
- Gunakan dependency injection.
- Gunakan Pydantic.
- Tambahkan unit test.
- Jangan mengubah API publik lain.

Expected Output:
Kode lengkap beserta pengujian.

Acceptance Criteria:
Seluruh test lulus dan endpoint terdokumentasi.
```

---

# 5. Context Management

Prompt harus menyediakan konteks yang cukup.

Prioritas konteks:

1. Tujuan bisnis.
2. Arsitektur.
3. Standar AEP.
4. Kode terkait.
5. Batasan teknis.
6. Kriteria keberhasilan.

Jangan mengandalkan AI untuk menebak konteks yang penting.

---

# 6. Role Definition

Selalu tetapkan peran AI.

Contoh:

* Product Manager
* Principal Architect
* Staff Backend Engineer
* Security Engineer
* QA Engineer
* Technical Writer
* DevOps Engineer

Peran menentukan perspektif, bukan tingkat kewenangan.

---

# 7. Constraints

Seluruh batasan harus eksplisit.

Contoh:

* Gunakan Python.
* Gunakan FastAPI.
* Ikuti AEP-007-PY.
* Ikuti AEP-007-FASTAPI.
* Jangan menambah dependency baru.
* Pertahankan backward compatibility.

---

# 8. Output Specification

Output harus memiliki format yang jelas.

Contoh:

* Source code.
* Markdown.
* JSON.
* ADR.
* PRD.
* SQL migration.
* Test cases.
* Release notes.

AI tidak boleh menentukan format output sendiri jika telah ditentukan.

---

# 9. Acceptance Criteria

Prompt harus mendefinisikan kapan hasil dianggap selesai.

Contoh:

* Lulus seluruh pengujian.
* Tidak ada error type checking.
* Dokumentasi diperbarui.
* Tidak ada perubahan API publik.
* Memenuhi standar AEP.

---

# 10. Prompt Versioning

Setiap prompt produksi harus memiliki:

* ID unik.
* Nomor versi.
* Pemilik.
* Tanggal perubahan.
* Riwayat revisi.
* Status.

Prompt diperlakukan seperti source code.

---

# 11. Prompt Library

Prompt disimpan berdasarkan kategori.

Contoh:

```text
product/
architecture/
backend/
frontend/
testing/
security/
documentation/
operations/
```

Seluruh prompt harus dapat ditemukan dan digunakan ulang.

---

# 12. Multi-Agent Collaboration

Prompt harus menjelaskan:

* Agent yang bertanggung jawab.
* Agent pendukung.
* Urutan pekerjaan.
* Artefak yang diteruskan.
* Titik review.

Contoh:

Product Agent
↓
Architect Agent
↓
Backend Agent
↓
QA Agent
↓
Security Agent
↓
Documentation Agent

---

# 13. Verification

Output AI harus diverifikasi.

Minimal:

* Review manusia untuk keputusan strategis.
* Pemeriksaan otomatis (lint, type check, test).
* Validasi terhadap standar AEP.
* Evaluasi keamanan bila relevan.

Output AI tidak boleh langsung masuk produksi tanpa proses verifikasi yang sesuai.

---

# 14. Security

Prompt tidak boleh:

* Meminta AI menyimpan secret.
* Menyertakan kredensial produksi.
* Meminta AI mengabaikan kontrol keamanan.
* Menginstruksikan AI melakukan tindakan yang melanggar kebijakan organisasi.

Informasi sensitif harus diperlakukan sesuai kebijakan keamanan AEP.

---

# 15. Anti-Patterns

Tidak diperbolehkan:

* Prompt tanpa tujuan.
* Prompt tanpa konteks.
* Instruksi yang saling bertentangan.
* Prompt yang meminta AI menebak kebutuhan.
* Prompt yang terlalu luas tanpa batasan.
* Menerima output AI tanpa validasi.

---

# 16. AI Coding Agent Rules

AI Coding Agent wajib:

* Meminta klarifikasi jika informasi penting tidak tersedia.
* Mengakui asumsi yang dibuat.
* Mengikuti seluruh standar AEP yang disebutkan.
* Menghasilkan output yang dapat ditinjau.
* Menjelaskan risiko atau trade-off bila ada.
* Tidak mengubah ruang lingkup tanpa instruksi.

---

# 17. Prompt Review Checklist

Reviewer memastikan:

* Tujuan jelas.
* Konteks memadai.
* Peran ditentukan.
* Batasan eksplisit.
* Format output jelas.
* Acceptance Criteria lengkap.
* Tidak mengandung informasi sensitif yang tidak semestinya.

---

# 18. Production Prompt Checklist

Sebelum prompt digunakan dalam workflow produksi:

* Memiliki ID dan versi.
* Telah diuji.
* Terdokumentasi.
* Memiliki pemilik.
* Memiliki riwayat perubahan.
* Selaras dengan standar AEP.
* Dapat direproduksi hasilnya dalam konteks yang sama.

---

# 19. Compliance

Seluruh prompt yang digunakan dalam AI Software Factory wajib mematuhi standar ini.

Pengecualian harus didokumentasikan dan disetujui melalui mekanisme governance yang berlaku.

---

# 20. Future Extensions

Standar ini akan diperluas menjadi:

* **AEP-007-PROMPT-CODE** — Coding Prompt Standards.
* **AEP-007-PROMPT-ARCH** — Architecture Prompt Standards.
* **AEP-007-PROMPT-PRD** — Product Requirements Prompt Standards.
* **AEP-007-PROMPT-REVIEW** — AI Code Review Standards.
* **AEP-007-PROMPT-EVAL** — AI Evaluation Standards.
* **AEP-007-PROMPT-AGENT** — Multi-Agent Orchestration Standards.
* **AEP-007-PROMPT-RAG** — Retrieval & Context Standards.
