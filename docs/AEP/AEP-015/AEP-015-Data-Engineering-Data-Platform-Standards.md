# AEP-015 — Data Engineering & Data Platform Standards

**Version:** 1.0 (Draft)  
**Status:** Core Engineering Standard

---

# 1. Purpose

Dokumen ini menetapkan standar Data Engineering dan Data Platform untuk seluruh proyek di bawah AI Engineering Playbook (AEP).

Tujuan utama:

* Menjamin kualitas data.
* Menyediakan fondasi data yang konsisten.
* Mendukung analitik, AI, dan operasional.
* Memastikan keamanan dan tata kelola data.
* Memungkinkan skalabilitas jangka panjang.

Data diperlakukan sebagai aset strategis organisasi.

---

# 2. Data Engineering Principles

Seluruh sistem data mengikuti prinsip:

* Data as a Product.
* Single Source of Truth.
* Schema Before Storage.
* Quality by Default.
* Security by Default.
* Metadata First.
* Lineage by Design.
* Automation First.

---

# 3. Data Lifecycle

Seluruh data mengikuti siklus berikut:

```text id="data-lifecycle"
Create
↓
Validate
↓
Store
↓
Process
↓
Serve
↓
Analyze
↓
Archive
↓
Delete
```

Setiap tahap harus memiliki pemilik dan kebijakan yang terdokumentasi.

---

# 4. Data Classification

Data diklasifikasikan minimal menjadi:

* Public
* Internal
* Confidential
* Restricted

Klasifikasi menentukan kebijakan akses, penyimpanan, enkripsi, dan retensi.

---

# 5. Data Modeling

Seluruh model data harus:

* Memiliki tujuan yang jelas.
* Dinormalisasi atau didenormalisasi sesuai kebutuhan.
* Menggunakan penamaan yang konsisten.
* Didokumentasikan.

Model konseptual, logis, dan fisik harus dapat ditelusuri keterkaitannya.

---

# 6. Database Standards

Pemilihan teknologi database didasarkan pada kebutuhan.

Kategori umum:

* Relational Database
* Document Database
* Key-Value Store
* Time-Series Database
* Graph Database
* Vector Database
* Object Storage

Tidak ada satu jenis database yang cocok untuk semua kebutuhan.

---

# 7. Data Quality

Minimal kualitas data mencakup:

* Accuracy.
* Completeness.
* Consistency.
* Timeliness.
* Validity.
* Uniqueness.

Kualitas data harus dipantau secara berkelanjutan.

---

# 8. Data Governance

Setiap data memiliki:

* Owner.
* Steward.
* Classification.
* Retention Policy.
* Access Policy.
* Audit Trail.

Perubahan struktur data harus melalui proses governance yang sesuai.

---

# 9. Metadata Management

Setiap dataset harus memiliki metadata yang mencakup:

* Nama.
* Deskripsi.
* Skema.
* Pemilik.
* Sumber.
* Frekuensi pembaruan.
* Tingkat sensitivitas.

Metadata harus dapat dicari dan diperbarui.

---

# 10. Data Integration

Integrasi data harus:

* Menggunakan kontrak yang jelas.
* Memiliki validasi.
* Menangani kegagalan secara aman.
* Mendukung idempotensi bila diperlukan.

Perubahan format data harus dikelola secara terkontrol.

---

# 11. Data Pipelines

Pipeline data harus:

* Dapat diulang.
* Terpantau.
* Memiliki logging.
* Memiliki mekanisme retry.
* Mendukung pemulihan setelah kegagalan.

Pipeline adalah bagian dari kode produksi dan mengikuti standar engineering yang sama.

---

# 12. Analytics

Data untuk analitik harus:

* Terverifikasi.
* Terdokumentasi.
* Memiliki definisi metrik yang konsisten.
* Dapat direproduksi.

Perbedaan definisi metrik harus dihindari.

---

# 13. AI & Machine Learning Data

Untuk sistem AI:

* Dataset harus memiliki versi.
* Dataset harus dapat ditelusuri asalnya.
* Label harus terdokumentasi.
* Perubahan dataset harus dicatat.
* Evaluasi kualitas dataset dilakukan secara berkala.

---

# 14. Security & Privacy

Data harus:

* Dilindungi selama transmisi.
* Dilindungi saat disimpan sesuai tingkat risiko.
* Diakses berdasarkan prinsip least privilege.
* Diproses sesuai regulasi yang berlaku.

Data sensitif tidak boleh digunakan untuk pengujian tanpa perlindungan yang memadai.

---

# 15. Backup & Retention

Seluruh data penting harus memiliki:

* Kebijakan backup.
* Kebijakan retensi.
* Kebijakan pemulihan.
* Kebijakan penghapusan.

Retensi mengikuti kebutuhan bisnis dan regulasi.

---

# 16. Monitoring

Pantau minimal:

* Pipeline Success Rate.
* Data Freshness.
* Data Quality.
* Storage Usage.
* Query Performance.
* Error Rate.

Anomali harus menghasilkan notifikasi yang sesuai.

---

# 17. AI Coding Agent Rules

AI Coding Agent wajib:

* Mengikuti standar skema data.
* Tidak membuat perubahan struktur data tanpa migrasi.
* Menambahkan validasi data bila diperlukan.
* Memperbarui dokumentasi skema.
* Menjaga kompatibilitas data jika memungkinkan.

---

# 18. Data Review Checklist

Reviewer memastikan:

* Model data sesuai kebutuhan.
* Skema terdokumentasi.
* Kualitas data dipertimbangkan.
* Pipeline memiliki observabilitas.
* Kebijakan keamanan diterapkan.
* Migrasi dapat dijalankan dengan aman.

---

# 19. Production Readiness Checklist

Sebelum rilis:

* Migrasi tervalidasi.
* Backup tersedia.
* Monitoring aktif.
* Metadata diperbarui.
* Dokumentasi skema lengkap.
* Kebijakan retensi diterapkan.
* Pipeline diuji.

---

# 20. Compliance

Seluruh sistem data wajib mematuhi AEP-015.

Pengecualian harus didokumentasikan melalui Architecture Decision Record (ADR).

---

# 21. Future Extensions

Standar ini akan diperluas menjadi:

* **AEP-015-SQL** — Relational Database Standards.
* **AEP-015-NOSQL** — NoSQL Standards.
* **AEP-015-PIPELINE** — Data Pipeline Standards.
* **AEP-015-GOVERNANCE** — Data Governance Standards.
* **AEP-015-QUALITY** — Data Quality Standards.
* **AEP-015-VECTOR** — Vector Database Standards.
* **AEP-015-ANALYTICS** — Analytics & BI Standards.
* **AEP-015-MLOPS-DATA** — AI Dataset Standards.
