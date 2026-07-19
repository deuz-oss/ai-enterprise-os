# AEP-007-TS — TypeScript Coding Standards

**Version:** 1.0 (Draft)  
**Status:** Language Standard  
**Parent:** AEP-007 — Universal Coding Standards

---

# 1. Purpose

Dokumen ini menetapkan standar penggunaan TypeScript pada seluruh proyek dalam AI Engineering Playbook (AEP).

Standar ini berlaku untuk:

* Frontend Applications
* Backend Node.js
* Shared Libraries
* SDK
* CLI Tools
* Build Tools

Target utama:

* Type Safety
* Maintainability
* Readability
* Scalability
* Testability
* Production Readiness

---

# 2. TypeScript Philosophy

Seluruh kode TypeScript mengikuti prinsip:

* Types First.
* Compile-Time Safety.
* Explicit Over Implicit.
* Simplicity Over Cleverness.
* Composition Over Inheritance.
* Immutable by Default.
* Domain-Driven Design.

TypeScript digunakan untuk menangkap kesalahan sedini mungkin melalui sistem tipe, bukan hanya sebagai pengganti JavaScript.

---

# 3. Compiler Configuration

Seluruh proyek wajib menggunakan konfigurasi ketat (`strict mode`).

Prinsip:

* Aktifkan pemeriksaan tipe yang ketat.
* Perlakukan peringatan tipe sebagai masalah yang harus diselesaikan.
* Hindari menonaktifkan pemeriksaan tanpa alasan yang terdokumentasi.

---

# 4. Project Structure

Struktur minimum:

```text
src/
components/
features/
services/
hooks/
types/
utils/
tests/
```

Aturan:

* Pisahkan domain bisnis dari utilitas.
* Hindari folder `misc`, `common`, atau `helpers` yang menjadi tempat segala hal tanpa struktur.

---

# 5. Naming Conventions

Gunakan:

**Files**

* kebab-case

Contoh:

```text
user-service.ts
invoice-summary.tsx
```

**Variables**

* camelCase

**Functions**

* camelCase

**Types & Interfaces**

* PascalCase

**Enums**

* PascalCase

**Constants**

* UPPER_SNAKE_CASE untuk konstanta global.
* camelCase untuk konstanta lokal.

---

# 6. Type Safety

Semua public API harus memiliki tipe eksplisit.

Gunakan:

* interface untuk kontrak objek yang dapat diperluas.
* type untuk union, intersection, mapped type, dan utility type.

Hindari penggunaan `any`.

Jika benar-benar diperlukan:

* Dokumentasikan alasannya.
* Batasi cakupannya seminimal mungkin.

Lebih baik gunakan `unknown` dibanding `any`, lalu lakukan validasi atau narrowing sebelum digunakan.

---

# 7. Functions

Fungsi harus:

* Memiliki satu tanggung jawab.
* Memiliki parameter yang jelas.
* Memiliki return type eksplisit untuk API publik.
* Mudah diuji.

Hindari fungsi dengan terlalu banyak parameter; gunakan objek konfigurasi bila sesuai.

---

# 8. Classes

Gunakan class hanya bila benar-benar diperlukan.

Lebih utamakan:

* Function.
* Composition.
* Pure Functions.

Class digunakan apabila memiliki state dan perilaku yang memang saling terkait.

---

# 9. Immutability

Prioritaskan objek yang tidak berubah.

Gunakan:

* `readonly`
* Immutable update
* Pure function

Hindari mutasi objek bersama tanpa alasan yang kuat.

---

# 10. Error Handling

Error harus:

* Konsisten.
* Dapat dipahami.
* Tidak membocorkan informasi sensitif.

Gunakan custom error untuk domain yang kompleks.

Jangan menggunakan exception untuk alur kontrol normal.

---

# 11. Async Programming

Gunakan:

* async / await

Hindari:

* Promise chaining yang panjang.
* Callback yang bertingkat.

Selalu tangani kemungkinan penolakan (`rejection`) secara eksplisit.

---

# 12. Modules

Gunakan ES Modules.

Aturan:

* Hindari circular dependency.
* Satu modul memiliki satu tujuan utama.
* Public API modul harus kecil dan jelas.

---

# 13. Dependency Management

Dependency baru hanya boleh ditambahkan jika:

* Memberikan nilai nyata.
* Dipelihara dengan baik.
* Lisensinya sesuai.
* Tidak meningkatkan risiko keamanan secara signifikan.

Kurangi dependency yang tidak lagi digunakan.

---

# 14. Testing

Seluruh logika bisnis harus dapat diuji.

Minimal:

* Unit Test.
* Integration Test.

Perubahan bug wajib disertai pengujian regresi.

---

# 15. Security

Wajib:

* Validasi input eksternal.
* Hindari evaluasi kode dinamis yang tidak perlu.
* Lindungi secret.
* Sanitasi data sebelum dirender atau dikirim.

Seluruh akses ke sumber daya sensitif harus melalui lapisan yang sesuai.

---

# 16. Performance

Optimasi berdasarkan pengukuran.

Prioritaskan:

* Struktur data yang tepat.
* Pengurangan render yang tidak perlu.
* Lazy loading bila relevan.
* Memoization hanya jika memberikan manfaat yang terbukti.

---

# 17. Documentation

Dokumentasikan:

* API publik.
* Tipe kompleks.
* Asumsi penting.
* Keputusan desain yang tidak intuitif.

Komentar harus menjelaskan *mengapa*, bukan sekadar *apa*.

---

# 18. Anti-Patterns

Tidak diperbolehkan:

* `any` tanpa justifikasi.
* Non-null assertion (`!`) tanpa alasan yang jelas.
* Circular dependency.
* Mutasi state global yang tidak terkontrol.
* Dead code.
* Fungsi dengan banyak tanggung jawab.
* Ekspor seluruh isi modul tanpa kebutuhan yang jelas.

---

# 19. AI Coding Agent Rules

AI Coding Agent wajib:

* Menghasilkan kode dengan type safety yang kuat.
* Menghindari penggunaan `any`.
* Menggunakan tipe yang paling spesifik.
* Menambahkan atau memperbarui pengujian yang relevan.
* Memperbarui tipe jika kontrak berubah.
* Menghindari duplikasi logika.

---

# 20. Code Review Checklist

Reviewer memastikan:

* Type safety terjaga.
* Tidak ada `any` yang tidak perlu.
* Struktur modul jelas.
* Fungsi mudah dipahami.
* Pengujian memadai.
* Tidak ada potensi regresi.
* Kepatuhan terhadap AEP-007 dan AEP-007-TS.

---

# 21. Production Readiness Checklist

Sebelum rilis:

* Proyek lulus type checking.
* Seluruh pengujian relevan lulus.
* Linter dan formatter berhasil dijalankan.
* Tidak ada dependency yang diketahui rentan.
* Dokumentasi diperbarui.
* Tidak ada penggunaan `any` yang tidak dapat dipertanggungjawabkan.
* Build dapat direproduksi.

---

# 22. Compliance

Seluruh proyek TypeScript wajib mematuhi standar ini.

Pengecualian hanya diperbolehkan jika didokumentasikan melalui Architecture Decision Record (ADR) atau mekanisme governance yang berlaku.

---

# 23. Future Extensions

Standar ini akan diperluas menjadi dokumen turunan, antara lain:

* **AEP-007-TS-REACT** — React & UI Standards.
* **AEP-007-TS-NODE** — Node.js Standards.
* **AEP-007-TS-NEXT** — Next.js Standards.
* **AEP-007-TS-LIB** — Shared Library Standards.
* **AEP-007-TS-TEST** — TypeScript Testing Standards.
* **AEP-007-TS-PERF** — Performance Standards.
