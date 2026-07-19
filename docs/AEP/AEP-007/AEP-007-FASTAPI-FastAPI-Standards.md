# AEP-007-FASTAPI — FastAPI Standards

**Version:** 1.0 (Draft)  
**Status:** Framework Standard  
**Parent:** AEP-007 — Universal Coding Standards  
**Requires:** AEP-007-PY — Python Coding Standards

---

# 1. Purpose

Dokumen ini menetapkan standar penggunaan FastAPI untuk seluruh layanan backend dalam AI Engineering Playbook (AEP).

Standar ini berlaku untuk:

* REST API
* Internal Services
* AI Services
* Microservices
* Backend for Frontend (BFF)
* Webhook Services

Target utama:

* High Performance
* High Security
* High Maintainability
* High Testability
* Production Ready

---

# 2. FastAPI Philosophy

Seluruh aplikasi FastAPI harus mengikuti prinsip:

* API First
* Type First
* Async First (untuk operasi I/O)
* Validation First
* Security First
* Documentation by Default
* Dependency Injection by Design

Framework digunakan untuk mengorkestrasi request, bukan sebagai tempat logika bisnis. Logika domain harus tetap berada di layer domain/service.

---

# 3. Project Structure

Standar minimum:

```text
app/
├── api/
├── core/
├── domain/
├── services/
├── repositories/
├── models/
├── schemas/
├── dependencies/
├── middleware/
├── security/
├── workers/
└── main.py
```

Aturan:

* Router tidak boleh berisi business logic.
* Service tidak boleh mengetahui detail HTTP.
* Repository bertanggung jawab pada akses data.
* Domain tidak bergantung pada FastAPI.

---

# 4. API Design

Semua endpoint harus:

* RESTful.
* Versioned.
* Idempotent jika relevan.
* Menggunakan HTTP status code yang tepat.
* Menggunakan response model.

Contoh:

```
GET
POST
PUT
PATCH
DELETE
```

Gunakan kata benda pada URL, bukan kata kerja.

Benar:

```
/users
/orders
/invoices
```

Salah:

```
/getUsers
/createInvoice
```

---

# 5. Request Validation

Semua input wajib divalidasi menggunakan model Pydantic.

Aturan:

* Tidak menerima dictionary mentah sebagai request body.
* Gunakan tipe data yang spesifik.
* Batasi panjang string dan nilai numerik bila memungkinkan.
* Gunakan model terpisah untuk input dan output bila diperlukan.

---

# 6. Response Models

Semua endpoint publik wajib memiliki response model.

Tujuan:

* Konsistensi.
* Validasi.
* Dokumentasi OpenAPI otomatis.

Jangan mengembalikan ORM model secara langsung.

---

# 7. Dependency Injection

Gunakan mekanisme `Depends()` untuk:

* Database session.
* Authentication.
* Authorization.
* Configuration.
* Shared services.

Dependency harus:

* Stateless bila memungkinkan.
* Dapat diuji.
* Dapat diganti (override) pada pengujian.

---

# 8. Business Logic

Business logic dilarang berada di:

* Router.
* Middleware.
* Dependency.

Business logic hanya berada pada:

* Service Layer.
* Domain Layer.

Router hanya:

* Validasi request.
* Memanggil service.
* Mengembalikan response.

---

# 9. Database Access

Repository bertanggung jawab terhadap:

* Query.
* Persistence.
* Transaction.

Service tidak boleh membuat query SQL secara langsung.

---

# 10. Async Guidelines

Gunakan `async` hanya untuk operasi I/O seperti:

* Database async.
* HTTP client.
* File.
* Object storage.

Jangan menjalankan pekerjaan CPU-intensif di dalam request handler; gunakan worker atau task queue bila diperlukan.

---

# 11. Error Handling

Gunakan:

* Exception khusus domain.
* HTTPException hanya pada layer HTTP.

Semua error harus:

* Konsisten.
* Memiliki kode.
* Memiliki pesan yang aman.
* Tidak membocorkan detail internal.

---

# 12. Authentication

Standar:

* OAuth2/JWT bila sesuai kebutuhan.
* Token validation.
* Refresh token terpisah.
* Role-Based Access Control (RBAC).

Endpoint privat wajib menggunakan dependency keamanan yang sesuai.

---

# 13. Authorization

Authorization dilakukan pada:

* Service Layer.
* Security Layer.

Jangan hanya mengandalkan validasi di frontend.

---

# 14. Middleware

Middleware hanya boleh digunakan untuk:

* Request ID.
* Logging.
* CORS.
* Compression.
* Security headers.
* Observability.

Hindari meletakkan business logic di middleware.

---

# 15. Background Processing

Gunakan:

* BackgroundTasks untuk pekerjaan ringan.
* Task Queue terpisah untuk pekerjaan berat atau berdurasi panjang.

Request API tidak boleh menunggu proses yang dapat dijalankan secara asinkron.

---

# 16. Documentation

Seluruh endpoint harus:

* Memiliki summary.
* Memiliki description bila diperlukan.
* Memiliki response model.
* Memiliki contoh request bila berguna.

OpenAPI merupakan kontrak resmi API.

---

# 17. Observability

Seluruh service wajib memiliki:

* Structured logging.
* Request ID.
* Health endpoint.
* Readiness endpoint.
* Metrics.
* Trace jika sistem terdistribusi.

---

# 18. Security Standards

Wajib:

* Input validation.
* Parameterized queries.
* Secret manager.
* Rate limiting bila diperlukan.
* Dependency scanning.
* Konfigurasi CORS yang ketat.

Dilarang:

* Hardcoded secret.
* Debug mode di produksi.
* Endpoint administratif tanpa autentikasi.

---

# 19. Testing Standards

Minimal:

* Unit Test.
* Integration Test.
* API Test.

Gunakan dependency override untuk pengujian sehingga layanan dapat diuji tanpa bergantung pada sistem eksternal.

---

# 20. AI Coding Agent Rules

AI Coding Agent wajib:

* Membuat router yang tipis (thin controllers).
* Menempatkan business logic di service.
* Menggunakan dependency injection.
* Menghasilkan model Pydantic untuk request dan response.
* Menggunakan type hints di seluruh endpoint.
* Menambahkan atau memperbarui pengujian yang relevan.
* Memastikan dokumentasi OpenAPI tetap akurat.

---

# 21. Anti-Patterns

Tidak diperbolehkan:

* Business logic di router.
* SQL di endpoint.
* Hardcoded configuration.
* Exception yang ditelan.
* Mengembalikan ORM model langsung.
* Membuat koneksi database baru pada setiap endpoint tanpa mekanisme pengelolaan yang tepat.
* Endpoint tanpa response model.

---

# 22. Production Readiness Checklist

Sebelum rilis:

* Seluruh endpoint tervalidasi.
* OpenAPI lengkap.
* Health & readiness endpoint aktif.
* Structured logging aktif.
* Authentication & authorization diuji.
* Monitoring tersedia.
* Dependency keamanan diperiksa.
* Pengujian otomatis lulus.

---

# 23. Compliance

Seluruh layanan FastAPI wajib mematuhi standar ini.

Penyimpangan hanya diperbolehkan melalui Architecture Decision Record (ADR) yang menjelaskan alasan, dampak, dan rencana mitigasi.
