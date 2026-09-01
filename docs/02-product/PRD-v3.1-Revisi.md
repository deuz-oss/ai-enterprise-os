# PRD v3.1 — Revisi Patch atas v3.0 (Final Bundle Opsi F)

**Merevisi:** `PRD-v3.0.md` (2026-08-30 Draft Final)
**Status:** Revisi — draft, belum diimplementasikan (rencana teknis lengkap ada di plan file kerja, bukan di dokumen ini)
**Penulis patch:** Audit gap + riset arsitektur pembanding (2026-09-01)
**Ringkasan patch:** 5 isu ditutup — 1 infrastruktur AI (metering), 3 perluasan Recruitment (pipeline, Job Order, AI Interview), 1 kapabilitas baru (Job Portal). Perubahan bersifat aditif — tidak ada perubahan model bisnis/harga SKU dari v3.0 (lihat §2 v3.0, tidak diubah patch ini).

**Catatan cakupan**: dokumen ini mencatat KEPUTUSAN produk & alasan bisnisnya (kenapa), bukan skema tabel/kode implementasi lengkap (bagaimana) — detail teknis penuh ada di plan file kerja sesi implementasi, disebutkan referensinya di tiap patch.

---

## Patch 1 — AI Usage Metering: Instrumentasi Token/Biaya per Tenant (baru)

**Masalah v3.0 §2.2:** SKU **AI Add-on** dideklarasikan harga `300/1k token`, tapi tidak ada satu pun mekanisme yang benar-benar menghitung/mencatat pemakaian token per tenant. Endpoint laporan usage yang sudah dibangun (`GET /platform/tenants/{id}/usage`) punya baris "AI Add-on" yang permanen `amount: None` dengan catatan eksplisit di kode: *"Pemakaian token belum diinstrumentasi"*.

**Konteks bisnis**: Brian memutuskan strategi AI di AEOS pakai model berbayar/frontier untuk performa terbaik, karena biaya ditagihkan ke klien + margin — bukan lagi soal "harus gratis". Konsekuensinya, pencatatan usage yang akurat jadi prasyarat wajib sebelum fitur AI apa pun (termasuk Patch 4 di bawah) ditambah, supaya penagihan berbasis data nyata, bukan estimasi.

**Revisi**: Tabel `ai_usage_events` (tenant_id, feature, model, token in/out, status, cost_idr) diinstrumentasi SENTRAL di satu titik pemanggilan AI (`core/llm.py`), bukan di tiap 15 titik panggil manual — supaya tidak ada yang lupa terinstrumen. Biaya (`cost_idr`) disimpan best-effort/nullable; token mentah jadi sumber kebenaran (harga vendor berubah-ubah, dihitung ulang kapan saja tanpa migrasi data).

**Kode terdampak**: `backend/app/core/llm.py`, `backend/app/core/ai_usage.py` (baru), 8 modul pemanggil AI (`talentpool`, `recruitment`, `ai/*`, `accounting/ai_accounting.py`), migrasi Alembic baru, `backend/tests/conftest.py`.

---

## Patch 2 — Recruitment: Pipeline Sourcing→Onboarding Diperluas (menggantikan bagian §4 v3.0)

**Masalah v3.0 §4:** Recruitment didokumentasikan sebagai "JO stage + TalentPool + 3 action (interview/offering/onboard)" — jauh lebih kasar dari alur operasional nyata SPC. Alur asli: Sourcing (Talent Pool/AI Matching + Job Portal, lihat Patch 5) → Screening → Interview Rekruter (internal) → Submission (rekruter→Ops→klien) → Klien Screening Ulang → Interview User (klien) → OJT (kondisional per JO) → Offering → Onboarding — 9 tahap, bukan 3 action generik.

**Revisi**: `PlacementStatus` (entitas penaut Candidate↔JobOrder, dipilih alih-alih `CandidateStatus` karena satu kandidat bisa dikejar untuk beberapa JO sekaligus dengan tahap berbeda-beda) diperluas dari 4 nilai jadi 13 tahap eksplisit: `sourced→screening→interview_rekruter→disubmit→dikirim_ke_klien→screening_klien→interview_klien→ojt→proposed→accepted→onboarded` (+ `rejected`/`cancelled` sebagai status terminal dari tahap manapun). Makna `proposed`/`accepted`/`onboarded` yang sudah ada (offering letter, esign) TIDAK berubah — cuma ditambah 8 tahap eksplisit sebelum itu. `InterviewSchedule` (state machine §11 v3.0) tambah field `interview_type` (internal/klien) supaya 1 kandidat bisa punya jadwal internal & klien yang jelas beda perannya, bukan cuma dibedakan urutan waktu.

**OJT**: flag `JobOrder.requires_ojt` (boolean per Job Order, bukan per Client — sebagian posisi dari klien yang sama bisa beda kebijakan OJT-nya). UI pipeline skip tahap OJT kalau `False`.

**Kode terdampak**: `backend/app/modules/recruitment/models.py` (`PlacementStatus`, `InterviewSchedule.interview_type`, `JobOrder.requires_ojt`), `recruitment/service.py` (`create_placement()` default status berubah dari `proposed` jadi `sourced` — regresi disengaja), migrasi Alembic, `frontend/src/pages/JobOrders.tsx`.

---

## Patch 3 — Job Order: Field Operasional Tambahan (menggantikan bagian §4/§11 v3.0)

**Masalah v3.0 §4:** `JobOrder` (state machine §11: `open→screening→interview→offering→filled→closed`) tidak punya field yang dipakai operasional sehari-hari SPC: Request ID (nomor requisisi, kadang dari klien kadang perlu auto-generate), Request Date + alert 30 hari belum filled, Area, Contract Duration, Gross Salary tunggal (beda dari `salary_min/max` yang dipakai AI Matching), dan status bisnis level tinggi (Open/On Hold/Cancel/Filled) yang beda konsep dari status pipeline rekrutmen yang sudah ada di §11.

**Revisi**: 6 field baru ditambah ke `JobOrder` — `request_id` (auto-generate `JO/{tahun}/{urutan}` kalau klien tidak kasih, ikut pola penomoran `EMP-0001`/`INV/2026/0001` yang sudah ada), `request_date` + fungsi `is_stale()` (alert on-read, bukan cron baru), `area`, `contract_duration_months`, `gross_salary` (field BARU terpisah dari `salary_min/max` — field lama tetap dipakai AI Matching untuk skor kecocokan ekspektasi gaji, tidak dihapus), `business_status` (Open/OnHold/Cancel/Filled — field TERPISAH dari status pipeline §11 v3.0 yang tetap dipertahankan apa adanya, bukan pengganti).

**Tambahan (dari kebutuhan dokumentasi komunikasi Operation↔TAD)**: dokumen "Job Order – Manpower Requisition" fisik yang selama ini dipakai internal bisa diupload saat create JO → field di-auto-fill dari ekstraksi AI (pola sama seperti CV Intake yang sudah ada), field kosong diisi manual. Dokumen sumber disimpan & bisa dilihat lagi lewat klik "Request ID" di tabel JO.

**Kode terdampak**: `backend/app/modules/recruitment/models.py`/`schemas.py`/`service.py`, endpoint ekstraksi baru, `frontend/src/pages/JobOrders.tsx`, migrasi Alembic.

---

## Patch 4 — AI Interview (kapabilitas baru di bawah Talent Cloud)

**Masalah v3.0 §2.2/§4:** Talent Cloud sudah punya AI Matching native, tapi tidak ada kapabilitas penilaian kandidat berbasis AI Interview — hanya `InterviewSchedule` manual (jadwal + feedback teks bebas dari interviewer manusia).

**Riset pembanding**: 5 repo open-source AI interview dibedah (DeepInterview, Aural, OpenInterview, FoloUp, Liftoff) untuk cari pola yang matang, bukan asal fork. Pola yang konvergen di ≥2 repo dan diadopsi: (a) reasoning berat dipisah dari momen live — cocok pola async MVP; (b) skor AI wajib lewat gate approval manusia sebelum final (persis prinsip `CONFIDENCE_THRESHOLD` yang sudah dipakai AEOS di CV Intake); (c) definisi interview (template+kriteria) terpisah dari instance/response.

**Revisi**: 2 entitas baru — `AIInterviewTemplate` (definisi: pertanyaan bertipe + kriteria penilaian, JSON fleksibel ikut pola `CvIntake.extracted`) dan `AIInterviewResponse` (instance per kandidat, akses via `invite_token` tanpa akun — kandidat AEOS tidak pernah punya akun `User`). **MVP mode async** (kandidat jawab teks/rekaman, diproses belakangan) — BUKAN voice real-time (kompleksitas infra jauh lebih tinggi, ditunda ke fase 2 kalau memang dibutuhkan; kalau/ketika dibutuhkan, rekomendasi "beli" kapabilitas voice dari vendor pihak ketiga alih-alih membangun sendiri, sejalan Patch 1's keputusan bayar-untuk-performa). Skor AI **wajib** direview manusia (`review_status`) sebelum dianggap final — tidak pernah otomatis jadi keputusan hire/reject.

**Kode terdampak**: modul baru `backend/app/modules/ai_interview/`, migrasi Alembic, integrasi `feature="ai_interview.*"` ke Patch 1 (`ai_usage_events`).

---

## Patch 5 — Job Portal: Sourcing Kandidat via Lamaran Publik (kapabilitas baru di bawah Talent Cloud)

**Masalah v3.0 §2.2:** Talent Cloud cuma punya 1 sumber sourcing — Talent Pool internal (kandidat diupload staf). Sourcing dari kandidat yang apply sendiri ke lowongan yang di-post publik (setara jalur JobStreet) belum ada sama sekali.

**Riset pembanding**: teardown level produk JobStreet (bukan arsitektur teknis — JobStreet tidak publikasikan itu) menemukan 2 fondasi terbesar yang biasanya perlu dibangun dari nol **sudah ada** di AEOS: profil kandidat terstruktur (lewat `CvIntake` yang sudah ada) dan tracking status lamaran bertahap (lewat `PlacementStatus` 13-tahap dari Patch 2). Yang benar-benar baru cuma titik masuk publik.

**Revisi**: Guest-apply (tanpa wajib akun kandidat, berbeda dari JobStreet — konsisten pola `invite_token` yang sudah dipilih AEOS di Patch 4) ke `JobOrder` yang ditandai `is_public=True`. Portal diakses per-tenant (`{tenant_slug}`, sejalan sifat white-label AEOS — bukan satu marketplace gabungan lintas-tenant). Nama klien di lowongan publik SENGAJA tersamar (`public_client_label`, terpisah dari `client.name` asli) — kebutuhan nyata yang ditemukan langsung dari dokumen Job Order internal SPC yang memuat instruksi eksplisit menyembunyikan identitas klien di lowongan publik. Screening question custom per JO (maks beberapa pertanyaan) mengurangi beban tahap `screening` manual di Patch 2.

**Kode terdampak**: modul baru `backend/app/modules/job_portal/`, `JobOrder` tambah `is_public`/`public_client_label`/`screening_questions`, `Placement` tambah `application_token`/`screening_answers`, halaman publik frontend baru (`/careers/{tenant_slug}`), migrasi Alembic.

---

## Ringkasan Dampak ke §2 v3.0 (Portofolio SKU)

**Tidak ada SKU baru, tidak ada perubahan harga.** Kelima patch di atas semuanya masuk kapabilitas yang sudah dideklarasikan v3.0:
- Patch 1 → mengisi instrumentasi yang sudah dijanjikan SKU **AI Add-on** (300/1k token) tapi belum ada mekanismenya.
- Patch 2, 3 → memperjelas & melengkapi **Talent Cloud** (`sales_crm`+`recruitment`) yang di v3.0 baru didokumentasikan kasar ("3 action").
- Patch 4, 5 → perluasan cara *talent record* masuk & dinilai dalam **Talent Cloud** — tetap sejalan klarifikasi v3.0 §2.2 ("bukan jualan kandidat, tagih per record + compute").

## Status Implementasi

Kelima patch di atas **belum satu pun dieksekusi ke kode** — semuanya masih draft rencana teknis (skema tabel, endpoint, migrasi) di plan file kerja sesi ini. Dokumen ini mencatat keputusan & alasan bisnisnya supaya tidak hilang; detail implementasi menyusul per-patch saat masing-masing mulai dikerjakan.

---

*Dokumen ini merevisi (menambah di atas, bukan mengganti) `PRD-v3.0.md` — model bisnis/bundling/harga v3.0 §1-§2 tetap berlaku penuh.*
