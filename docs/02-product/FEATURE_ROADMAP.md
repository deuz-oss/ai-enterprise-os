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
| Lanjutan | Platform | Mobile app (Flutter), multi-tenant SaaS untuk perusahaan outsourcing lain, integrasi API (e-signature, BPJS) | 🔄 Berjalan — TTE kontrak ✅, rekap iuran BPJS + ekspor CSV portal ✅, mobile app internal v1 ✅ (`mobile/`, butuh `flutter create .` untuk build); API resmi BPJS & multi-tenant menyusul |

## Prinsip pengembangan

1. Setiap fase menghasilkan fitur yang **dipakai beneran** sebelum fase berikutnya dimulai.
2. Modul backend ditambah sebagai *module* baru di monolith (`backend/app/modules/<nama>`)
   dengan pola yang sama: `models.py → schemas.py → service.py → router.py`.
3. Rate/config pajak dan parameter regulasi dipisah dari kode.
