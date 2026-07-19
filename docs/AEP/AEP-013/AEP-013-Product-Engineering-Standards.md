# AEP-013 — Product Engineering Standards

**Version:** 1.0 (Draft)  
**Status:** Core Engineering Standard

---

# 1. Purpose

Dokumen ini menetapkan standar Product Engineering untuk seluruh produk yang dikembangkan di bawah AI Engineering Playbook (AEP).

Tujuan utama:

* Mengubah ide menjadi produk yang tervalidasi.
* Menyatukan Product, Design, Engineering, dan AI Agent dalam satu proses.
* Mengurangi pembangunan fitur yang tidak memberikan nilai.
* Memastikan setiap implementasi memiliki dasar bisnis yang jelas.

Product Engineering menghubungkan strategi bisnis dengan implementasi teknis.

---

# 2. Product Engineering Principles

Seluruh pengembangan produk mengikuti prinsip:

* Customer First.
* Problem Before Solution.
* Outcome Over Output.
* Data-Informed Decision Making.
* Continuous Discovery.
* Continuous Delivery.
* Small Iterations.
* AI-Assisted by Default.

---

# 3. Product Lifecycle

Setiap produk mengikuti siklus berikut:

```text id="product-lifecycle"
Vision
↓
Problem Discovery
↓
Opportunity Assessment
↓
Solution Discovery
↓
PRD
↓
Architecture
↓
Design
↓
Implementation
↓
Testing
↓
Release
↓
Learning
↓
Iteration
```

Setiap tahap menghasilkan artefak yang menjadi masukan bagi tahap berikutnya.

---

# 4. Product Vision

Setiap produk wajib memiliki:

* Vision Statement.
* Mission.
* Target Users.
* Business Goals.
* Success Metrics.
* Scope.
* Non-goals.

Visi menjadi acuan seluruh keputusan produk.

---

# 5. Problem Discovery

Sebelum menentukan solusi, identifikasi:

* Masalah utama.
* Dampak terhadap pengguna.
* Frekuensi masalah.
* Alternatif yang sudah ada.
* Akar penyebab.

Masalah harus divalidasi menggunakan data, observasi, atau umpan balik pengguna.

---

# 6. Opportunity Assessment

Evaluasi peluang berdasarkan:

* Nilai bisnis.
* Nilai pengguna.
* Risiko.
* Kompleksitas.
* Diferensiasi.
* Kesesuaian dengan strategi organisasi.

Tidak semua peluang layak diwujudkan.

---

# 7. Product Requirements Document (PRD)

Setiap fitur utama wajib memiliki PRD yang mencakup:

* Latar belakang.
* Tujuan.
* Ruang lingkup.
* Persona.
* User Stories.
* Functional Requirements.
* Non-Functional Requirements.
* Acceptance Criteria.
* Dependencies.
* Risiko.
* Metrik keberhasilan.

PRD menjadi kontrak antara Product dan Engineering.

---

# 8. User Stories

Format yang disarankan:

"As a <user>, I want <goal>, so that <benefit>."

Setiap user story harus:

* Independen.
* Bernilai.
* Dapat diperkirakan.
* Kecil.
* Dapat diuji.

---

# 9. Acceptance Criteria

Acceptance Criteria harus:

* Spesifik.
* Terukur.
* Dapat diuji.
* Tidak ambigu.

Setiap fitur harus memiliki kriteria penerimaan sebelum implementasi dimulai.

---

# 10. Backlog Management

Backlog harus:

* Diprioritaskan.
* Memiliki pemilik.
* Memiliki estimasi.
* Memiliki status.
* Ditinjau secara berkala.

Backlog adalah daftar pekerjaan yang hidup dan terus diperbarui.

---

# 11. Prioritization

Prioritas ditentukan berdasarkan:

* Nilai pengguna.
* Nilai bisnis.
* Risiko.
* Kompleksitas.
* Urgensi.
* Ketergantungan.

Metode penilaian harus konsisten dalam satu organisasi.

---

# 12. Product Metrics

Setiap produk harus memiliki metrik utama, seperti:

* Adoption.
* Activation.
* Retention.
* Conversion.
* Engagement.
* Revenue.
* Customer Satisfaction.
* Performance.

Metrik dipilih sesuai tujuan produk.

---

# 13. AI-Assisted Product Development

AI dapat membantu:

* Problem analysis.
* Market research.
* PRD drafting.
* User Story generation.
* Acceptance Criteria generation.
* Risk identification.
* Competitive analysis.
* Roadmap planning.

Keputusan akhir tetap berada pada manusia yang bertanggung jawab.

---

# 14. Cross-Functional Collaboration

Kolaborasi minimal melibatkan:

* Product Manager.
* UX Designer.
* Architect.
* Engineering.
* QA.
* Security.
* AI Agents.

Keputusan penting harus terdokumentasi.

---

# 15. Product Review

Sebelum implementasi dimulai, lakukan Product Review untuk memastikan:

* Masalah telah dipahami.
* Solusi relevan.
* PRD lengkap.
* Risiko diidentifikasi.
* Ketergantungan diketahui.
* Metrik keberhasilan ditetapkan.

---

# 16. AI Coding Agent Rules

AI Agent wajib:

* Tidak langsung menulis kode sebelum PRD tersedia atau ruang lingkup telah jelas.
* Meminta klarifikasi jika kebutuhan ambigu.
* Menghasilkan artefak sesuai standar AEP.
* Menandai asumsi yang dibuat.
* Menjaga keterlacakan antara kebutuhan dan implementasi.

---

# 17. Product Review Checklist

Reviewer memastikan:

* Visi jelas.
* Masalah tervalidasi.
* PRD lengkap.
* User Stories dapat diuji.
* Acceptance Criteria memadai.
* Prioritas sesuai.
* Metrik keberhasilan telah ditentukan.

---

# 18. Production Readiness Checklist

Sebelum implementasi:

* PRD disetujui.
* Arsitektur tersedia.
* UX/UI siap.
* Risiko utama ditangani.
* Backlog diprioritaskan.
* Metrik ditentukan.
* Ketergantungan dipahami.

---

# 19. Compliance

Seluruh proyek wajib mengikuti standar AEP-013 sebelum memasuki tahap implementasi.

Pengecualian harus didokumentasikan melalui Architecture Decision Record (ADR).

---

# 20. Future Extensions

Standar ini akan diperluas menjadi:

* **AEP-013-PRD** — Product Requirements Document Standards.
* **AEP-013-DISCOVERY** — Product Discovery Standards.
* **AEP-013-ROADMAP** — Roadmap & Planning Standards.
* **AEP-013-BACKLOG** — Backlog Management Standards.
* **AEP-013-METRICS** — Product Metrics Standards.
* **AEP-013-RESEARCH** — User Research Standards.
* **AEP-013-VALIDATION** — Product Validation Standards.
