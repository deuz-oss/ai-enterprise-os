# AEP-002 — Engineering Principles

**Version:** 1.0 (Draft)  
**Status:** Foundational Standard

---

# Purpose

Dokumen ini menetapkan prinsip-prinsip dasar yang wajib menjadi landasan seluruh keputusan engineering, mulai dari perencanaan produk hingga operasi sistem. Setiap engineer dan AI agent harus mematuhi prinsip ini.

---

# EP-01 — Product First

**Principle**

Engineering ada untuk menghasilkan nilai bagi pengguna dan bisnis.

**Mandatory Rules**

* Setiap pekerjaan harus memiliki tujuan bisnis atau kebutuhan pengguna yang jelas.
* Hindari membangun fitur tanpa validasi kebutuhan.
* Prioritaskan penyelesaian masalah daripada penambahan fitur.

**Anti-Patterns**

* Feature bloat.
* Solusi teknis yang tidak memberikan nilai nyata.
* Optimisasi prematur.

**Success Indicators**

* Fitur digunakan oleh pengguna.
* Dampak bisnis dapat diukur.

---

# EP-02 — AI First

**Principle**

AI adalah mitra engineering, bukan sekadar alat bantu.

**Mandatory Rules**

* Gunakan AI untuk mempercepat analisis, implementasi, pengujian, dan dokumentasi.
* Semua output AI harus ditinjau sebelum masuk ke produksi.
* AI tidak boleh menjadi satu-satunya sumber kebenaran.

**Anti-Patterns**

* Menyalin hasil AI tanpa verifikasi.
* Mengabaikan hasil AI yang berkualitas tanpa alasan.

**Success Indicators**

* Waktu pengembangan menurun.
* Kualitas tetap terjaga.

---

# EP-03 — Security by Design

**Principle**

Keamanan merupakan bagian dari desain sejak awal.

**Mandatory Rules**

* Terapkan autentikasi dan otorisasi yang tepat.
* Lindungi data sensitif.
* Gunakan prinsip least privilege.
* Validasi semua input.

**Anti-Patterns**

* Secret di dalam source code.
* Endpoint tanpa kontrol akses.
* Input yang tidak divalidasi.

**Success Indicators**

* Tidak ada kerentanan kritis yang lolos ke produksi.
* Audit keamanan dapat ditelusuri.

---

# EP-04 — Simplicity Over Complexity

**Principle**

Solusi paling sederhana yang memenuhi kebutuhan adalah pilihan utama.

**Mandatory Rules**

* Pilih desain yang mudah dipahami dan dipelihara.
* Kurangi dependensi yang tidak perlu.
* Hindari abstraksi berlebihan.

**Anti-Patterns**

* Overengineering.
* Pola desain yang tidak diperlukan.
* Struktur kode yang membingungkan.

**Success Indicators**

* Waktu onboarding engineer lebih singkat.
* Refactoring lebih mudah dilakukan.

---

# EP-05 — Reuse Before Build

**Principle**

Gunakan kembali aset yang sudah ada sebelum membuat yang baru.

**Mandatory Rules**

* Cari komponen, library, atau template internal terlebih dahulu.
* Dokumentasikan komponen yang dapat digunakan ulang.

**Anti-Patterns**

* Duplikasi kode.
* Membuat ulang solusi yang sudah tersedia.

**Success Indicators**

* Tingkat reuse meningkat.
* Jumlah duplikasi kode menurun.

---

# EP-06 — Documentation First

**Principle**

Dokumentasi adalah bagian dari produk.

**Mandatory Rules**

* Setiap perubahan signifikan harus disertai pembaruan dokumentasi.
* Gunakan template dokumentasi yang seragam.

**Anti-Patterns**

* Dokumentasi tidak sinkron dengan implementasi.
* Pengetahuan hanya tersimpan di kepala individu.

**Success Indicators**

* Dokumentasi selalu relevan.
* Onboarding menjadi lebih cepat.

---

# EP-07 — Testing First

**Principle**

Kualitas dibangun melalui pengujian yang sistematis.

**Mandatory Rules**

* Semua fitur memiliki strategi pengujian.
* Perubahan harus lulus seluruh pipeline pengujian yang relevan.
* Bug yang ditemukan harus menghasilkan pengujian untuk mencegah regresi.

**Anti-Patterns**

* Menguji hanya secara manual.
* Memperbaiki bug tanpa menambah pengujian.

**Success Indicators**

* Tingkat regresi menurun.
* Kepercayaan terhadap proses rilis meningkat.

---

# EP-08 — Automation First

**Principle**

Pekerjaan berulang harus diotomatisasi.

**Mandatory Rules**

* Gunakan pipeline otomatis untuk build, test, dan deployment.
* Hindari proses manual yang dapat digantikan oleh otomasi.

**Anti-Patterns**

* Langkah manual yang rentan kesalahan.
* Deployment tanpa proses yang terdokumentasi.

**Success Indicators**

* Waktu rilis berkurang.
* Kesalahan operasional menurun.

---

# EP-09 — Measure Everything

**Principle**

Keputusan engineering harus didasarkan pada data.

**Mandatory Rules**

* Tentukan metrik untuk setiap sistem penting.
* Pantau kualitas, performa, dan reliabilitas secara berkelanjutan.

**Anti-Patterns**

* Mengandalkan asumsi tanpa data.
* Tidak memiliki indikator keberhasilan.

**Success Indicators**

* Dashboard engineering tersedia.
* Keputusan dapat dijelaskan dengan data.

---

# EP-10 — Continuous Improvement

**Principle**

Tidak ada proses yang dianggap sempurna.

**Mandatory Rules**

* Lakukan evaluasi berkala terhadap proses engineering.
* Dokumentasikan pembelajaran dari setiap insiden atau proyek.

**Anti-Patterns**

* Mengulang kesalahan yang sama.
* Menolak perubahan tanpa evaluasi.

**Success Indicators**

* Proses terus berkembang.
* Peningkatan kualitas dapat diukur.

---

# Compliance

Semua engineer, reviewer, dan AI agent wajib mematuhi prinsip-prinsip dalam dokumen ini. Penyimpangan harus memiliki alasan yang terdokumentasi dan disetujui sesuai mekanisme governance.

---

# Exit Criteria

Sebuah pekerjaan engineering dianggap selesai apabila:

* Selaras dengan seluruh prinsip AEP.
* Memenuhi standar keamanan dan kualitas.
* Memiliki dokumentasi yang memadai.
* Lulus proses pengujian yang relevan.
* Siap dipelihara dan dikembangkan di masa depan.
