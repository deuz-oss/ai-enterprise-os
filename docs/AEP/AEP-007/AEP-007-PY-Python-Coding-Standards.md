# AEP-007-PY — Python Coding Standards

**Version:** 1.0 (Draft)  
**Status:** Language Standard  
**Parent:** AEP-007 — Universal Coding Standards

---

# 1. Purpose

Dokumen ini menetapkan standar pengembangan Python untuk seluruh proyek di bawah AI Engineering Playbook (AEP).

Standar ini berlaku untuk:

* Backend Services
* AI Services
* Automation Scripts
* CLI Applications
* Data Processing
* Internal Libraries

Tujuan utamanya adalah menghasilkan kode Python yang:

* Konsisten
* Mudah dipelihara
* Aman
* Mudah diuji
* Siap produksi

---

# 2. Python Philosophy

Seluruh kode Python harus mengikuti prinsip berikut:

* Readability counts.
* Explicit is better than implicit.
* Simple is better than complex.
* Composition over inheritance.
* Type safety where practical.
* Testability by design.
* Fail fast with meaningful errors.

Jika terjadi konflik antara kecerdasan implementasi dan keterbacaan, pilih keterbacaan.

---

# 3. Python Version Policy

Standar organisasi:

* Gunakan satu versi Python yang didukung organisasi (misalnya Python 3.13) untuk seluruh proyek baru.
* Hindari fitur eksperimental pada sistem produksi.
* Semua proyek harus mendokumentasikan versi Python yang digunakan.

---

# 4. Project Structure

Direkomendasikan:

```text
project/
├── src/
├── tests/
├── docs/
├── scripts/
├── migrations/
├── pyproject.toml
├── README.md
└── .env.example
```

Semua kode aplikasi berada di dalam `src/`.

---

# 5. Naming Conventions

## Modules

Gunakan:

* snake_case

Contoh:

```text
user_service.py
payment_gateway.py
```

---

## Packages

Gunakan:

* snake_case
* Nama singkat
* Hindari singkatan yang tidak umum

---

## Classes

Gunakan:

PascalCase

Contoh:

```python
UserService
InvoiceProcessor
```

---

## Functions

Gunakan:

snake_case

Contoh:

```python
calculate_total()
validate_token()
```

Nama fungsi harus berupa kata kerja atau frasa kerja yang menggambarkan tindakan.

---

## Variables

Gunakan nama yang deskriptif.

Hindari:

```python
x
data1
tmp
```

Gunakan:

```python
invoice_total
customer_id
access_token
```

---

## Constants

Gunakan:

UPPER_SNAKE_CASE

Contoh:

```python
DEFAULT_TIMEOUT
MAX_RETRIES
```

---

# 6. Type Hints

Type hints wajib digunakan pada:

* Public functions
* Public methods
* Return values
* Class attributes yang relevan

Contoh:

```python
def calculate_total(items: list[Item]) -> Decimal:
 ...
```

Hindari penggunaan `Any` kecuali benar-benar diperlukan dan terdokumentasi alasannya.

---

# 7. Function Design

Fungsi harus:

* Memiliki satu tujuan utama.
* Memiliki nama yang jelas.
* Memiliki jumlah parameter yang wajar.
* Mengembalikan hasil yang konsisten.

Jika fungsi mulai menangani banyak tanggung jawab, pecah menjadi fungsi yang lebih kecil.

---

# 8. Classes

Class digunakan ketika:

* Memiliki state yang perlu dipertahankan.
* Mengelompokkan perilaku yang saling berkaitan.
* Mewakili domain yang jelas.

Hindari membuat class hanya untuk membungkus satu fungsi.

---

# 9. Error Handling

Gunakan exception yang spesifik.

Hindari:

```python
except Exception:
 pass
```

Lebih baik:

```python
except ValueError:
 ...
```

Exception tidak boleh disembunyikan tanpa alasan yang terdokumentasi.

---

# 10. Logging

Gunakan modul `logging`.

Aturan:

* Jangan gunakan `print()` untuk logging aplikasi.
* Sertakan konteks yang relevan.
* Jangan mencatat password, token, atau data sensitif.
* Gunakan level log yang sesuai (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`).

---

# 11. Configuration

Konfigurasi harus dipisahkan dari kode.

Gunakan:

* Environment variables.
* File konfigurasi yang terversi bila tidak mengandung rahasia.
* Secret manager untuk kredensial.

Jangan pernah melakukan hardcode:

* API key.
* Password.
* Connection string produksi.

---

# 12. Data Models

Gunakan tipe data sesuai kebutuhan:

* `dataclass` untuk objek sederhana yang berisi data.
* Pydantic untuk validasi dan serialisasi data eksternal.
* ORM model hanya untuk representasi penyimpanan data.

Pisahkan model domain dari model database jika kompleksitas domain meningkat.

---

# 13. Async Programming

Gunakan `async` hanya jika memberikan manfaat nyata, misalnya untuk operasi I/O.

Aturan:

* Hindari mencampur pola sinkron dan asinkron tanpa alasan.
* Jangan memblokir event loop.
* Dokumentasikan asumsi konkurensi jika relevan.

---

# 14. Dependency Management

Gunakan:

* `pyproject.toml` sebagai sumber konfigurasi utama.
* Dependency seminimal mungkin.
* Versi dependency yang dapat direproduksi.

Evaluasi keamanan dependency secara berkala.

---

# 15. Testing

Gunakan `pytest` sebagai standar.

Setiap fitur baru harus memiliki pengujian yang sesuai.

Minimal:

* Unit test untuk logika bisnis.
* Integration test untuk integrasi penting.

Bug yang diperbaiki harus disertai pengujian untuk mencegah regresi.

---

# 16. Documentation

Public API, fungsi kompleks, dan modul penting harus memiliki dokumentasi yang menjelaskan tujuan, parameter utama, dan perilaku yang tidak intuitif.

Komentar digunakan untuk menjelaskan *mengapa*, bukan mengulang apa yang sudah jelas dari kode.

---

# 17. Security

Wajib:

* Validasi seluruh input eksternal.
* Gunakan query terparameterisasi.
* Lindungi data sensitif.
* Perbarui dependency yang memiliki kerentanan.

Larangan:

* Menonaktifkan validasi keamanan tanpa persetujuan.
* Menyimpan secret di repository.

---

# 18. Performance

Optimasi dilakukan berdasarkan hasil pengukuran.

Prioritaskan:

* Algoritma yang tepat.
* Struktur data yang sesuai.
* Pengurangan operasi I/O yang tidak perlu.
* Caching bila memberikan manfaat yang terbukti.

---

# 19. Anti-Patterns

Tidak diperbolehkan:

* `from module import *`
* Hardcoded secret.
* Fungsi dengan banyak tanggung jawab yang tidak terkait.
* Duplikasi logika bisnis.
* Exception yang ditelan tanpa penanganan.
* Dependensi yang tidak digunakan.
* Kode mati (dead code) yang tidak memiliki rencana penghapusan.

---

# 20. AI Coding Agent Rules

AI Coding Agent wajib:

* Menghasilkan kode yang mengikuti standar ini.
* Menggunakan type hints.
* Memilih nama yang deskriptif.
* Menghindari duplikasi.
* Menambahkan atau memperbarui pengujian sesuai perubahan.
* Memperbarui dokumentasi jika antarmuka publik berubah.
* Tidak mengubah perilaku yang sudah ada tanpa justifikasi yang jelas.

---

# 21. Code Review Checklist

Reviewer memastikan:

* Kode mudah dipahami.
* Type hints sesuai.
* Error handling memadai.
* Pengujian relevan tersedia.
* Tidak ada kerentanan keamanan yang jelas.
* Tidak ada duplikasi yang tidak perlu.
* Kepatuhan terhadap AEP-007 dan AEP-007-PY.

---

# 22. Production Readiness Checklist

Sebelum rilis:

* Seluruh pengujian relevan lulus.
* Dokumentasi diperbarui.
* Konfigurasi dipisahkan dari kode.
* Logging memadai.
* Tidak ada secret di repository.
* Dependency telah ditinjau.
* Observabilitas tersedia.
* Persyaratan keamanan telah dipenuhi.

---

# 23. Compliance

Semua proyek Python wajib mematuhi standar ini.

Pengecualian hanya diperbolehkan jika:

* Memiliki alasan teknis yang terdokumentasi.
* Disetujui melalui Architecture Decision Record (ADR) atau mekanisme governance yang berlaku.
