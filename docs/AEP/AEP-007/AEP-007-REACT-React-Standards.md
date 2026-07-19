# AEP-007-REACT — React Standards

**Version:** 1.0 (Draft)  
**Status:** Framework Standard  
**Parent:** AEP-007-TS — TypeScript Coding Standards

---

# 1. Purpose

Dokumen ini menetapkan standar pengembangan aplikasi React pada seluruh proyek di bawah AI Engineering Playbook (AEP).

Standar ini berlaku untuk:

* Web Applications
* Enterprise Dashboard
* Admin Panel
* SaaS Products
* Design System
* Internal Applications

Target utama:

* Maintainability
* Performance
* Accessibility
* Scalability
* Testability
* Consistency

---

# 2. React Philosophy

Seluruh aplikasi React mengikuti prinsip:

* Component First
* Composition Over Inheritance
* State Minimalism
* UI as a Pure Function of State
* Accessibility by Default
* Performance by Design
* Reusable Before Rebuild

---

# 3. Project Structure

Direkomendasikan:

```text
src/
├── app/
├── features/
├── components/
├── layouts/
├── hooks/
├── services/
├── contexts/
├── types/
├── utils/
├── assets/
└── tests/
```

Aturan:

* Struktur berdasarkan fitur (feature-based) untuk domain besar.
* Hindari folder `misc`, `common`, atau `helpers` yang menjadi tempat segala sesuatu.

---

# 4. Component Design

Komponen harus:

* Memiliki satu tanggung jawab.
* Dapat digunakan ulang bila memang relevan.
* Mudah diuji.
* Memiliki API yang sederhana.

Pisahkan:

* Presentational Components
* Container / Feature Components

Business logic tidak boleh berada di komponen presentasi.

---

# 5. Component Naming

Gunakan:

PascalCase

Contoh:

```text
InvoiceCard.tsx
UserProfile.tsx
SalesDashboard.tsx
```

File komponen utama menggunakan nama yang sama dengan nama komponennya.

---

# 6. Props

Props harus:

* Bertipe eksplisit.
* Seminimal mungkin.
* Bersifat immutable.

Hindari:

* Prop drilling yang panjang.
* Objek besar yang tidak diperlukan.

---

# 7. State Management

Prioritas:

1. Local State
2. Context (untuk state global sederhana)
3. State Management Library (untuk kebutuhan kompleks)

Prinsip:

* Simpan state sedekat mungkin dengan tempat penggunaannya.
* Jangan menduplikasi state yang dapat dihitung dari data lain.

---

# 8. Hooks

Gunakan Hooks untuk:

* State
* Side Effects
* Reusable Logic

Custom Hook harus:

* Memiliki satu tujuan.
* Diawali dengan `use`.
* Tidak mengandung logika UI.

---

# 9. Effects

Gunakan efek hanya untuk sinkronisasi dengan sistem eksternal.

Hindari:

* Menggunakan efek untuk menghitung nilai yang dapat dihitung saat render.
* Efek yang saling bergantung secara rumit.

---

# 10. Rendering

Prioritaskan:

* Pure rendering.
* Conditional rendering yang sederhana.
* Key yang stabil pada daftar.

Jangan menggunakan indeks array sebagai `key` jika urutan data dapat berubah.

---

# 11. Performance

Optimasi dilakukan berdasarkan hasil pengukuran.

Teknik yang dapat digunakan bila terbukti bermanfaat:

* Lazy Loading
* Code Splitting
* Memoization
* Virtualization untuk daftar besar

Hindari memoization berlebihan yang justru menambah kompleksitas.

---

# 12. Forms

Seluruh form harus:

* Memiliki validasi.
* Menampilkan pesan kesalahan yang jelas.
* Mendukung navigasi keyboard.
* Menangani status loading dan submit.

Pisahkan logika validasi dari komponen tampilan bila kompleks.

---

# 13. Accessibility

Seluruh aplikasi wajib:

* Menggunakan elemen HTML semantik.
* Mendukung keyboard navigation.
* Memiliki label untuk kontrol formulir.
* Memiliki kontras warna yang memadai.
* Menggunakan atribut ARIA hanya bila diperlukan.

Accessibility bukan fitur tambahan, melainkan bagian dari kualitas aplikasi.

---

# 14. Styling

Standar organisasi:

* Gunakan Design System.
* Gunakan design tokens.
* Hindari inline style kecuali untuk kasus yang sangat spesifik.
* Hindari duplikasi aturan CSS.

---

# 15. API Integration

Seluruh komunikasi API:

* Berada di service layer.
* Tidak dilakukan langsung di komponen presentasi.
* Memiliki penanganan loading, error, dan retry bila sesuai.

Komponen tidak boleh mengetahui detail implementasi HTTP.

---

# 16. Error Handling

UI harus menangani:

* Loading.
* Empty State.
* Error State.
* Retry.

Gunakan Error Boundary untuk menangkap kesalahan render pada area aplikasi yang sesuai.

---

# 17. Testing

Minimal:

* Unit Test untuk logika penting.
* Component Test.
* Integration Test.

Perubahan bug wajib disertai pengujian regresi.

---

# 18. Security

Wajib:

* Sanitasi data yang dirender bila berasal dari sumber yang tidak tepercaya.
* Hindari penggunaan HTML mentah kecuali benar-benar diperlukan dan telah divalidasi.
* Jangan menyimpan secret di frontend.
* Validasi otorisasi tetap dilakukan di backend.

---

# 19. Anti-Patterns

Tidak diperbolehkan:

* Business logic kompleks di komponen UI.
* Prop drilling yang berlebihan.
* State yang diduplikasi.
* Komponen yang terlalu besar.
* Side effect saat proses render.
* Penggunaan `any` pada props.
* Inline function yang berlebihan pada jalur kritis performa tanpa alasan yang jelas.

---

# 20. AI Coding Agent Rules

AI Coding Agent wajib:

* Membuat komponen kecil dan fokus.
* Menggunakan TypeScript secara penuh.
* Menempatkan logika bisnis di layer yang sesuai.
* Menambahkan atau memperbarui pengujian.
* Mengikuti Design System.
* Memastikan komponen memenuhi standar aksesibilitas.

---

# 21. Code Review Checklist

Reviewer memastikan:

* Komponen memiliki satu tanggung jawab.
* Props bertipe dengan benar.
* State tidak berlebihan.
* Tidak ada business logic di komponen presentasi.
* Accessibility terpenuhi.
* Pengujian memadai.
* Kepatuhan terhadap AEP-007, AEP-007-TS, dan AEP-007-REACT.

---

# 22. Production Readiness Checklist

Sebelum rilis:

* Build berhasil.
* Type checking lulus.
* Linter dan formatter lulus.
* Pengujian relevan lulus.
* Accessibility dasar diverifikasi.
* Bundle size ditinjau.
* Error Boundary tersedia pada area yang sesuai.
* Dokumentasi diperbarui.

---

# 23. Compliance

Seluruh aplikasi React wajib mematuhi standar ini.

Pengecualian hanya diperbolehkan melalui Architecture Decision Record (ADR) atau mekanisme governance yang berlaku.

---

# 24. Future Extensions

Standar ini akan diperluas menjadi:

* **AEP-007-REACT-NEXT** — Next.js Standards.
* **AEP-007-REACT-STATE** — State Management Standards.
* **AEP-007-REACT-UI** — Design System Standards.
* **AEP-007-REACT-A11Y** — Accessibility Standards.
* **AEP-007-REACT-PERF** — Performance Standards.
* **AEP-007-REACT-TEST** — React Testing Standards.
