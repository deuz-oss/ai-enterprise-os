# AEP-010 — Testing & Quality Assurance Standards

**Version:** 1.0 (Draft)  
**Status:** Core Engineering Standard

---

# 1. Purpose

Dokumen ini menetapkan standar pengujian dan jaminan kualitas (Quality Assurance) untuk seluruh proyek di bawah AI Engineering Playbook (AEP).

Tujuan utama:

* Mencegah regresi.
* Meningkatkan kepercayaan terhadap perubahan.
* Menjamin kualitas produk.
* Mendukung Continuous Integration dan Continuous Delivery.
* Memastikan output AI tervalidasi sebelum digunakan.

Pengujian adalah bagian dari proses pengembangan, bukan aktivitas setelah implementasi selesai.

---

# 2. Testing Principles

Seluruh pengujian mengikuti prinsip:

* Test Early.
* Test Automatically.
* Test Continuously.
* Test the Behavior.
* Keep Tests Deterministic.
* Fast Feedback.
* Quality Over Coverage.
* Risk-Based Testing.

---

# 3. Testing Strategy

Gunakan pendekatan berlapis:

```text id="testpyramid"
 End-to-End
 Integration Tests
 Component Tests
 Unit Tests
```

Prioritaskan:

1. Unit Test.
2. Integration Test.
3. End-to-End Test sesuai kebutuhan.

Jumlah pengujian yang lebih tinggi pada lapisan bawah akan memberikan umpan balik yang lebih cepat dan biaya pemeliharaan yang lebih rendah.

---

# 4. Test Categories

Kategori yang didukung:

* Unit Test
* Integration Test
* Component Test
* Contract Test
* API Test
* End-to-End Test
* Performance Test
* Load Test
* Stress Test
* Security Test
* Accessibility Test
* AI Evaluation Test

Tidak semua kategori wajib untuk setiap proyek, tetapi pemilihannya harus didasarkan pada risiko.

---

# 5. Unit Testing

Unit Test harus:

* Cepat.
* Terisolasi.
* Deterministik.
* Tidak bergantung pada jaringan atau layanan eksternal.

Satu unit test sebaiknya memverifikasi satu perilaku utama.

---

# 6. Integration Testing

Digunakan untuk memverifikasi interaksi antar komponen.

Contoh:

* API ↔ Database.
* Service ↔ Queue.
* Backend ↔ Object Storage.
* AI Service ↔ Vector Database.

Gunakan lingkungan pengujian yang dapat direproduksi.

---

# 7. API Testing

Seluruh API publik harus diuji untuk:

* Status code.
* Validasi input.
* Respons sukses.
* Respons error.
* Authentication.
* Authorization.
* Edge cases.

---

# 8. End-to-End Testing

E2E digunakan untuk memverifikasi alur bisnis utama.

Fokus pada:

* Critical User Journey.
* Login.
* Checkout.
* Pembayaran.
* Workflow utama.

Hindari menjadikan E2E sebagai satu-satunya bentuk pengujian.

---

# 9. Test Data

Gunakan data uji yang:

* Konsisten.
* Dapat direproduksi.
* Tidak mengandung data produksi.
* Mudah dipahami.

Data sensitif harus dianonimkan atau disintesis.

---

# 10. Test Environment

Lingkungan pengujian harus:

* Terkonfigurasi otomatis.
* Terisolasi dari produksi.
* Dapat dibuat ulang.
* Memiliki konfigurasi yang terdokumentasi.

---

# 11. Test Automation

Seluruh pengujian yang dapat diotomatisasi sebaiknya dijalankan melalui pipeline CI.

Minimal mencakup:

* Build.
* Lint.
* Type checking.
* Unit Test.
* Integration Test (sesuai proyek).
* Security scan.

---

# 12. Code Coverage

Code coverage digunakan sebagai indikator, bukan tujuan akhir.

Target coverage ditetapkan berdasarkan risiko dan kebutuhan proyek.

Coverage tinggi tidak menggantikan kualitas skenario pengujian.

---

# 13. Performance Testing

Lakukan pengujian performa untuk sistem yang memiliki persyaratan throughput atau latensi.

Ukur:

* Response time.
* Throughput.
* Resource usage.
* Error rate.

Optimasi dilakukan berdasarkan hasil pengukuran.

---

# 14. Security Testing

Minimal mencakup:

* Dependency scanning.
* Static analysis.
* Authentication test.
* Authorization test.
* Input validation test.

Kerentanan yang ditemukan harus diprioritaskan berdasarkan tingkat risikonya.

---

# 15. Accessibility Testing

Untuk aplikasi dengan antarmuka pengguna:

* Uji navigasi keyboard.
* Uji label formulir.
* Uji kontras warna.
* Uji elemen semantik.

Accessibility merupakan bagian dari kualitas produk.

---

# 16. AI Evaluation

Untuk sistem AI:

* Evaluasi akurasi.
* Evaluasi konsistensi.
* Evaluasi relevansi.
* Evaluasi hallucination.
* Evaluasi prompt regression.

Perubahan model atau prompt harus dievaluasi sebelum digunakan di produksi.

---

# 17. Bug Management

Setiap bug harus memiliki:

* Reproduksi yang jelas.
* Tingkat keparahan.
* Prioritas.
* Status.
* Pengujian regresi setelah diperbaiki.

Bug yang telah diperbaiki sebaiknya tidak muncul kembali.

---

# 18. AI Coding Agent Rules

AI Coding Agent wajib:

* Menambahkan pengujian untuk fitur baru.
* Menambahkan pengujian regresi saat memperbaiki bug.
* Tidak menghapus pengujian tanpa justifikasi.
* Memastikan seluruh pengujian yang relevan tetap lulus.
* Melaporkan asumsi atau keterbatasan yang memengaruhi hasil pengujian.

---

# 19. Test Review Checklist

Reviewer memastikan:

* Pengujian mencakup perilaku penting.
* Edge cases dipertimbangkan.
* Pengujian mudah dipahami.
* Tidak bergantung pada kondisi yang tidak stabil.
* Tidak ada pengujian yang rapuh (flaky) tanpa rencana perbaikan.

---

# 20. Production Readiness Checklist

Sebelum rilis:

* Seluruh pengujian wajib lulus.
* Tidak ada bug kritis yang belum ditangani.
* Pipeline CI berhasil.
* Pengujian keamanan selesai.
* Pengujian AI (jika relevan) selesai.
* Laporan hasil pengujian tersedia.

---

# 21. Metrics

Pantau metrik kualitas, antara lain:

* Test pass rate.
* Build success rate.
* Defect escape rate.
* Mean Time to Detect (MTTD).
* Mean Time to Recover (MTTR).
* Flaky test rate.
* Regression rate.

Metrik digunakan untuk perbaikan berkelanjutan, bukan untuk mengevaluasi individu.

---

# 22. Compliance

Seluruh proyek wajib mematuhi standar AEP-010.

Pengecualian harus didokumentasikan melalui Architecture Decision Record (ADR).

---

# 23. Future Extensions

Standar ini akan diperluas menjadi:

* **AEP-010-UNIT** — Unit Testing Standards.
* **AEP-010-INTEGRATION** — Integration Testing Standards.
* **AEP-010-E2E** — End-to-End Testing Standards.
* **AEP-010-PERF** — Performance Testing Standards.
* **AEP-010-SEC** — Security Testing Standards.
* **AEP-010-AI** — AI Evaluation Standards.
* **AEP-010-QA** — Quality Engineering Standards.
