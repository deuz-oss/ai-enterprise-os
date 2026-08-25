# Feature Roadmap

Rujukan kebutuhan lengkap: [PRD](PRD.md).

| Fase | Milestone | Isi utama | Status |
|------|-----------|-----------|--------|
| 1 | **MVP: Pre-sales s/d Rekrutmen** | Pipeline lead, aktivitas, konversi ke klien, upload dokumen legalitas (PKS/addendum), job order, database kandidat, seleksi & placement | ✅ Selesai |
| 2 | HRD | Database karyawan, kontrak kerja, tracking tanda tangan, dokumen HR (KTP/NPWP/BPJS), reminder akhir kontrak | ✅ Selesai |
| 3 | Operasional | Payrol bulanan, PPh21 (pasal 17 & TER), monitoring approval klien, integrasi absensi | ✅ Selesai |
| 4 | Finance | Invoice otomatis dari payrol + fee, pajak (PPN/PPh23), aging & overdue tracking, cash flow | ✅ Selesai |
| 5 | Akunting | Jurnal umum, buku besar, neraca saldo, laporan Neraca/Laba Rugi/Arus Kas | ✅ Selesai |
| 6 | AI Layer | Screening CV otomatis, matching kandidat ↔ job order, Q&A dokumen kontrak (RAG), forecast cash flow | ✅ Selesai — LLM via API kompatibel OpenAI (`AI_BASE_URL` di .env); embedding untuk RAG via `AI_EMBEDDING_MODEL` |
| Lanjutan | Platform | Mobile app (Flutter), multi-tenant SaaS untuk perusahaan outsourcing lain, integrasi API (e-signature, BPJS) | ✅ Selesai — TTE kontrak (sandbox/PrivyID), rekap iuran BPJS + ekspor CSV portal, mobile app internal v1 (`mobile/`), dan **multi-tenant SaaS** (shared schema + `tenant_id`, provisioning via `/platform/tenants`). Tersisa: kredensial PrivyID produksi & API resmi BPJS bila tersedia |
| 7 | **Platform Multi-App & UI Notion** (repositioning ala Mekari) | App registry + entitlement/lisensi per tenant (trial 14 hari, guard 403, nav dinamis, halaman upsell); design system Notion-style (token Inter/dark mode, sidebar workspace + app launcher, ⌘K, view tabel/papan, aksen warna per app); packaging standalone/bundle/full package | ✅ Selesai — entitlement + guard + launcher (`/apps`), design system + ⌘K + dark mode, kanban Pipeline. Tersisa polish: page tree (ditunda), papan Kandidat, emoji judul di semua halaman. Mockup: `docs/design/mockup-notion-ui.html`, spesifikasi: [PRD §4–5](PRD.md) |
| 8 | **Absensi** | Record harian (status, clock-in/out, lembur, sumber), impor CSV mesin fingerprint, integrasi cuti/izin ESS, validasi dua jalur (internal→HR, outsourcing→Ops), agregasi bulanan otomatis | 🔜 Direncanakan — spesifikasi: [PRD Fase 8](PRD.md) |
| 9 | **Payrol Dua Jalur, Saltab Digital, PR & Invoice** | `employment_type` internal/eksternal; payrol internal (HR) vs proyek per klien (Ops) dengan approval klien ber-token; Saltab digital (komponen line-item, prorata otomatis dari absensi, grid editable, ekspor Excel/PDF); BPJS dua sisi (perusahaan→invoice, karyawan→potongan THP); workflow Payment Request dengan approval atasan configurable; jurnal otomatis saat FINALIZED | 🔜 Direncanakan — spesifikasi: [PRD §6–7](PRD.md) |
| 10 | **Accounting ala Accurate + AI Akuntansi** | Bagan akun dinamis + template outsourcing; jurnal memorial/terposting; mesin auto-journal berbasis rule config; modul kas-bank (rekonsiliasi), pembelian, aset tetap (depresiasi otomatis); periode & tutup buku; dimensi klien/proyek → laba rugi per kontrak; laporan lengkap (arus kas tidak langsung, aging); AI: auto-kategori OCR, rekonsiliasi bank cerdas, asisten tutup buku, tanya-laporan NL→SQL, narasi eksekutif, prediksi pembayaran klien, deteksi anomali/kepatuhan | 🔜 Direncanakan — spesifikasi: [PRD §8](PRD.md) |
| 11 | **Chat Workspace ala Slack** *(gratis di semua paket)* | Channel publik/private/DM/broadcast, thread, reaksi, mention, unread, pencarian; channel otomatis per entitas (job order, payrol per periode, onboarding); notifikasi interaktif dengan tombol aksi; **karyawan outsourcing ikut ter-scope per proyek** — hanya sesama se-proyek + tim Ops proyeknya, tak bisa menemukan/menyebut user lain (dipaksakan server-side); keanggotaan tersinkron dari placement; WebSocket real-time | 🔜 Direncanakan — spesifikasi: [PRD §9](PRD.md) |
| 12 | **AI Kolaborasi** *(gelombang 2 chat)* | Asisten @AEOS via DM (RAG lintas app), rangkuman thread, digest harian, slash command (`/pr`, `/cuti`, `/jo`), routing pertanyaan ke tim yang tepat | 🔜 Direncanakan — spesifikasi: [PRD §9.6](PRD.md) |
| 13 | **Talent Pool & CV Standardization** | Upload CV (PDF/DOCX/scan via OCR) → LLM ekstraksi ke skema tetap → draft profil terstruktur + dokumen CV standar bertemplate dengan branding per tenant; review recruiter (confidence highlighting) → finalize; versioning CV + snapshot saat submission; screening/matching AI beralih ke data terstruktur; filter/facet talent pool | 🔜 Direncanakan — spesifikasi: [PRD §10](PRD.md) |

## Prinsip pengembangan

0. Repositioning v1.1: fitur baru dieksekusi **setelah** entitlement (Fase 7)
   agar setiap kemampuan sejak awal dapat dipaketkan/dijual per aplikasi.
1. Setiap fase menghasilkan fitur yang **dipakai beneran** sebelum fase berikutnya dimulai.
2. Modul backend ditambah sebagai *module* baru di monolith (`backend/app/modules/<nama>`)
   dengan pola yang sama: `models.py → schemas.py → service.py → router.py`.
3. Rate/config pajak dan parameter regulasi dipisah dari kode.
