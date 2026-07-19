# AEP-007-SQL — SQL Standards

**Version:** 1.0 (Draft)  
**Status:** Language Standard  
**Parent:** AEP-007 — Universal Coding Standards

---

# 1. Purpose

Dokumen ini menetapkan standar penggunaan SQL pada seluruh sistem di bawah AI Engineering Playbook (AEP).

Standar ini berlaku untuk:

* PostgreSQL
* MySQL
* SQL Server
* SQLite
* Data Warehouse
* Reporting Database
* Analytics Database

Target utama:

* Correctness
* Readability
* Performance
* Maintainability
* Security
* Scalability

---

# 2. SQL Philosophy

Seluruh SQL harus mengikuti prinsip berikut:

* Readability First.
* Correctness Before Performance.
* Explicit Over Implicit.
* Normalize Until Proven Otherwise.
* Optimize With Evidence.
* Security By Default.

SQL ditulis untuk dibaca oleh engineer berikutnya, bukan hanya dijalankan oleh database.

---

# 3. Naming Standards

Gunakan:

* snake_case
* Nama deskriptif
* Singular untuk tabel domain (misalnya `user`, `invoice`) atau konvensi organisasi yang konsisten.
* Hindari singkatan yang tidak umum.

Kolom:

* `id`
* `created_at`
* `updated_at`
* `deleted_at`
* `created_by`
* `updated_by`

Foreign Key:

```text
customer_id
invoice_id
project_id
```

---

# 4. Primary Keys

Standar:

* Setiap tabel wajib memiliki Primary Key.
* Primary Key bersifat immutable.
* Hindari menggunakan nilai bisnis sebagai Primary Key.

---

# 5. Foreign Keys

Semua relasi wajib:

* Menggunakan Foreign Key.
* Memiliki indeks bila diperlukan.
* Mendefinisikan perilaku penghapusan (`CASCADE`, `RESTRICT`, `SET NULL`) secara eksplisit.

---

# 6. Schema Design

Normalisasi digunakan sebagai default.

Denormalisasi hanya diperbolehkan apabila:

* Ada kebutuhan performa yang telah diukur.
* Didokumentasikan dalam ADR.

---

# 7. Data Types

Gunakan tipe data yang paling tepat.

Contoh:

* BOOLEAN untuk status logis.
* DECIMAL/NUMERIC untuk nilai uang.
* TIMESTAMP untuk waktu.
* UUID bila diperlukan sebagai identifier global.

Hindari menggunakan tipe data generik untuk seluruh kolom.

---

# 8. Query Standards

Setiap query harus:

* Mudah dibaca.
* Menggunakan indentasi konsisten.
* Menggunakan alias yang bermakna.
* Menghindari nested query yang berlebihan.

Gunakan CTE (`WITH`) untuk query kompleks agar lebih mudah dipahami dan dipelihara.

---

# 9. SELECT Standards

Dilarang:

```sql
SELECT *
```

Selalu pilih kolom yang benar-benar dibutuhkan.

Gunakan alias hanya bila meningkatkan kejelasan.

---

# 10. JOIN Standards

Gunakan:

* INNER JOIN
* LEFT JOIN
* RIGHT JOIN
* FULL JOIN

secara eksplisit.

Dilarang:

* Comma Join
* NATURAL JOIN

Seluruh kolom pada query multi-tabel harus diawali alias tabel agar tidak ambigu.

---

# 11. Filtering

Gunakan WHERE sedini mungkin.

Hindari:

* Filter setelah pemrosesan yang tidak diperlukan.
* Kondisi yang tidak dapat memanfaatkan indeks tanpa alasan yang jelas.

---

# 12. Indexing

Index dibuat berdasarkan pola akses data.

Index bukan dibuat untuk setiap kolom.

Evaluasi:

* Query Plan.
* Cardinality.
* Write Cost.
* Storage Cost.

---

# 13. Transactions

Gunakan transaksi hanya bila diperlukan.

Aturan:

* Sesingkat mungkin.
* Atomic.
* Consistent.
* Isolated.
* Durable.

Hindari transaksi panjang yang mengunci banyak data.

---

# 14. Migrations

Seluruh perubahan skema harus melalui migration.

Migration harus:

* Versioned.
* Repeatable.
* Dapat di-review.
* Dapat di-rollforward.

Rollback hanya dilakukan bila benar-benar aman untuk data.

---

# 15. Performance

Optimasi dilakukan berdasarkan:

* EXPLAIN / EXPLAIN ANALYZE.
* Monitoring.
* Data nyata.

Hindari optimasi berdasarkan asumsi.

---

# 16. Security

Wajib:

* Parameterized Query.
* Prepared Statement.
* Least Privilege.
* Encryption bila diperlukan.
* Audit Logging untuk operasi sensitif.

Dilarang:

* SQL Injection.
* Dynamic SQL tanpa validasi.
* Kredensial di dalam query atau source code.

---

# 17. Soft Delete

Jika menggunakan soft delete:

Gunakan:

```text
deleted_at
```

Hindari:

```text
is_deleted
```

kecuali ada alasan domain yang jelas.

---

# 18. Auditing

Tabel penting sebaiknya memiliki:

* created_at
* created_by
* updated_at
* updated_by

Untuk kebutuhan kepatuhan atau regulasi, pertimbangkan audit trail terpisah.

---

# 19. Anti-Patterns

Tidak diperbolehkan:

* SELECT *
* Comma Join
* NATURAL JOIN
* Hardcoded SQL parameter
* Query tanpa batas (`LIMIT`) untuk kebutuhan eksplorasi data yang besar
* Index berlebihan
* Trigger yang menyembunyikan logika bisnis tanpa dokumentasi

---

# 20. AI Coding Agent Rules

AI Coding Agent wajib:

* Menulis SQL yang mudah dibaca.
* Menggunakan parameterized query.
* Memilih kolom secara eksplisit.
* Menggunakan JOIN eksplisit.
* Menghindari duplikasi query.
* Meninjau kebutuhan indeks pada query baru.
* Menyarankan migration daripada perubahan manual.

---

# 21. Code Review Checklist

Reviewer memastikan:

* SQL mudah dipahami.
* Tidak menggunakan SELECT *.
* JOIN benar.
* Index dipertimbangkan.
* Parameterized query digunakan.
* Tidak ada risiko SQL Injection.
* Migration tersedia jika skema berubah.

---

# 22. Production Readiness Checklist

Sebelum rilis:

* Migration telah diuji.
* Query penting telah dianalisis dengan EXPLAIN.
* Foreign Key tervalidasi.
* Index sesuai kebutuhan.
* Backup dan recovery plan tersedia.
* Hak akses database mengikuti prinsip least privilege.
* Monitoring query aktif.

---

# 23. Compliance

Seluruh perubahan database wajib:

* Menggunakan migration.
* Melalui code review.
* Memenuhi standar AEP-007 dan AEP-007-SQL.

Pengecualian hanya diperbolehkan melalui Architecture Decision Record (ADR).

---

# 24. Future Extensions

Dokumen ini akan diperluas melalui standar turunan, antara lain:

* **AEP-007-SQL-PG** — PostgreSQL Standards
* **AEP-007-SQL-MY** — MySQL Standards
* **AEP-007-SQL-SERVER** — SQL Server Standards
* **AEP-007-SQL-DW** — Data Warehouse Standards
* **AEP-007-SQL-PERF** — SQL Performance Optimization
* **AEP-007-SQL-SEC** — Database Security Standards
