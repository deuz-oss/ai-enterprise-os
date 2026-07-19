# AEP-007 — Universal Coding Standards

**Version:** 1.0 (Draft)  
**Status:** Core Engineering Standard

---

# Purpose

Dokumen ini menetapkan standar penulisan kode yang berlaku untuk seluruh proyek di bawah AI Engineering Playbook (AEP).

Standar ini berlaku bagi:

* Software Engineer
* AI Coding Agent
* Code Reviewer
* Technical Architect

Tujuannya adalah menghasilkan kode yang:

* Benar (Correct)
* Mudah dipahami (Readable)
* Mudah dipelihara (Maintainable)
* Mudah diuji (Testable)
* Aman (Secure)
* Efisien (Efficient)
* Konsisten (Consistent)

---

# Coding Philosophy

## Code is Read More Than It Is Written

Kode harus dioptimalkan untuk mudah dibaca dan dipahami oleh manusia maupun AI.

---

## Simplicity Wins

Pilih solusi yang paling sederhana yang memenuhi kebutuhan.

Hindari:

* Overengineering.
* Abstraksi yang belum diperlukan.
* Clever code.

---

## Explicit Over Implicit

Perilaku sistem harus jelas.

Lebih baik kode sedikit lebih panjang tetapi mudah dipahami daripada singkat namun membingungkan.

---

## Consistency Over Personal Preference

Standar organisasi selalu lebih penting daripada preferensi individu.

---

# Universal Rules

## UC-001 — Readability First

Kode harus mudah dibaca.

Gunakan:

* Nama yang deskriptif.
* Struktur yang rapi.
* Indentasi konsisten.
* Format otomatis melalui formatter resmi.

---

## UC-002 — Single Responsibility

Setiap:

* fungsi,
* class,
* module,
* service,

harus memiliki satu tanggung jawab utama.

---

## UC-003 — Small Functions

Fungsi sebaiknya:

* Fokus pada satu tujuan.
* Mudah diuji.
* Memiliki alur yang jelas.

Jika fungsi mulai menangani banyak skenario yang tidak berkaitan, pertimbangkan pemecahan menjadi fungsi yang lebih kecil.

---

## UC-004 — Avoid Duplication

Jangan menduplikasi logika.

Sebelum menambah kode baru:

* Cari implementasi yang sudah ada.
* Gunakan kembali komponen yang sesuai.
* Ekstrak utilitas jika pola berulang muncul.

---

## UC-005 — Meaningful Naming

Nama harus menjelaskan maksud.

Hindari:

* data1
* temp
* obj
* value2
* test123

Gunakan nama yang menggambarkan peran dan isi variabel atau fungsi.

---

## UC-006 — Fail Fast

Validasi kondisi penting sedini mungkin.

Kesalahan harus:

* jelas,
* dapat ditelusuri,
* tidak disembunyikan.

---

## UC-007 — Defensive Programming

Asumsikan bahwa:

* Input dapat salah.
* Dependency dapat gagal.
* Network dapat terputus.
* Data dapat tidak lengkap.

Tulis kode yang menangani kondisi tersebut secara aman.

---

## UC-008 — Security First

Semua kode harus mempertimbangkan keamanan.

Minimal:

* Validasi input.
* Sanitasi data.
* Hindari injection.
* Jangan mencetak data sensitif ke log.
* Gunakan mekanisme penyimpanan secret yang aman.

---

## UC-009 — Performance With Evidence

Optimisasi dilakukan berdasarkan data.

Jangan mengorbankan keterbacaan hanya karena dugaan performa.

---

## UC-010 — Testability

Kode harus mudah diuji.

Prinsip:

* Dependency dapat diganti (mock/stub bila diperlukan).
* Hindari efek samping tersembunyi.
* Pisahkan logika bisnis dari infrastruktur.

---

# Error Handling

Semua error harus:

* Memiliki pesan yang jelas.
* Tidak membocorkan informasi sensitif.
* Dicatat pada level yang sesuai.
* Dapat ditangani atau diteruskan secara konsisten.

---

# Logging Standards

Logging harus membantu operasional.

Log sebaiknya:

* Memiliki konteks yang cukup.
* Menggunakan format terstruktur jika memungkinkan.
* Tidak menyimpan data sensitif.
* Mendukung pelacakan permintaan (request tracing).

---

# Configuration Standards

Konfigurasi harus dipisahkan dari kode.

Gunakan:

* Environment variables.
* Secret manager.
* File konfigurasi yang terversi bila tidak memuat informasi sensitif.

Hindari:

* Hardcoded URL.
* Hardcoded credential.
* Hardcoded API key.

---

# Dependency Management

Tambahkan dependency baru hanya jika:

* Ada kebutuhan nyata.
* Lisensinya sesuai.
* Masih dipelihara.
* Tidak menimbulkan risiko keamanan yang signifikan.

Kurangi dependency yang tidak lagi digunakan.

---

# Documentation Standards

Kode harus dapat dipahami tanpa komentar yang berlebihan.

Dokumentasikan:

* Keputusan yang tidak intuitif.
* Kontrak publik.
* Perilaku kompleks.
* Asumsi penting.

Komentar yang menjelaskan *apa* yang dilakukan kode sebaiknya dihindari jika kode itu sendiri sudah cukup jelas; fokuslah pada *mengapa* keputusan tersebut diambil.

---

# Code Review Expectations

Reviewer memeriksa:

* Kebenaran logika.
* Kepatuhan terhadap standar AEP.
* Keamanan.
* Keterbacaan.
* Kemudahan pengujian.
* Dampak terhadap arsitektur.
* Potensi regresi.

Review bertujuan meningkatkan kualitas, bukan mencari kesalahan individu.

---

# AI Coding Agent Rules

AI Coding Agent wajib:

* Mematuhi seluruh standar AEP.
* Tidak menghapus kode tanpa alasan yang jelas.
* Tidak mengubah perilaku publik tanpa persetujuan.
* Memperbarui dokumentasi yang terdampak.
* Menambahkan atau memperbarui pengujian sesuai perubahan.
* Menjelaskan asumsi penting dalam deskripsi perubahan.
* Menghindari menghasilkan kode duplikat jika solusi yang setara sudah tersedia.

---

# Definition of Clean Code

Kode dianggap memenuhi standar AEP apabila:

* Mudah dibaca.
* Mudah diuji.
* Aman.
* Konsisten.
* Tidak mengandung duplikasi yang tidak perlu.
* Mengikuti arsitektur yang disepakati.
* Siap dipelihara oleh engineer lain tanpa penjelasan tambahan.

---

# Compliance

Seluruh perubahan kode wajib melalui:

* Pemeriksaan otomatis (formatter, linter, dan pengujian yang relevan).
* Code review sesuai kebijakan proyek.
* Validasi terhadap standar dalam AEP-007.

Pengecualian harus didokumentasikan dan disetujui melalui mekanisme governance yang berlaku.
