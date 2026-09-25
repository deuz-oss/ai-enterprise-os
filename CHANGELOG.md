# Changelog

Semua perubahan penting pada AI Enterprise OS dicatat di sini.

Format mengikuti [Keep a Changelog](https://keepachangelog.com/id/1.1.0/).

## [Unreleased]

### Added — Fase 66: AI Interview — uji E2E suara & dengar bukti mode suara

Detail di `PRD.md` Fase 66.
- Kutipan bukti hasil interview suara real-time kini bisa diklik untuk memutar rekaman sesi di detik kandidat mulai mengucapkannya (agen mengirim offset waktu per baris transkrip; migrasi `ad1e2f3a4b5c`).
- Setting `LIVEKIT_PUBLIC_URL` (URL LiveKit untuk browser kandidat), `STT_TIMEOUT_SEC`, `VAD_MIN_SILENCE`, `ENDPOINTING_MIN_DELAY/MAX_DELAY` (agen), `STT_COMPUTE_TYPE` (stt-server).

### Fixed — Fase 66 (ditemukan uji E2E suara dengan kandidat sintetis)
- **Agen suara tidak pernah bisa mendengar kandidat**: plugin STT LiveKit 1.7 memakai model default `gpt-4o-mini-transcribe` yang ditolak faster-whisper self-hosted (500); percakapan selalu macet setelah pertanyaan pertama. Kini model whisper dikirim eksplisit (`STT_MODEL`).
- **Kandidat di browser tidak bisa terhubung ke LiveKit** di setup Docker: `voice/start` mengembalikan host internal `ws://livekit:7880`. Kini memakai `LIVEKIT_PUBLIC_URL` (default compose `ws://localhost:7880`).
- Jawaban pertama tiap interview hilang: model whisper dilepas setelah 5 menit idle dan memuat ulang 39 dtk (> batas 30 dtk plugin STT). Kini model tetap dimuat dan memakai `int8` di CPU (transkripsi 9 dtk audio: 21 dtk -> 4 dtk).
- Timeout STT 10 dtk bawaan LiveKit + ulang 3x membuat tiap jawaban ditranskripsi ulang sampai 4x (jeda 78 dtk); kini 60 dtk, 1x ulang.
- Jawaban 2 kalimat terpotong: jeda antarkalimat memecah jawaban jadi segmen STT terpisah dan agen pindah pertanyaan sebelum kalimat terakhir tertranskripsi. Kini VAD menunggu 1,2 dtk hening.
- "Nilai ulang" interview suara menilai jawaban kosong (skor hilang); kini menilai transkrip.
- Offset per baris transkrip tidak sejajar bila ucapan AI berisi baris baru; kini satu pesan = satu baris.

### Fixed — cek gap Fase 65
- Template AI Interview tidak bisa dikaitkan ke job order dari UI (form tanpa kolom job order, PATCH tidak menerima `job_order_id`, tombol "Mode AI" di Job Order hanya membawa kandidat) -- akibatnya keputusan pipeline di review (Fase 64) tidak pernah tersedia. Kini form punya pilihan job order (terkunci bila template sudah dipakai), tombol "Mode AI" membawa job order, template aktif job order itu terpilih otomatis, dan ada ajakan membuat template bila belum ada.
- `job_order_id` template tidak divalidasi: UUID sembarang -> error 500 di PostgreSQL, ID job order tenant lain diterima.
- Validasi struktur template (Fase 65) mengunci template lama yang tersimpan dengan ID pertanyaan ganda: tidak bisa diaktifkan, diarsipkan, atau diganti judul. Kini validasi hanya berjalan bila pertanyaan/kriteria benar-benar diubah.

### Added — Fase 65: AI Interview — edit, duplikat & arsip template

Detail di `PRD.md` Fase 65.
- Template AI Interview kini bisa diedit (sebelumnya hanya bisa dibuat). Template yang sudah dipakai kandidat mengunci pertanyaan, kriteria, dan mode supaya hasil lama tetap sebanding; judul, tujuan, pedoman percakapan, dan pengaturan pertanyaan susulan tetap bisa diubah.
- Tombol Duplikat (salinan draft langsung terbuka untuk diedit) dan Arsipkan.

### Fixed — Fase 65
- Form template membuat ID pertanyaan `q{jumlah+1}`: menghapus pertanyaan lalu menambah yang baru menghasilkan ID ganda, dan jawaban kandidat (dipetakan lewat ID) tertimpa diam-diam. Kini ID unik, dan backend menolak ID pertanyaan/kunci kriteria ganda serta pertanyaan yang merujuk kriteria tidak ada.

### Fixed — cek gap AI Interview (setelah Fase 62-64)
- Kandidat mode rekaman bisa terkunci permanen (tidak bisa rekam ulang maupun mengirim interview): saat 3x suara tidak tertangkap, saat STT server gangguan (kegagalan sistem ikut memakan jatah rekam), atau saat proses transkripsi hilang (status "diproses" abadi). Kini gangguan sistem mengembalikan jatah, transkripsi macet >10 menit dianggap gagal sistem, dan jawaban yang jatahnya habis boleh dikirim kosong.
- Endpoint jawaban teks tidak memeriksa mode template: di mode rekaman, jawaban teks menimpa rekaman sehingga file suaranya tertinggal di storage tanpa ikut terhapus retensi/penarikan persetujuan; di mode suara real-time, kandidat bisa melewati percakapan dengan mengetik jawaban lalu submit. Pertanyaan yang tidak ada di template juga kini ditolak.
- Unggahan rekaman jawaban (endpoint publik) dibaca utuh ke memori sebelum ukurannya dicek; kini dibatasi selama streaming (413).
- "Nilai ulang" setelah review membuat status "disetujui" menempel pada skor baru yang belum dilihat reviewer; kini review kembali ke "menunggu review" (diaudit).
- Kandidat yang datanya sudah dihapus (UU PDP) masih bisa diundang AI Interview lagi; kini dilewati dan disembunyikan dari daftar undangan.
- Daftar respons AI Interview tidak lagi membawa timestamp per kata (bisa ribuan per respons).

### Added — Fase 64: AI Interview — bukti bertimestamp, konsistensi skor, integrasi pipeline

Fase 5 roadmap AI Interview. Detail di `PRD.md` Fase 64.
- Kutipan bukti di halaman review bisa diklik untuk memutar rekaman jawaban tepat di detik kutipan (timestamp per kata dari faster-whisper; WhisperX tidak diperlukan).
- Penilaian AI dijalankan 2x secara independen (`AI_INTERVIEW_SCORING_RUNS`); skor dirata-rata dan kriteria yang hasilnya berbeda jauh ditandai "tidak stabil".
- Ringkasan kalibrasi per template: berapa hasil AI yang disetujui/dikoreksi reviewer dan rata-rata koreksinya. Skor AI asli kini tersimpan saat disesuaikan (migrasi `9c0d1e2f3a4b`).
- Saat review, staf bisa sekaligus memindahkan kandidat di pipeline job order (submit ke klien, interview klien, atau tidak lolos). Selalu keputusan manusia.

### Added — Fase 63: AI Interview — alur terstruktur & pedoman percakapan

Fase 4 roadmap AI Interview. Detail di `PRD.md` Fase 63.
- Agen suara kini mengajukan pertanyaan satu per satu sesuai urutan template; kuota pertanyaan susulan per pertanyaan (0-3, dengan fokus yang digali) dan syarat penutupan dijaga kode, bukan hanya prompt. Agen tidak bisa pindah pertanyaan atau menutup interview sebelum kandidat menjawab (ditemukan lewat simulasi dengan LLM sungguhan).
- Penutup interview berupa kalimat baku yang selalu terucap sebelum panggilan diakhiri.
- Setting opsional `AI_AGENT_MODEL` untuk model agen suara (disarankan `gpt-4.1-mini`, paling patuh di simulasi).
- Pedoman percakapan (jika kandidat ... -> jawaban baku): aturan bawaan terkunci (atribut dilindungi, skor, manipulasi), pedoman per template, dan jawaban default (gaji, info tidak tersedia, minta berhenti, minta ulang). Aturan bawaan tampil di editor template.
- Pertanyaan/pedoman yang menanyakan agama, suku, status pernikahan, kehamilan, usia, orientasi seksual, atau pandangan politik ditolak saat template disimpan.
- Transkrip suara diberi penanda per pertanyaan, tampil sebagai judul bagian di halaman review.
- Penilaian mengabaikan pertanyaan kandidat soal gaji dan info pribadi yang dilindungi (`RUBRIC_VERSION` 2026-09-25). Migrasi `8b9c0d1e2f3a`.

### Fixed — Fase 63
- Agen suara memutus panggilan (`room.disconnect()`) langsung di dalam tool `end_interview`, sehingga apa pun yang diucapkan sesudahnya terpotong.
- Template lama yang melanggar aturan validasi yang ditambahkan belakangan membuat daftar template error 500; validasi kini hanya saat menyimpan.

### Added — Fase 62: AI Interview — mode rekaman jawaban

Fase 3 roadmap AI Interview. Detail di `PRD.md` Fase 62.
- Mode template `async_recording`: kandidat merekam jawaban suara per pertanyaan di browser (meter level, pratinjau, batas 3 menit), ditranskripsi di background lewat STT (`STT_BASE_URL`, setting baru `STT_MODEL`), lalu dinilai dengan rubrik berbukti.
- Rekam ulang maksimal 3x per pertanyaan (rekaman lama dihapus); kirim ditolak selama ada jawaban yang masih diproses atau suaranya tidak tertangkap.
- Staf bisa memutar rekaman tiap jawaban di halaman review (akses diaudit, tanpa cache).
- Penghapusan data ikut menghapus audio jawaban; versi persetujuan `2026-09-24.3`.

### Fixed — Fase 62
- Halaman sesi kandidat bisa kena 429 karena rate limit 30/jam per IP berlaku juga untuk GET/polling. Sekarang baca 1200/jam dan tulis 60/jam, per IP+token.

### Added — Fase 61: AI Interview — rekaman sesi, transkrip rapi, auth agent

Fase 2 roadmap AI Interview. Detail di `PRD.md` Fase 61.
- Rekaman sesi suara 2 kanal (kandidat / pewawancara AI) direkam agent, disimpan di object storage, diputar di halaman review (WaveSurfer.js); akses diaudit, link 15 menit, tanpa cache browser. Agent menolak merekam bila terhubung ke LiveKit Cloud.
- Transkrip dirapikan LLM untuk dibaca; transkrip asli tetap dasar penilaian (bisa di-toggle).
- Interview yang diputus kandidat tetap terkirim (transkrip parsial).
- Penghapusan data (retensi/penarikan/forget) ikut menghapus file rekaman.

### Security — Fase 61
- Endpoint khusus agent suara (`voice/context`, `voice/complete`, `voice/recording`) wajib tanda tangan HMAC agent; dulu kandidat bisa mengirim transkrip karangan dan membaca kriteria/bobot penilaian dengan invite token-nya.

### Fixed — Fase 61
- Semua link unduhan file (CV, dokumen, kontrak, selfie, rekaman) di setup Docker menunjuk ke host internal `minio:9000` sehingga tidak bisa dibuka browser. Setting baru `STORAGE_PUBLIC_ENDPOINT`; produksi melayani MinIO lewat `files.<DOMAIN>` di Caddy (butuh DNS record).

### Added — Fase 60: AI Interview — turn detector, rubrik berbukti, tampilan review

Fase 1 roadmap AI Interview. Detail di `PRD.md` Fase 60.
- Agen suara: turn detector lokal `v1-mini` (mendukung Bahasa Indonesia, tanpa LiveKit Cloud) + endpointing lebih sabar untuk jeda berpikir kandidat; STT dipaksa bahasa Indonesia; dependensi LiveKit dipin 1.7.x; bobot model diunduh saat build.
- Penilaian berbasis rubrik: tiap kriteria wajib punya kutipan persis jawaban kandidat, diverifikasi server; kutipan karangan/kalimat pewawancara dibuang; kriteria tanpa bukti tidak dihitung; skor total dihitung server (rata-rata berbobot).
- `AI_SCORING_MODEL` opsional untuk uji A/B model penilai (mis. Sahabat-AI/SEA-LION).
- Halaman review: kartu per kriteria dengan bar skor, alasan, kutipan bukti; jawaban kandidat mode teks kini bisa dilihat.
- Fix test flaky `test_match_job_order_ranking_dan_reuse` (bergantung detik pembuatan kandidat di SQLite).

### Added — Fase 59: AI Interview — fondasi kepatuhan (persetujuan, retensi, larangan analisis emosi)

Fase 0 roadmap AI Interview, prasyarat sebelum fitur rekaman suara. Detail di `PRD.md` Fase 59.
- Kandidat wajib menyetujui ketentuan pemrosesan data (UU PDP) sebelum interview; semua aksi sesi ditolak tanpa persetujuan. Versi ketentuan & waktu tersimpan per respons.
- Kandidat bisa menarik persetujuan kapan saja: jawaban, transkrip, dan hasil AI dihapus, link terkunci.
- Retensi per tenant (default 180 hari, 30–730, diubah role management) dengan pembersihan otomatis.
- Kriteria template yang menilai emosi/nada suara/aksen/ekspresi ditolak; prompt penilaian melarang inferensi dari cara bicara.
- Halaman admin: status persetujuan & penghapusan per respons, kartu privasi + pengaturan retensi, dan error simpan template kini tampil (sebelumnya gagal diam-diam).
- Migrasi `6f7a8b9c0d1e` (kolom persetujuan/pembersihan + tabel `ai_interview_settings` dengan RLS).

### Changed — Fase 58: Redesign Chat (review UI/UX)

**Bug yang ditemukan saat review**
- Pengirim pesan tampil sebagai potongan UUID (`dc3c770c…`) -- API cuma mengirim `sender_id`. Kini `sender_name`, `sender_role`, `is_bot` (akun @AEOS), `reply_count`, `my_reactions` ikut di payload pesan.
- Membuka channel menampilkan area pesan **kosong** sampai polling 4 dtk berikutnya: Virtuoso merender nol item saat mount (props data terisi, rentang internal kosong -- terukur lewat fiber props di browser). Diperbaiki dengan `initialItemCount` + scroll eksplisit ke pesan terbaru.
- Tombol "Balas" hanya muncul di pesan milik sendiri -- tidak bisa membalas orang lain di thread.
- Kartu PR mengulang judulnya sebagai teks pesan tepat di atas kartu.

**Struktur & layout**
- Tinggi penuh (`100vh - 7rem`) menggantikan `64vh` + header halaman bersubjudul marketing ("Gratis di semua paket").
- Sidebar dikelompokkan (Channel / Pesan langsung / Proyek klien / Payroll / Job order, bisa dilipat, prefiks "JO:"/"Proyek:" dibuang), pencarian channel, pratinjau pesan terakhir, unread tebal + badge aksen. Form "channel baru" jadi tombol `+`.
- Header percakapan: nama + jumlah anggota, aksi jadi ikon (cari, disematkan, digest, menu notifikasi dgn penjelasan tiap level). Tombol "Tandai dibaca" dihapus (sudah otomatis saat channel dibuka).
- Mobile: daftar channel dan percakapan bergantian penuh-lebar dengan tombol kembali.

**Pesan**
- Avatar inisial + nama + jam (HH.mm, tanggal lengkap di tooltip), pemisah hari ("Hari ini", "Kemarin", "Kamis, 3 September"), pesan beruntun pengirim sama digabung (< 5 menit).
- 6 emoji + pin + edit + hapus yang dulu menempel permanen di bawah SETIAP pesan jadi toolbar hover/fokus; chip reaksi hanya bila ada, reaksi milik sendiri disorot.
- Bot @AEOS: avatar Sparkles + badge "AI"; @mention disorot; kartu aksi dengan aksen kiri dan area tombol terpisah; tautan "N balasan" ke thread; pesan induk ditampilkan di atas thread.
- Composer: textarea auto-tinggi (Enter kirim, Shift+Enter baris baru), tombol kirim ikon, petunjuk pintasan, error unggah lampiran ditampilkan.
- Empty/loading state yang benar (dulu "Belum ada pesan. Mulai percakapan!" tampil walau belum memilih channel).

Validasi: `tsc` + build bersih; diverifikasi live (light/dark, iframe 400px utk mobile karena jendela browser tak bisa di-resize -- DES-014); kontras WCAG dihitung per pasangan warna baru (semua >= 4.5:1; inisial avatar sempat 2.31:1 di light mode, sudah diperbaiki).

### Fixed — Fase 57: Audit backend keamanan & logika + uang Decimal

Audit modul-per-modul backend (bagian yang paling jarang diaudit dibanding UI).

**Keamanan**
- **[Kritis] Eskalasi ke platform_admin**: admin tenant bisa `POST /auth/register` atau `PATCH /auth/users/{id}` dengan `role=platform_admin` lalu lolos `require_platform_admin()` -> kuasai `/platform/*` lintas tenant (suspend/provisioning/billing tenant lain). Ditolak di `create_user` & `update_user`; guard platform kini juga mewajibkan akun tanpa tenant.
- `/files/{path}`: cek traversal pakai `str.startswith` (lolos ke folder saudara `uploads-*`) -> `Path.is_relative_to`.
- Billing: subscribe/top up/auto-reload bisa dipanggil role apa pun (termasuk karyawan) -> `BILLING_MANAGE_ROLES` (finance/management + admin), sama dengan menu.
- `GET /overview` (revenue, piutang, pipeline, klien) terbaca akun karyawan outsourcing -> 403; mereka tetap pakai `/overview/personal`.
- Pages (wiki internal): baca daftar/isi halaman terbuka untuk karyawan -> staf saja.
- Chat: reaksi tanpa cek akses channel; `add_member` menerima id user tenant lain/fiktif; pesan terhapus masih bisa diedit.
- ESS: HR yang juga karyawan bisa menyetujui cuti/lembur/koreksi absensinya sendiri -> ditolak (pemisahan tugas).

**Payroll & keuangan (uang)**
- Perhitungan PPh 21, BPJS, slip, invoice kini `Decimal` + pembulatan rupiah setengah-ke-atas (`app/core/money.py`). Dulu `float` + `round()` bawaan (banker's rounding): mis. 5.500.200 x 0,25% = 13.750,5 -> 13.750, seharusnya 13.751.
- PKP Pasal 17 dibulatkan ke bawah ribuan penuh sebelum tarif.
- Menambah bonus/THR/insentif di grid Saltab dulu tidak menghitung ulang PPh 21 (kurang potong). Kini `pph21` yang masih `auto` dihitung ulang dari bruto kena pajak; reimbursement, perdin, dan pencairan gaji ditahan dikecualikan (bukan objek / sudah dipajaki).
- Komponen baru yang ditambahkan ke slip terhitung dobel di agregat `gross`/`net_pay` tersimpan (append setelah flush).
- Kode komponen sistem (`pph21`, `gaji_pokok`, dst) bisa dipakai komponen manual -> menimpa pajak asli. Nominal tahan gaji bisa diubah dari grid (tidak lagi sama dgn `SalaryHold`). Tahan gaji melebihi gaji bersih. Allowance/potongan/tarif lembur negatif saat generate. Semua kini ditolak.
- Kegagalan query tarif PPh 21/BPJS/biaya admin bank dulu ditelan diam-diam -> jatuh ke konstanta/0. Lookup biaya bank kini case-insensitive.
- Jurnal otomatis `invoice_issued` timpang sebesar PPh 23 (Dr piutang sudah net) -> akun baru `1-1350 PPh 23 Dibayar di Muka`; `post_auto_event` kini menolak jurnal tidak seimbang dan melengkapi akun template yang belum ada di tenant lama.

**Keandalan**
- WebSocket chat menahan satu koneksi pool DB sepanjang sesi -> ~15 user online menghabiskan pool seluruh API.
- `_get_admin_user_id` `MultipleResultsFound` di tenant dengan >1 admin/user -> channel JO/proyek/payroll tak pernah dibuat (error ditelan).
- Cek tabrakan cuti -> 500 bila ada >=2 pengajuan bertabrakan.
- Impor CSV (absensi, rekening koran, lead): file Excel cp1252 -> 500; tanpa batas ukuran -> kini fallback cp1252 + batas 5 MB.

### Fixed — Fase 56: DES-015 — 4 aksi destruktif lain tanpa konfirmasi

Ditemukan saat sweep DES-008 (Sprint 1) tapi sengaja tidak difix saat itu (di luar scope yang disepakati) -- dikerjakan sekarang atas permintaan eksplisit.

- `revokePortalAccess` (`ClientDetail.tsx`) -- cabut akses portal klien, sebelumnya langsung jalan tanpa konfirmasi. Paling severe: klien bisa mendadak tidak bisa login ke portalnya sendiri karena satu misklik.
- `revokeOnboardingInvite` (`JobOrderDetail.tsx`) -- tombolnya sudah `variant="danger"` (merah) tapi itu cuma gaya visual, bukan konfirmasi sungguhan.
- `removeLeadContact` (`Leads.tsx`) -- hapus kontak dari lead.
- `removeLogo` (`TalentPool.tsx`) -- hapus logo klien, severity paling rendah (cuma gambar).

Semua dibungkus `confirmToast()`, pola identik dengan DES-008. Diverifikasi live pada `revokePortalAccess` (yang paling severe): toast konfirmasi "Cabut akses portal klien ini? Klien tidak akan bisa login ke portalnya lagi sampai link baru dibuat." muncul, klik Batal mempertahankan akses. `tsc --noEmit` + `npm run build` bersih.

### Fixed — Fase 55: Sprint 4 audit desain 2026-09-15 (polish — badge dark-mode, urutan form, zero-state, AI UX)

- **DES-005**: badge `bg-{hue}-50/100 + text-{hue}-600/700` yang tidak pernah dimigrasi dark mode sama sekali (`Finance.tsx` kotak risiko/rekomendasi/aging, `AccountingAi.tsx` badge status jurnal AI, `TalentPoolPanels.tsx` badge "CV belum diunggah") ditambah pasangan `dark:bg-{hue}-500/10 dark:text-{hue}-400`, mengikuti pola `CALLOUT_TONES` yang sudah ada di `components/workspace.tsx`. Sweep app-wide mengonfirmasi tidak ada instance lain -- ketemu 1 bonus: `Pages.tsx` tombol hapus halaman (`hover:bg-rose-50` tanpa varian dark).
- **DES-012**: form "buat baru" dipindah ke bawah daftar/pencarian existing di Talent Pool (`Tambah Kandidat`) dan Accounting tab Jurnal (`Jurnal Umum Baru`) -- isi form tidak berubah sama sekali, cuma urutan render, karena browse adalah tugas yang lebih sering di kedua halaman ini.
- **DES-006**: kartu KPI "Revenue MTD" (Dashboard) sekarang bilang "Belum ada invoice — buat dari Quotation" saat tenant benar-benar belum punya invoice sama sekali, bukan cuma "0 invoice tercatat" yang tidak membedakan "baru mulai" dari "genuinely nol".
- **DES-002**: widget "Tanya Kontrak (AI)" di Employees.tsx dapat ikon `Sparkles` yang sama dengan FAB "Tanya AEOS AI" dan kartu "AI Executive Digest" Dashboard -- supaya ketiganya kebaca sebagai satu kapabilitas AI, bukan fitur lepas-lepas. `@AEOS` di Chat sudah punya hint yang cukup lewat placeholder input pesannya sendiri, tidak disentuh.
- Validasi: `tsc --noEmit` + `npm run build` bersih di tiap tahap; diverifikasi live browser (Finance dark mode, Talent Pool, Accounting Jurnal, Dashboard, Employees).

### Fixed — Fase 54: Sprint 3 audit desain 2026-09-15 (lanjutkan rollout design system)

Bukan temuan baru — menuntaskan rollout pola dashboard yang sudah direncanakan sejak 2026-09-12 (`design.md` §5a) tapi belum sempat menjangkau semua halaman target.

- **DES-004** (`HeaderCanvas`): diterapkan ke `JobOrders.tsx`, `Employees.tsx`, `Payroll.tsx` (sebelumnya cuma Dashboard.tsx). Komponen `HeaderCanvas` ditambah prop opsional `actions?: ReactNode` (backward-compatible -- Dashboard.tsx yang tidak mengisinya tetap sama persis) supaya tiap halaman bisa taruh primary action (tombol "+ Job Order Baru", dst.) atau filter sendiri berdampingan dengan header, tanpa perlu date-range picker (`showRangePicker={false}` di ketiga halaman ini -- belum ada kebutuhan filter tanggal, beda dari Dashboard).
- **DES-003** (restyle tabel): `JobOrders.tsx` dan tabel run `Payroll.tsx` dapat perlakuan `py-1.5` per-sel (32-36px target, sama seperti `Employees.tsx`) -- avatar+nama TIDAK ditambahkan (barisnya job order/payroll run, bukan orang, jadi pattern itu genuinely tidak relevan). `StatusPill` dapat domain baru `payroll_run` menggantikan `STATUS_LABELS` lokal di `Payroll.tsx`.
- **DES-013**: AI Interview (`AIInterview.tsx`) dapat KPI row (Total Template/Aktif/Draft/Arsip) yang sebelumnya tidak ada sama sekali di halaman ini, beda dari hampir semua modul lain. Filter tabs SENGAJA tidak ditambahkan -- daftar template biasanya cuma segelintir baris, filter tidak menambah nilai di list sekecil itu.
- Validasi: `tsc --noEmit` + `npm run build` bersih di tiap tahap; diverifikasi live browser (light mode) di keempat halaman.

### Fixed — Fase 53: Sprint 2 audit desain 2026-09-15 (bracket PPh21, Kanban, label Referral)

- **DES-010**: form "Versi Baru PPh 21" (Rates) sebelumnya minta admin ketik 4 tabel bracket pajak (Pasal 17 + TER A/B/C, TER masing-masing ~26-27 baris di kode Python) lewat textarea JSON mentah tanpa validasi apa pun -- salah ketik sekali berarti salah potong PPh 21 semua karyawan tanpa ketahuan sampai payroll jalan. Diganti `BracketRowsEditor` (baru, lokal di `Rates.tsx`): baris per-bracket (batas atas Rp + tarif %, checkbox "tak terbatas" cuma di baris terakhir), validasi ascending + tarif 0-100% sebelum submit, tidak ada JSON yang terekspos ke user. Form juga sekarang otomatis terisi dari versi PALING BARU yang sudah ada (`pph21.data[0]`) begitu dibuka, jadi admin EDIT tabel existing (26-27 baris) alih-alih ngetik dari nol.
- **DES-009**: Kanban Job Orders (tab Candidates) bisa terlihat kosong padahal kandidatnya ada, cuma tersembunyi di kolom tahap ke-9 yang perlu discroll horizontal jauh. Ditambah auto-scroll ke kolom terisi pertama begitu data termuat (`JobOrderDetail.tsx`) -- terverifikasi live di job order "Operator Produksi" yang jadi bukti temuan aslinya.
- **DES-011**: input nominal reward di Referral tidak pernah menampilkan placeholder-nya ("Nominal reward (Rp)") karena `defaultValue`-nya `0` (bukan string kosong) -- placeholder browser cuma tampil saat field genuinely kosong, jadi field ini terlihat seperti angka polos tanpa arti. Diganti jadi `<label>` persisten yang selalu terlihat, bukan bergantung ke placeholder.
- Validasi: `tsc --noEmit` + `npm run build` bersih (frontend-only, tidak ada perubahan backend di sprint ini).

### Fixed — Fase 52: Sprint 1 audit desain 2026-09-15 (reminder kontrak & konfirmasi hapus)

- **DES-001**: `GET /employees/contracts/expiring` tidak punya batas bawah tanggal dan tidak sadar rantai perpanjangan kontrak -- kontrak yang sudah kedaluwarsa bertahun-tahun lalu, atau yang sudah digantikan lewat `previous_contract_id` (Tier 2), tetap ikut tampil di banner "Reminder Kontrak ≤30 hari" (Karyawan) & KPI "Kontrak Akan Berakhir" (Overview) sebagai "0 hari lagi" karena `max(days_left, 0)` menutupi tanggal yang sudah lewat. Diperbaiki: tambah `end_date >= today`, exclude kontrak yang direferensikan sebagai `previous_contract_id` kontrak lain, hapus clamp. Diverifikasi live: banner & KPI yang sebelumnya salah tampil sekarang kosong/benar untuk data dummy yang memicu bug ini.
- **DES-008**: 6 tombol hapus (bukan 5 -- ditemukan 1 lagi saat perbaikan) langsung memanggil `mutate()` tanpa dialog konfirmasi sama sekali, atau (khusus `Accounting.tsx`) pakai `window.confirm()` native alih-alih `confirmToast()` yang sudah jadi standar app sejak audit 2026-09-12. Dibungkus `confirmToast()` di `Chat.tsx` (hapus pesan), `EmployeeDetail.tsx` (hapus kontak darurat), `ClientDetail.tsx` (hapus site), `TalentPoolPanels.tsx` (hapus pengalaman kerja), `Payroll.tsx` (hapus komponen payroll), `Accounting.tsx` (hapus jurnal draft). Diverifikasi live di EmployeeDetail. Sweep lanjutan menemukan 4 aksi destruktif lain yang masih tanpa konfirmasi (`revokePortalAccess`, `revokeOnboardingInvite`, `removeLeadContact`, `removeLogo`) -- sengaja TIDAK diperbaiki di fase ini, dicatat sbg DES-015 di `docs/design/PRODUCT_DESIGN_AUDIT-2026-09-15.md` menunggu approval terpisah.
- Regresi backend: `test_expiring_contracts_excludes_past_and_superseded` (baru, `test_hrd.py`); full suite + ruff + mypy + `tsc --noEmit` bersih.

### Added — Fase 51: HRD — validasi otomatis rekening bank karyawan (api.co.id)

- Integrasi vendor opsional baru `app/core/bank_validation/` (adapter interface + factory `get_adapter()`, provider `""`/`sandbox`/`api_co_id`) -- mirror persis pola `app/core/payment/` (Xendit) yang sudah ada. api.co.id dipilih (Rp 50rb/bulan flat, bukan platform disbursement penuh) setelah riset provider mana yang paling murah/gampang diintegrasikan.
- `Employee` dapat 4 field baru: `bank_code` (slug bank kanonik provider, berdampingan dgn `bank_name` teks bebas lama yg TIDAK di-backfill) dan 3 field server-computed `bank_account_verified`/`_name`/`_at`.
- Validasi jalan **otomatis** saat HR menyimpan `bank_code`+`bank_account` di form edit karyawan (bukan tombol terpisah) -- best-effort, pola sama `core/geocoding.py::reverse_geocode`: kegagalan/nonaktifnya provider TIDAK PERNAH menggagalkan simpan data karyawan utama. Mengubah `bank_code`/`bank_account` lagi otomatis mereset status verifikasi lama sebelum dihitung ulang.
- Endpoint baru `GET /employees/bank-options` -- daftar bank diambil LIVE dari provider (`GET /validation/bank/available`), bukan di-hardcode (hindari risiko salah slug).
- UI: field "Nama Bank" yg dulu teks bebas jadi `<select>` terisi dari endpoint di atas; badge status "✓ Terverifikasi (nama di bank: ...)" / "⚠ Rekening tidak ditemukan/tidak aktif" / "belum diverifikasi" di Employee Detail.
- Nama pemilik rekening dari api.co.id SENGAJA tersamar sebagian (kebijakan privasi provider, mis. "Rif\*\*\*\* Eln\*\*\*\*") -- tidak ada logika pencocokan nama otomatis, HR yang eyeball manual.
- Migrasi `4d5e6f7a8b9c`, tervalidasi lewat `test_upgrade_head_identik_dengan_create_all`. Di luar cakupan (sengaja): form onboarding self-service kandidat, wiring ke anomali Payroll, adapter Xendit utk bank validation (trivial ditambah nanti, reuse `xendit_api_key` yg sudah ada).
- Cek-gap saat implementasi: `BANK_VALIDATION_PROVIDER` sempat lupa didaftarkan di `conftest.py` (daftar provider berbayar yang di-blank paksa utk tiap test run, pola sama `AI_BASE_URL`/`GOOGLE_OAUTH_*`) -- tanpa ini, kalau developer set `api_co_id`+API key asli di `.env` lokalnya, seluruh test suite diam-diam akan memanggil vendor berbayar sungguhan. Ditemukan lewat test suite penuh yang gagal 1 kasus, diperbaiki di akar.

### Added — Fase 50: HRD — gap-fill profil karyawan dari audit MYOHRIS

- Field identitas baru di `Employee`: `email`, `birthdate`, `birthplace`, `gender`, `kk_no`, `religion`, `blood_type`, `education`, `current_position` -- yang punya padanan di `Candidate` (`birthdate`/`gender`/`education`/`current_position`/`blood_type`/`birthplace`, sejak Fase 24) sekarang disalin otomatis saat onboarding, bukan ditinggal begitu saja.
- Kontak darurat jadi tabel one-to-many (`employee_emergency_contacts`, CRUD sendiri) menggantikan 3 kolom flat yang cuma nampung satu kontak; data lama di-backfill sbg kontak utama.
- `placement_client_name`/`placement_job_title` (properti model, join lewat placement->job_order->client) supaya klien penempatan karyawan eksternal kebaca di profil.
- `ptkp_label` (computed, reuse rumus `payroll/tax.py`) supaya status PTKP kebaca langsung di profil.
- Kontrak kerja bisa diperpanjang (`POST /contracts/{id}/extend`) dengan rantai riwayat (`previous_contract_id`); `contract_type` (PKWT/PKWTT) + validasi total durasi PKWT maksimal 5 tahun termasuk semua perpanjangan (UU Cipta Kerja), dihitung dari kontrak AWAL rantai. Validasi & guard "cuma kontrak terbaru boleh diperpanjang" ditegakkan di satu tempat (`create_contract`) supaya berlaku di semua jalur yang menulis `previous_contract_id`/`contract_type`/tanggal -- bukan cuma endpoint `/extend`, termasuk: `PATCH /contracts/{id}` langsung, `previous_contract_id` yang ditulis manual lewat `POST /contracts` biasa (bisa bikin cabang ganda atau rantai lintas-karyawan kalau tidak dicek), dan penghapusan kontrak yang masih dirujuk perpanjangannya (409, bukan sukses diam-diam meninggalkan referensi menggantung -- SQLite tidak menegakkan FK secara default).
- `division`/`position` jadi field live di `Employee` (dulu cuma snapshot before/after di `EmployeeMovement`); mencatat movement baru sekarang otomatis mensinkron grade/level/division/position ke Employee.
- UI Employee Detail: header menampilkan jabatan/divisi/tanggal masuk/kontrak aktif + link klien penempatan; baris Data Pribadi, Rekening Bank (field sudah ada di backend tapi sebelumnya tidak ada UI sama sekali), PTKP; kartu Kontak Darurat; tab Absensi baru (rekap bulanan + tabel harian per karyawan, reuse endpoint attendance/payroll yang sudah ada); badge rantai perpanjangan & PKWT/PKWTT di tab Kontrak Kerja.
- Migrasi: `7fffe60cc637`, `9a1c2e3f4b5d`, `2b3c4d5e6f7a`, `3c4d5e6f7a8b` -- semua tervalidasi lewat `test_upgrade_head_identik_dengan_create_all`.
- Sengaja tidak termasuk: field `manager_id` (atasan langsung) -- dilewati atas keputusan eksplisit.
- Diverifikasi hidup di browser (data dummy) untuk semua alur: isi field baru, tambah/hapus/jadikan-utama kontak darurat, buat & perpanjang kontrak PKWT sampai kena batas 5 tahun, tab Absensi menampilkan rekap nyata.

### Fixed — Fase 49: Absensi — RBAC endpoint tulis/baca tanpa pembatasan role

- `POST/GET /attendance/records` dan `POST /attendance/import` sebelumnya cuma dicek `get_current_user` tanpa `require_roles` sama sekali -- role `karyawan` bisa melihat rekap absensi siapa pun atau memalsukan record lewat form admin. Menu sidebar "Absensi" juga tidak punya `roles` (beda dari item admin lain di `NAV_ITEMS`), jadi celah ini juga terlihat di UI.
- Command Palette (Ctrl/Cmd+K) punya daftar `QUICK_ACTIONS` internal terpisah yang tidak ikut difilter role sama sekali -- lolos dari fix sidebar di atas. Dipindah ke `Layout.tsx` supaya reuse logika filter role yang sama dengan `NAV_ITEMS`, bukan sumber ganda yang gampang divergen lagi.
- Ditambahkan `ATTENDANCE_ROLES` (admin/hr/operations/management) di `core/permissions.py`, diterapkan ke ketiga endpoint + nav item + terdaftar di `test_rbac_matrix.py`. Tes HTTP eksplisit ditambahkan yang membuktikan role karyawan mendapat 403 di ketiga endpoint tersebut.

### Added — Fase 48: CRM — Ringkasan AI Lead

- Redesain dari "AI enrichment" trycompai/crm (agent riset web + evidence-scoring) yang tadinya ditandai out-of-scope: `core/llm.py` Aeos tidak punya web search/tool-calling, jadi meniru apa adanya berisiko halusinasi fakta perusahaan. Diganti: LLM cuma merangkum data yang staf sendiri sudah masukkan (catatan, aktivitas, kontak & peran, nilai potensi) -- bukan riset fakta baru.
- Tabel baru `ai_lead_briefs` (riwayat ringkasan, pola sama `AIScreening`). Endpoint `POST/GET /ai/leads/{lead_id}/brief` (guard `AI_PRESALES_ROLES`, di dalam `ai/router.py` existing).
- UI: seksi "Ringkasan AI" di panel detail Lead -- tombol "Buat Ringkasan AI"/"Buat Ulang Ringkasan". Diverifikasi hidup di browser dengan AI sungguhan: ringkasan yang dihasilkan berpijak pada data lead asli.

### Added — Fase 47: CRM — sync Gmail/Google Calendar ke Activity lead

- Modul baru `integrations/` (OAuth per-user, bukan tenant-wide): koneksi Google milik staf sendiri, tabel baru `google_mailbox_connections`. Config `GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI` kosong => fitur nonaktif (503), pola sama `AI_BASE_URL`/`SMTP_HOST`.
- Sync manual per-lead (tombol "Sync Lead Ini") -- BUKAN polling otomatis, mengikuti konvensi codebase ini yang memang tidak punya scheduler background sama sekali.
- `LeadActivity` dapat `external_source`/`external_id` untuk dedup sync berulang. Endpoint `GET/POST /integrations/google/*` (authorize, callback publik, status, connection, sync/{lead_id}).
- 2 bug ditemukan & diperbaiki lewat 11 tes yang mock API Google: callback OAuth kehilangan konteks tenant (di-fix lewat `state` JWT bawa tenant_id), dan datetime naive dari SQLite bikin perbandingan kedaluwarsa token error.
- UI: seksi "Sync Google" di panel detail Lead. Belum diverifikasi ke Google sungguhan (perlu OAuth app + akun asli, di luar cakupan sesi ini).

### Added — Fase 46: CRM — multi-currency untuk nilai potensi lead

- `Lead` dapat `currency` (ISO 4217, default IDR) dan `fx_rate_to_idr` (kurs manual snapshot, bukan API live), terinspirasi `Deal.amount/currency/baseAmount/baseCurrency/fxRate` trycompai/crm.
- Fix bug nyata: `funnel_stats` sebelumnya menjumlah `estimated_value` mentah lintas currency -- sekarang menjumlah nilai IDR-nya (`estimated_value * fx_rate_to_idr`) supaya tidak mencampur satuan uang.
- Validasi: IDR selalu kurs 1 (tidak bisa di-override); ganti ke currency asing wajib sertakan kurs di request yang sama.
- UI: tampilan per-lead format sesuai currency aslinya, semua agregat (KPI/kanban) pakai nilai IDR. Field "Mata Uang" edit-di-tempat di panel detail Lead.

### Added — Fase 45: CRM — suppression list (company/contact "jangan hubungi lagi")

- Tabel baru `suppressed_contacts` (menunjuk company ATAU contact, XOR), terinspirasi `SuppressedDomain`/`SuppressedContact` trycompai/crm. Beda sengaja dari "Black Lists" rekrutmen yang sudah ada: administratif ringan, aktif langsung tanpa approval, tidak memblokir hard proses lain — murni daftar + peringatan visual.
- Endpoint `GET/POST /suppressed-contacts`, `DELETE /suppressed-contacts/{id}`.
- UI: halaman baru `/suppressed-contacts` (nav CRM), banner peringatan kuning di panel detail Lead kalau company/kontaknya ada di daftar ini.

### Added — Fase 44: CRM — tampilan Pipeline tersimpan (Saved Views)

- Tabel baru `saved_lead_views` (filter tersimpan: tahap/pemilik/pencarian/mode tampilan, opsional dibagikan ke tim), terinspirasi `SavedView` trycompai/crm.
- Sekalian menutup 2 celah UI nyata: input pencarian nama perusahaan (backend sudah lama dukung `q`, belum pernah ada UI-nya) dan filter "Pemilik" deal.
- Endpoint `GET/POST /leads/saved-views`, `DELETE /leads/saved-views/{id}` (privat vs dibagikan; hanya pembuat yang bisa hapus).
- UI: pill "Tampilan Tersimpan" di atas tabel Pipeline untuk menerapkan/menghapus, tombol "+ Simpan Tampilan Ini".

### Added — Fase 43: CRM — follow-up terjadwal & widget "Tugas Jatuh Tempo"

- `LeadActivity` dapat `due_at`/`completed_at` + tipe aktivitas baru `tugas`, terinspirasi `Activity.dueAt`/`completedAt` trycompai/crm.
- Endpoint `GET /leads/activities/due` (daftar tugas lintas semua lead, filter `overdue_only`/`include_completed`) dan `PATCH /leads/activities/{id}` (toggle selesai).
- UI: form Aktivitas dapat input jadwal opsional, badge "Terlambat" untuk tugas lewat tempo, widget baru "Tugas Jatuh Tempo" di halaman Pipeline (klik untuk buka lead, checkbox tandai selesai tanpa pindah halaman).

### Added — Fase 42: CRM — bundel field sales-ops (target closing, alasan menang/kalah, kecepatan tahap)

- 4 kolom baru di `Lead`: `expected_close_date` (manual), `closed_reason` (manual, kondisional saat deal/gagal), `stage_changed_at`/`last_activity_at` (auto, tidak bisa dipalsukan lewat PATCH klien) — terinspirasi `Deal.stageChangedAt`/`closedReason`/`expectedCloseDate`/`lastActivityAt` trycompai/crm.
- UI: indikator "sudah N hari di tahap ini", input Target Closing, field Alasan Menang/Kalah kondisional, baris read-only Aktivitas Terakhir.

### Added — Fase 41: CRM — field kustom admin-configurable (Company/Contact/Lead)

- Tabel baru `custom_field_definitions`/`custom_field_options`/`custom_field_values` (satu tabel value polimorfik untuk 3 entitas), terinspirasi `FieldDefinition`/`FieldValue` trycompai/crm. 9 tipe field dengan validasi per tipe.
- Endpoint CRUD definisi + upsert nilai (`/custom-fields/definitions`, `/custom-fields/values`).
- UI: komponen reusable `CustomFieldsSection` dipasang di level Lead, Company, dan per-kontak (expandable) di `Leads.tsx`. Hapus field pakai `confirmToast`, bukan `window.confirm`.

### Added — Fase 40: CRM — multi-contact per lead dengan peran (LeadContact)

- Tabel baru `lead_contacts` (junction Lead↔Contact + `role` teks bebas), terinspirasi pola `DealContact` trycompai/crm — satu lead/deal bisa punya beberapa PIC dengan peran berbeda (Decision Maker, Champion, dst.), beda dari `Company.contacts` yang cuma satu PIC "primary" per company.
- Endpoint `GET/POST /leads/{id}/contacts`, `PATCH/DELETE /leads/contacts/{lead_contact_id}`.
- UI: seksi "Kontak Terlibat" di panel detail Lead — tambah/hapus PIC, edit peran inline.

### Added — Fase 39: Pola Dashboard Baru (KpiCard/DonutChart/StatusPill/HeaderCanvas) + fix kontras warna semantik

- `KpiCard` diperluas: ikon jadi lingkaran tinted + delta indicator opsional (belum dipasang di mana pun — `/overview` belum punya data perbandingan periode sungguhan).
- `DonutChart` baru (library recharts, dipilih via skill `/pick-ui-library`): total di tengah cincin + legend persentase. Diterapkan di Overview "Status Kandidat".
- `StatusPill` baru: konsolidasi mapping status→warna (payment request, invoice, margin, status karyawan) yang sebelumnya tersebar per halaman. Job Order status (select interaktif) dan tahap `PlacementStatus` (sistem dot multi-tahap) sengaja tidak dipaksa ke pola ini.
- `HeaderCanvas` baru: greeting + headline + subtext + date-range picker (presentasional, backend belum dukung filter tanggal) — diterapkan di Overview.
- Sidebar: nav aktif dari fill solid ke tint lembut + teks `var(--accent)`; struktur/urutan menu tidak berubah.
- Restyle tabel (avatar+nama, `tabular-nums`, `StatusPill`, tinggi baris 32-36px): `Employees.tsx` dan tabel invoice Overview.
- Fix kontras: `text-red/rose/emerald/amber-{500,600,700}` sebagai teks polos gagal WCAG AA di salah satu tema — ~140 titik di 33 file diperbaiki (dihitung exact via rumus luminance, bukan tebakan); `emerald-600`/`amber-600` base dinaikkan ke 700 karena gagal light mode sama sekali.

### Added — Fase 37-38: Audit UI/UX menyeluruh — priority backlog, aksesibilitas (axe-core), siklus "cek gap"

- **Fase 37**: quick-win (state `:active` tombol, crossfade tema, transisi progress bar, `prefers-reduced-motion`), medium polish (`color-scheme` native control, `sonner` toast + `confirmToast`/`promptToast` menggantikan `window.confirm`/`prompt`), EmployeeDetail mode lihat/edit per field (Ringkasan lalu BPJS & Cuti), pre-flight confirm sebelum cancel Job Order/Run Payroll beranomali, migrasi token warna dituntaskan (`PlacementStatus` disatukan ke `lib/pipelineStages.ts`).
- **Fase 38**: audit `axe-core` live ke seluruh halaman internal + 5 portal token-based. Temuan sistemik: teks putih di atas `--accent` gagal kontras dark mode (token `--accent-contrast` baru), warna kategori sidebar gagal kontras di kartu gelap (token `--cat-*`), `.th`/`--text-muted` di atas `--hover` gagal kontras app-wide (token `--th-color`), label `<label>` tak terhubung `htmlFor`/`id` (accessible name salah/kosong, tidak terdeteksi axe), kartu/baris `onClick` tanpa `tabIndex`/keyboard access (7 titik).

### Added — Fase 36: Portal ESS — shift default per karyawan, reverse geocoding, halaman Absensi tersendiri

- `Employee.shift_start_time`/`shift_end_time` ditampilkan di Portal Saya sebagai jam kerja standar.
- Reverse geocoding best-effort (Nominatim) untuk alamat clock-in/out dari GPS — tidak pernah memblokir absensi.
- Portal Saya: absensi dipindah ke halaman tersendiri (tombol "Buka Absensi"), menggantikan widget selalu-terbuka di beranda.
- Fix bug: `mobile_clock()` tidak memanggil `recompute_month_summary()` — absensi mobile tidak muncul di riwayat/rekap bulanan.
- Sidebar jadi drawer overlay di mobile (hamburger + backdrop, tutup otomatis saat pindah halaman).

### Added — Fase 35: Klien — halaman detail bertab + kolom Jobs count

- Halaman baru `ClientDetail.tsx` (`/clients/:id`), mirror arketipe tab horizontal `EmployeeDetail.tsx`/`JobOrderDetail.tsx`: tab Ringkasan (+ form edit `PATCH /clients/{id}` yang sebelumnya tidak pernah dipanggil dari UI), Jobs, Karyawan (endpoint baru — employee eksternal yang pernah ditempatkan di klien), Dokumen, Portal & Lokasi (pindahan dari panel inline lama), Riwayat (audit log, admin/management saja).
- `create_client`/`update_client`/`delete_client` sekarang mencatat `audit.log_event`.
- `Clients.tsx` disederhanakan jadi list-only (mirror `Employees.tsx`); tabel tambah kolom Jobs dari `job_count` (satu query outerjoin+group_by).
- Dibandingkan langsung ke referensi MyOHRIS; field yang di luar cakupan (Client Reference/Code/Type/Industry, Fee Settings, Team/multi-Contact) sengaja tidak ditambahkan.

### Added — Fase 34: Geofencing absensi (radius per lokasi klien)

- Model `ClientSite` (`client_sites`, RLS) — klien multi-cabang bisa punya banyak lokasi, masing-masing radius sendiri. Migrasi `4eae323acbfb`.
- `Employee.site_id` nullable — kosong = absen bebas (perilaku lama, nol regresi), terisi = wajib dalam radius site itu saat clock-in/out (validasi haversine di `ess/service.py::mobile_clock`). Fail-open kalau site dihapus tapi `site_id` tersisa.
- CRUD lokasi (`/clients/{id}/sites`, `/clients/sites` lintas klien) + kartu "Lokasi Kantor" di halaman Klien (tombol "Pakai Lokasi Saat Ini" via GPS browser) + dropdown "Lokasi Kerja" di Employee Detail.

### Added — Fase 33: Sederhanakan Pipeline Penempatan + Tutup Celah Email Dokumen HR

- `PlacementStatus` disederhanakan 13→11 tahap (kirim/screening klien digabung `submitted`; diusulkan/disetujui klien digabung `offering`); OJT jadi kondisional lewat `JobOrder.requires_ojt`; `rejection_note` wajib diisi saat placement gagal/dibatalkan.
- Surat penawaran dan kontrak kerja (TTE) sekarang benar-benar mengirim email ke kandidat/calon karyawan — sebelumnya cuma tersimpan/di-upload provider tanpa notifikasi nyata. Mengirim surat penawaran otomatis memindahkan kandidat ke status `hired`.
- Undangan onboarding punya daftar dokumen per-undangan (bukan 3 jenis tetap); placement otomatis pindah ke `onboarded` begitu kandidat selesai mengisi form, tidak lagi menunggu HR klik "Terapkan" manual.
- `OfferingSettings` digeneralisasi jadi `HrDocumentSettings` (satu setting per tenant untuk alamat pengembalian dokumen, dipakai bersama offering letter + kontrak).

### Added — Fase 32: Portal Klien (monitoring kehadiran & lembur read-only, tanpa akun)

- Model `ClientPortalAccess` — link ber-token **persisten** (beda dari token sekali-pakai payroll/onboarding), satu baris per klien, regenerate mencabut token lama. Migrasi `a7b8c9d0e1f2`.
- Endpoint publik `GET /clients/portal/{token}` (rate-limited) + endpoint internal generate/status/revoke di bawah role Clients.
- Halaman publik `ClientPortal.tsx` (`/clients/portal/:token`, tanpa Layout/sidebar) — read-only murni, tidak ada tombol approve (approval kehadiran/lembur tetap jalur internal HR/Ops).
- Kartu "Portal Klien" di halaman Klien (HR) untuk generate/salin link, cabut akses.

### Added — Fase 31: Portal ESS clock-in/out (UI web) + alur pengajuan lembur

- `GET /me/attendance/today` + seksi "Absen Masuk/Keluar" di Portal Saya (GPS + selfie kamera) — backend sudah ada dari sesi sebelumnya, sekarang punya UI web.
- Model `OvertimeRequest` baru (mirror `LeaveRequest`): karyawan ajukan/batalkan, HR setujui/tolak; disetujui → jam otomatis masuk `AttendanceRecord.overtime_hours` (reuse `recompute_month_summary`, ikut otomatis ke Rekap Kehadiran portal, CSV absensi HR, dan Portal Klien). Migrasi `f6a7b8c9d0e1`.

### Added — Fase 30: AI Interview Fase 2 — percakapan suara real-time, self-hosted

- Stack: LiveKit (WebRTC self-hosted) + `faster-whisper-server` (STT self-hosted) + OpenAI (LLM, reuse `core/llm.py`) + TTS OpenAI `gpt-4o-mini-tts` (diganti dari self-hosted `facebook/mms-tts-ind` setelah kualitas suara dinilai tidak layak).
- Worker baru `agent/` (`livekit-agents` SDK Python) — proses long-running pertama di codebase ini; tidak akses Postgres langsung, memanggil REST backend via `invite_token` yang sama seperti kandidat browser. Reuse `_score_transcript()` yang sama dengan mode async teks.
- 4 service Docker baru di bawah profile `voice` (tidak start default). Diverifikasi end-to-end Docker sungguhan; 3 bug nyata ditemukan+diperbaiki (tabrakan port UDP LiveKit, healthcheck `stt-server` salah binary, bit-depth WAV self-hosted TTS vs decoder agent).
- **Status: kode selesai, wiring terverifikasi — performa belum divalidasi** (butuh akses server ber-GPU untuk STT self-hosted).

### Added — Fase 29: Black Lists kandidat

- Alur request→approve untuk menandai kandidat bermasalah (shortlist riset arsitektur MyOHRIS item #3). Model `BlacklistEntry`/`BlacklistStatus`, migrasi `f7g8h9i0j1k2`, halaman `Blacklist.tsx`.
- Diperkecil sengaja dari versi MyOHRIS: satu tabel (bukan request-batch+entry terpisah), tanpa whitelist, belum jadi blocking check di sourcing/matching.

### Added — Fase 23-28: Employee expansion ala MYOHRIS, Contract Generator, Referral, Opsi G billing

- Gelombang polish arketipe (KPI row, tab/pill status filter, Kanban) di atas Component Library Fase 22 (lihat entri "Fase 22" di bawah), diterapkan ke hampir seluruh halaman utama (Blacklist, Quotations, Agreements, Clients, Candidates, TalentPool, JobOrders, Employees, Users, PaymentRequests, Referral, PlatformTenants, Finance/Invoice) serta redesign topbar (kredit widget, menu akun menggantikan tombol "Action Baru" duplikat search) dan rename label sidebar Dashboard→Overview.
- **Fase 23** — Employee: perbaikan RBAC Ops, field SKCK, Warning Letter, kirim Saltab ke klien.
- **Fase 24** — Perluasan field `JobOrder`/`Candidate` ala MYOHRIS (remote, office_address, experience_level, industry, position+level, package_detail; reference kode unik, gender, current_position, alamat lengkap, ktp_no, dll) + stage baru `hired` di `PlacementStatus`. `frequency` (JobOrder) dan `industry`/`current_department` (Candidate) sengaja di-drop dari referensi MYOHRIS.
- **Fase 25** — Employee Contract Generator (template engine terpisah dari generator dokumen Job Order Fase 20).
- **Fase 26** — Employee Detail: riwayat mutasi (movements), data vaksin, kontak darurat, kunci payroll per karyawan, kirim slip gaji via email.
- **Fase 27** — Program Referral karyawan: kode referral, insentif, toggle on/off per tenant.
- **Fase 28** — Migrasi Opsi F→Opsi G (model komersial baru, §4.4 PRD): `TenantSubscription`/`TenantBudgetCycle`/`TenantCreditAccount`/`CreditTransaction`, hapus guard lisensi per-SKU, indikator saldo credit, integrasi Xendit Subscriptions (checkout manual penuh; auto-reload charge sungguhan belum — baru preferensi tersimpan), halaman pembayaran self-service. Script migrasi tenant existing `backend/scripts/fase28_migrate_opsi_f_to_g.py` (`--dry-run` default).
- Perbaikan lintas-fase: employee/candidate detail page bertab, preview PDF slip gaji in-app, form onboarding self-service kandidat via link ber-token, field kandidat Talent Pool bisa dikonfigurasi admin, email pengiriman Quotation/Agreement ke klien, komponen payroll baru (Bonus/Insentif/THR/UUCK/Reimbursement/Perdin/Kasbon + Tahan-Cairkan Gaji), lead sourcing via impor CSV massal, fix bypass RLS di endpoint platform-admin + perluasan RLS ke 14 tabel yang belum tercakup, retire 4 halaman landing "4-Cloud" yang sudah tidak dipakai.

> Detail lengkap tiap fase di atas: `docs/02-product/PRD.md` §5.

### Added — Fase 20 (item 1-4) & Fase 21: Presales Documents, Job Order Enhancements

- **Company/Contact refactor**: `Lead.company_id` jadi FK ke `Company`
  (dengan `Contact[]` multi-kontak per company), menggantikan field bebas
  `company_name`/`contact_*` — migrasi backfill data lama otomatis
  (`b0946b216ff2`). API tetap backward-compatible lewat properti Python.
- **Quotation generator**: `QuotationTemplate` + `Quotation` (state machine
  `draft → pending_approval → approved/rejected → sent`), approval
  single-level, render PDF via `reportlab`. Halaman `Quotations.tsx`.
- **Agreement generator + perluasan Esign**: `AgreementTemplate` +
  `Agreement` (state machine `draft → internal_review → approved/declined
  → sent → signed`), output `.docx` (ground baru, python-docx baru dipakai
  untuk *authoring* pertama kali). `EsignRequest.agreement_id` — modul
  esign sekarang tuntas menandatangani 3 jenis dokumen (kontrak, offering
  letter, agreement). Halaman `Agreements.tsx`.
- **Job Order — field terstruktur**: `benefits`/`working_days`/
  `working_hours_start`/`working_hours_end`, dulunya numpang di teks bebas
  description/requirements.
- **Offering call**: `Placement.offering_call_done`/`offering_call_at` —
  aksi tercatat terpisah dari offering letter+esign yang sudah ada.
- **Unifikasi UI interview**: halaman baru `JobOrderDetail.tsx`
  (`/job-orders/:id`) — pipeline placement via `ProgressStep`, satu tombol
  "Jadwalkan Interview" bercabang ke mode human (form inline) atau AI
  (deep-link ke `AIInterview.tsx` dengan kandidat ter-pre-select). Backend
  tetap 2 sistem terpisah, tidak digabung.
- **Invite kalender `.ics`**: dependency baru `icalendar`; kapabilitas
  attachment email baru di `notifications/service.py` (belum pernah ada
  sebelumnya) — interview terjadwal otomatis kirim `.ics` ke kandidat +
  interviewer, bukan OAuth Google Calendar (keputusan eksplisit).
- **Generate dokumen Job Order**: `JobOrderTemplate` (tanpa `field_schema`
  — isi dokumen 100% dari field JobOrder sendiri, beda dari
  Quotation/AgreementTemplate) + `JobOrder.generated_document_object_key`/
  `generated_document_at`, reuse penuh `presales/rendering.py`.
- **Belum dikerjakan**: Fase 20 item 5 (lead sourcing scraping LinkedIn) —
  menunggu konsultasi legal (UU PDP), sengaja di luar cakupan batch ini.
- Detail keputusan lengkap di `PRD.md` Fase 20 & 21.

### Added — Fase 22: Component Library Frontend (Button, Badge, Card, ProgressStep)

- 4 komponen dasar baru di `frontend/src/components/ui/`: `Button`,
  `Badge`, `Card`, `ProgressStep` (yang terakhir benar-benar baru, 3
  lainnya reuse token `.btn`/`.pill`/`.card` yang sudah ada di
  `index.css`, sekarang lewat API komponen bukan className manual).
- 2 varian baru `.btn-ghost`/`.btn-danger` ditambahkan ke `index.css`.
- Migrasi 3 halaman auth (`Login.tsx`, `ForgotPassword.tsx`,
  `ResetPassword.tsx`) dari hardcode Tailwind `slate-*` ke token
  `var(--...)` + komponen baru — memperbaiki bug tidak merespons dark
  mode yang ditemukan saat audit design-system 2026-09-03.
- Detail keputusan di `PRD.md` Fase 22.

### Added — Polish: Foto Kandidat pada CV Standar & Page Tree Notion

- **Foto kandidat (§10.3)**: unggah/hapus foto (`/talentpool/candidates/{id}/photo`,
  PNG/JPEG ≤5 MB); tampil di header CV standar hanya bila branding tenant
  mengaktifkan `show_photo`; kegagalan baca foto tidak menggagalkan render PDF.
- **Page tree ala Notion (Fase 7 polish)**: modul `pages` — halaman buatan user
  berhierarki (parent/child, ikon emoji, konten) dengan anti-siklus induk dan
  hapus kaskade; editor `/pages/:id` + grup "📄 Halaman" dinamis di sidebar;
  gratis untuk staf internal. Kolom `candidates.photo_object_key` + tabel
  `notion_pages` (migrasi `r8s9t0u1v2w3`).
- Tes: `test_pages.py` (+2), `test_talentpool.py::test_foto_kandidat_toggle_show_photo`.

### Added — Fase 12: AI Kolaborasi (gelombang 2 chat)

- **Asisten @AEOS**: mention `@AEOS` di channel/DM memicu jawaban dari data
  lintas aplikasi terverifikasi (pipeline, job order, kandidat, karyawan, PR,
  invoice, payrol, laba rugi) — LLM sebagai lapisan bahasa dengan fallback
  deterministik; saran routing ke tim yang tepat (Finance / HR-Ops / HR /
  Recruiter / Business Dev) bila pertanyaan di luar cakupan data.
- **Rangkuman thread**: `POST /chat/messages/{id}/summarize` merangkum diskusi
  menjadi poin keputusan/tugas; hasil diposting bot AEOS ke thread.
- **Digest harian** `GET /chat/digest`: item deterministik — PR menunggu
  approval, payrol menunggu persetujuan klien, SLA job order ≤7 hari, kontrak
  berakhir ≤14 hari, invoice overdue; karyawan mendapat versi portal sendiri.
- **Slash command server-side**: `/help`, `/pr status`, `/jo status [kw]`,
  `/cuti sisa`, `/cuti ajukan <jenis> <mulai> <selesai> [alasan]` — dijawab
  bot AEOS sebagai thread reply; perintah personal (`/cuti*`) hanya boleh di DM.
- **Pemisahan paket**: fitur AI ter-guard lisensi `ai_addon`; slash command &
  digest gratis mengikuti chat. Identitas AEOS = user bot per tenant tanpa
  password aktif (tidak bisa login).
- Frontend Chat: tombol 🧵 Rangkum, panel 📋 Digest, hint slash/@AEOS.
- Modul baru `ai/collab.py`; tes `test_fase12_ai_kolaborasi.py` (+6).

### Added — Mobile GPS+selfie Absensi & Logo Branding CV

- **Absensi mobile GPS+selfie (Fase 8 lanjutan)**: `POST /me/attendance/clock-in|clock-out`
  (multipart selfie + koordinat) — satu record per hari (duplikat → 409), selfie
  JPG/PNG ≤5 MB tersimpan sebagai bukti, koordinat divalidasi, notifikasi otomatis
  ke HR/Ops tiap clock. HR/Ops melihat flag selfie + geo di daftar harian dan dapat
  membuka bukti (`GET /attendance/records/{id}/selfie/{which}/download-url`,
  role-gated + audit). Portal `/me` memuat URL selfie milik sendiri. Kolom baru
  `attendance_records` (migrasi `q7r8s9t0u1v2`).
- **App mobile**: tab "Absensi Saya" di Portal karyawan (`self_attendance_screen.dart`)
  — izin lokasi (geolocator) → foto depan (image_picker) → unggah multipart;
  `ApiClient.postMultipart` baru; deps pubspec bertambah geolocator & image_picker
  (verifikasi build butuh Flutter SDK).
- **Logo branding CV (§10.3)**: unggah/hapus logo perusahaan
  (`POST|DELETE /talentpool/branding/logo`, PNG/JPEG ≤2 MB, admin/management);
  logo tampil di header PDF CV standar; preview via panel "🎨 Branding CV Standar"
  pada halaman Talent Pool.
- Tes: `test_mobile_absensi.py` (+4), `test_talentpool.py::test_logo_upload_render_dan_hapus`.

### Added — Fase 13: Talent Pool & CV Standardization

- **Pipeline intake CV** (`POST /talentpool/intake`, modul `talentpool` baru,
  migrasi `p6q7r8s9t0u1`): unggah PDF (teks/scan), DOCX, atau gambar → deteksi
  jenis dokumen → ekstraksi LLM ke **skema tetap berversi** (scan/gambar via satu
  panggilan vision). File asli tersimpan sebagai bukti sumber dan tidak pernah
  ditimpa; intake gagal tetap tercatat dan bisa diproses ulang (`/reprocess`).
- **Confidence per kelompok field + review wajib**: skor model dikoreksi
  deterministik (validasi email/telepon, kelengkapan data); kelompok di bawah
  ambang 0.7 wajib dicek recruiter sebelum finalisasi; koreksi inline tersimpan.
- **Dokumen CV standar berversi**: finalisasi merender PDF struktur konsisten
  (identitas → ringkasan → pengalaman → pendidikan → skill/sertifikasi/bahasa →
  data penempatan) dengan **branding per tenant** (warna aksen + footer,
  configurable); tiap finalize membuat versi baru; **placement baru otomatis
  mengunci versi terbaru** sebagai bukti submission ke klien (§10.3).
- **Facet talent pool**: `GET /talentpool?q=&domisili=&skill=&readiness=&tp_status=`
  sesuai skema seragam §10.2.
- **Kepatuhan UU PDP**: consent wajib saat unggah; hak hapus subjek
  (`POST /talentpool/candidates/{id}/forget`) menghapus profil/snapshot dan
  membersihkan PII kandidat dengan jejak audit.
- Frontend: halaman "🧬 Talent Pool" (nav Recruitment) — unggah+consent, filter
  facet, badge "perlu cek", panel review, unduh versi PDF.
- Deps baru: `python-docx`. Tes: `backend/tests/test_talentpool.py`.

### Added — Fase 10 sisa AI: OCR Faktur, Rekonsiliasi Bank Cerdas, Prediksi Pembayaran

- **OCR faktur + auto-kategori (§8.8 #1)**: `POST /accounting/ai/ocr-bill` — foto
  faktur/nota (PNG/JPEG/WebP) diekstraksi satu panggilan model vision
  (`vision_completion` di `app/core/llm.py`) menjadi draft pembelian + saran COA
  dari riwayat tenant. Hasil berupa draft — bill tetap dibuat lewat endpoint
  pembelian agar jurnal terkontrol.
- **Rekonsiliasi bank cerdas (§8.8 #2)**: impor CSV rekening koran
  (`GET /cashbank/statement/template`, `POST /cashbank/statement/import`) dengan
  laporan baris gagal & duplikat; matching fuzzy deterministik ke transaksi kas-bank
  belum terekonsiliasi — skor = nominal 60% (toleransi ≤0,5%) + jarak tanggal ≤14 hari
  25% + kemiripan token deskripsi 15%, ambang usulan 75%. Konfirmasi usulan
  (`POST .../{id}/match`) menandai transaksi terekonsiliasi dan membersihkan usulan
  basi; baris tanpa pasangan diberi alasan yang bisa dibaca. Model baru
  `BankStatementLine` (migrasi `o5p6q7r8s9t0`).
- **Prediksi pembayaran klien (§8.8 #6)**: `GET /accounting/ai/payment-prediction` —
  skor risiko telat bayar per klien dari histori invoice (rasio keterlambatan +
  rata-rata hari telat + paparan overdue) → prioritas collection = outstanding × risiko.
- **Frontend**: tab baru "🤖 AI & Rekonsiliasi" pada halaman Akunting berisi Scan
  Faktur, Rekonsiliasi Bank Cerdas, dan tabel Prediksi Pembayaran Klien.
- Tes: `backend/tests/test_fase10_ai_sisa.py`.

### Added — Fase 9 penutup: Rantai Approval PR Multi-level per Tenant

- **Konfigurasi rantai** (`pr_approval_steps`, migrasi `n4o5p6q7r8s9`): urutan tahap
  approval per tenant — tiap tahap menunjuk satu user spesifik atau satu peran staf.
  `GET|PUT /payment-requests/approval-chain` (PUT khusus admin/management).
- **Eksekusi bertahap**: PR berjalan tahap demi tahap; hanya approver tahap berjalan
  yang dapat memutus (403 bila bukan); setujui tahap non-akhir melanjutkan ke approver
  berikutnya (notifikasi otomatis); tolak di tahap mana pun menggugurkan seluruh PR.
- **Jejak keputusan per tahap** (`pr_approvals`): step, approver, keputusan + catatan,
  waktu — tercatat juga di audit log. Progres `Tahap X/Y` tampil di daftar PR.
- **Kompatibilitas legacy**: tanpa konfigurasi rantai → perilaku lama (management/
  admin mana pun memutus). Kartu aksi chat PR ikut tunduk pada validasi rantai.
- Frontend: panel "Rantai Approval" di halaman Payment Request (tambah/hapus/simpan
  tahap), badge progres tahap per baris PR.
- Tes: rantai 2 tahap (peran → user), 403 approver salah tahap, penolakan per tahap,
  validasi config (422), reset ke legacy.

### Added — Saltab Export Excel/PDF + Pencarian & Mention Chat

- **Ekspor Saltab**: `GET /payroll/runs/{id}/saltab/export-excel` (openpyxl) dan
  `/export-pdf` (reportlab landscape A4); CSV tetap tersedia.
- **Pencarian pesan chat** + **autocomplete mention** ter-scope (karyawan hanya bisa
  menyebut sesama scope proyeknya).

### Added — Fase 11: Chat Workspace (gratis, WebSocket real-time — v1 REST polling)

- **Model chat** (`chat_channels`, `chat_channel_members`, `chat_messages`, `chat_message_reactions`, migrasi `l3m4n5o6p7q8`): Channel tipe `public/private/dm/broadcast`, pesan thread (`parent_id`), soft delete, reaksi emoji, anggota channel.
- **Akses ter-scope (PRD §9.2) dipaksakan server-side**: staff melihat semua channel tenant; karyawan outsourcing hanya channel yang dia member — penegakan di semua endpoint.
- **Broadcast channel** (📢 read-only untuk karyawan; hanya admin/Ops/management bisa posting).
- **Thread reply + reaksi**: kirim pesan ke channel/ke thread via `parent_id`; filter thread; toggle reaksi emoji; edit/hapus pesan milik sendiri.
- **Unread**: `unread_count` per channel untuk karyawan; `POST /channels/{id}/read-all`.
- **Channel gratis** (tanpa guard lisensi); rilis v1 memakai polling — WebSocket pluggable menyusul.
- **Halaman Chat** (`/chat`, nav 💬 Chat): layout dua panel (channel list + pesan), thread view Balas↩, polling 2.5–4 detik, reaksi per pesan, edit/hapus pesan milik sendiri.
- **Sisa Fase 11 lanjutan**: channel otomatis per job order / payroll periode / proyek penempatan; kartu notifikasi interaktif (PR & payroll) dengan tombol aksi dari chat; WebSocket real-time native FastAPI (bertahan sebagai fallback polling).
- Tes: channel CRUD, scope karyawan (403 → 200 setelah diinvite), broadcast hanya Ops/admin, thread + reaksi, unread count.

### Added — Fase 10: AI Layer Akuntansi (§8.8)

- **Asisten tutup buku** `GET /accounting/ai/close-checklist?year=&month=` — checklist deterministik tanpa LLM: jurnal memorial belum diposting, invoice/payrol/PR tanpa jurnal otomatis.
- **Deteksi anomali** `GET /accounting/ai/anomalies?year=&month=` — duplikasi bill vendor (nama+nominal dalam 7 hari), transaksi >3× median, sanity PPN (ppn ≠ rate×amount).
- **Kategori bill cerdas** `POST /accounting/ai/categorize-bill` — saran COA berdasarkan keyword + riwayat vendor serupa.
- **Narasi eksekutif** `GET /accounting/ai/executive-summary?year=[&month=]` — angka terverifikasi → narasi Bahasa Indonesia via LLM (fallback template bila AI tidak dikonfigurasi).
- **Tanya laporan** `POST /accounting/ai/ask` — pertanyaan natural → pre-computed data terverifikasi (laba rugi, neraca, per klien) → jawaban dirangkai LLM.
- Semua fitur AI berbasis data terstruktur yang bisa diverifikasi, bukan teks bebas; LLM opsional — checklist & anomali sepenuhnya deterministik.

### Added — Fase 10 lanjutan: Kas & Bank, Pembelian, Aset Tetap, Arus Kas Tidak Langsung

- **Kas & Bank** (`BankTransaction`, migrasi `k2l3m4n5o6p7`): penerimaan/pembayaran/transfer antar rekening dengan jurnal otomatis; rekonsiliasi manual per transaksi.
- **Pembelian** (`PurchaseBill`): bill vendor → Dr Beban/Aset + PPN Masukan / Cr Utang Usaha; pembayaran → Dr Utang / Cr Bank.
- **Aset tetap** (`FixedAsset`): perolehan (Dr Aset / Cr sumber dana), penyusutan garis lurus bulanan idempoten (Dr Beban Penyusutan / Cr Akum Penyusutan), disposisi dengan gain/loss otomatis.
- **Arus kas metode tidak langsung**: `GET /accounting/reports/cash-flow-indirect?year=` dari perubahan saldo grup akun — CFO/CFI/CFF terpisah.
- `ensure_coa` kini sync-upsert: menambah akun/rule template baru ke tenant lama tanpa duplikasi.
- Frontend Akunting: tab Kas & Bank / Pembelian / Aset Tetap + laporan arus kas tidak langsung.

### Added — Fase 10 (core): Accounting ala Accurate

- **Bagan akun dinamis per tenant** (`accounts`, migrasi `j1k2l3m4n5o6`): kode, kelompok 10 jenis ala Accurate, saldo normal, flag `is_cash_bank`/`is_control_ar_ap`; template default outsourcing di-seed otomatis; CRUD dengan guard "akun termutasi tidak boleh dihapus".
- **Jurnal memorial → posted**: `POST /accounting/journal?status=memorial` lalu `POST /accounting/journal/{id}/post` dengan validasi seimbang, periode open, akun aktif. Baris jurnal kini punya `account_id` FK, dimensi klien (`client_dim_id`), dan memo.
- **Periode & tutup buku**: `GET /accounting/periods`, `POST /periods/{y}/{m}/close|reopen` — input backdate ke periode tertutup ditolak; buka ulang tercatat di audit.
- **Mesin auto-journal idempoten** `post_auto_event()`: event unik per dokumen sumber (unique event+ref); rule aktif per tenant (`journal_rules`). Hook aktif: `invoice_issued`, `invoice_paid`, `payroll_finalized_internal/proyek`, `pr_executed`.
- **Laporan berbasis akun DB + hanya posted**: neraca saldo, buku besar, laba rugi (tahun/bulan), neraca; **laba rugi per klien** dari dimensi baris jurnal.
- **Frontend Akunting**: tab Jurnal (form memorial/posted, filter event, tombol Posting), Bagan Akun (+tambah akun), Periode & Tutup Buku (tutup/buka ulang).
- Sisa Fase 10 (irisan lanjut): kas-bank & rekonsiliasi, pembelian, aset tetap + penyusutan otomatis, arus kas tidak langsung, AI akuntansi.

### Added — Fase 9b-c: Saltab Line-item, BPJS Dua Sisi & Payment Request

- **Line-item Saltab** (`PayslipComponent`, migrasi `i0j1k2l3m4n5`): setiap slip kini punya rincian komponen (gaji pokok, tunjangan, lembur, PPh21, potongan lain, admin bank) yang dibangun otomatis saat generate — komponen ↔ agregat slip selalu "nol selisih".
- **Prorata absensi (opt-in)**: `prorata_absensi=true` pada `POST /payroll/runs/{id}/generate` memprorata gaji pokok & tunjangan dari hari hadir rekap tervalidasi ÷ hari kerja Sen–Jum bulan tsb (jejak di notes komponen).
- **BPJS dua sisi (opt-in)**: `bpjs_enabled=true` menambah potongan karyawan (Kesehatan/JHT/JP) + passthrough tanggungan perusahaan dari mesin BPJS ber-versi.
- **Grid Saltab**: `GET /payroll/runs/{id}/saltab` + override manual per komponen `PATCH /payroll/saltab/components/{id}` (gross/net recompute + audit) + ekspor CSV.
- **Invoice draft otomatis** saat payrol proyek disetujui klien (Σ earnings + BPJS employer; fee diatur Finance; idempoten per periode+klien).
- **Workflow Payment Request**: `PaymentRequest` dengan state machine diajukan → menunggu_atasan → disetujui → dieksekusi / ditolak (+catatan wajib); endpoint `/payment-requests` (create dari run final, list+filter, approve/reject management, execute finance); notifikasi approver & pemohon; nomor PR/ tahun berurutan.
- **Frontend**: grid Saltab editable inline di halaman Payroll; halaman "🧾 Payment Request" dengan aksi per status; tombol "+ Payment Request" pada run final.
- Tes: komponen/prorata/BPJS dua sisi, override + recompute, invoice otomatis, PR lifecycle lengkap.

### Added — Fase 9a: Payrol Dua Jalur + Approval Klien Ber-Token (ADR-0006)

- **`PayrollRun.run_type`** (`internal|proyek`) + `client_id` wajib untuk run proyek; duplikat diperiksa per (periode, jenis, klien). Migrasi `h9i0j1k2l3m4`.
- **State machine** sesuai PRD: proyek `draft → submitted_to_client → client_approved/rejected → finance_processing → final` (ditolak → perbaiki → kirim ulang); internal `draft → finance_processing → final` (finalisasi langsung dari draft tetap didukung).
- **Approval klien ber-token tanpa akun**: `POST /payroll/runs/{id}/submit-to-client` menghasilkan link `/payroll/client/{token}` (token disimpan sebagai hash SHA-256, masa berlaku 1–90 hari, link baru mencabut yang lama). Endpoint publik read-only `GET /payroll/client/{token}` + keputusan `POST .../decision` (nama & catatan wajib; kedaluwarsa 410; sudah diputus 409). Semua tercatat di audit + notifikasi HR.
- **Guard ADR-0006 dieksekusi**: shell `/payroll` jadi OR (`hr_payroll` ATAU `operations_billing`, role operations/management/hr), mutasi divalidasi lisensi per `run_type` di service.
- **Generate slip proyek** hanya menarik karyawan yang ditempatkan di klien run tersebut.
- **Frontend Payroll**: pilih jenis payrol + klien saat buat run; badge status 6 state; aksi kontekstual per status (Kirim ke Klien / Mulai Proses Finance / Finalisasi) + callout link approval dengan tombol salin URL.
- Tes: lifecycle internal & proyek lengkap, tolak→perbaiki→kirim ulang, token kedaluwarsa/terpakai, guard lisensi per jenis.

### Added — Rates ber-versi untuk pajak, BPJS, billing, bank fee (NFR §11)

- **Tabel rate ber-versi** (`pph21_configs`, `bpjs_configs`, `billing_tax_configs`, `bank_fee_configs`) dengan `effective_from` — tarif terpisah dari kode, versi dicatat per periode agar laporan historis konsisten. Migrasi `g1h2i3j4k5l6` (seed 2025-01-01 dari konstanta kode).
- **Payroll & BPJS memakai DB**: `TaxProfile.from_db(db, effective_date)` dan `compute_contribution(db, effective_date)` → fallback ke konstanta bila DB kosong; snapshot `pph21_snapshot`/`bpjs_snapshot` disimpan di `payroll_runs` saat generate.
- **Billing**: `generate_invoice` memakai `billing_tax_configs` efektif per periode (PPN/PPh23/due_days) dengan fallback `finance/tax_config.py`.
- **Bank fee**: `POST/GET /rates/bank-fees` — potongan admin otomatis di slip gaji (non-Mandiri, default Rp 3.500, configurable per bank). Endpoint `GET /rates/{pph21,bpjs,billing}` list, `POST` buat versi baru (admin/finance/management).
- **CRUD rates**: `GET /rates/{pph21,bpjs,billing,bank-fees}` + `POST` (admin) — versi untuk tanggal yang sama ditolak 409.
- **Halaman "🧮 Tarif & Rate"** (`/rates`, role admin/finance/management): tab PPh21/BPJS/Billing/Bank Fee, tabel riwayat versi + form buat versi baru (bracket JSON), edit fee bank inline.
- **ADR-0006** — guard lisensi payrol per `run_type`: shell `/payroll` menjadi OR (`hr_payroll` ATAU `operations_billing`), mutasi divalidasi per objek; BPJS recap tetap any-of.

### Added — Fase 8: Absensi Harian (Clock-in/out)

- **Model harian `AttendanceRecord`** (`date`, `clock_in`, `clock_out`, `overtime_hours`, `status`, `source`, `notes`) dengan unique `(employee_id, date)`; kolom `employees.employment_type` (`internal/eksternal`, default eksternal). Migrasi `b4d5e6f7a8b9`.
- **Guard multi-app**: absensi dilindungi `require_any_licensed_app("hr_payroll", "operations_billing")` — cukup salah satu aplikasi berlisensi.
- **Input manual + agregasi otomatis**: `POST /attendance/records` upsert satu hari langsung menghitung ulang `AttendanceSummary` bulanan; angka berubah me-reset approval (`client_approved`).
- **Impor CSV mesin fingerprint**: template `GET /attendance/template` (delimiter `;`), upload `POST /attendance/import` mengembalikan `{inserted, updated, failed[]}` dengan laporan baris gagal.
- **Validasi dua jalur**: `POST /attendance/summaries/{id}/validate?lane=hr|klien` — internal divalidasi HR, eksternal divalidasi Operations/klien; endpoint legacy `/payroll/attendance/.../client-approval` kini menolak karyawan internal (422).
- **Integrasi ESS**: cuti/izin yang disetujui di portal otomatis membuat record harian ber-status `cuti/izin/sakit` (source `ess`, tidak menimpa record manual/impor).
- **Halaman Absensi** (`/attendance`, nav "📅 Absensi"): periode picker, rekap bulanan + tombol Validasi HR / Approval Klien, form input manual, panel impor CSV dengan tabel baris gagal, daftar record harian.
- Tes: CRUD + agregasi, dua jalur, impor CSV dengan baris gagal, template, sinkron cuti ESS.

### Added — Fase 7: View Papan, Callout & Properti Notion (bagian 3 dari 3)

- **View papan/kanban Pipeline**: toggle "Tabel | Papan" di halaman Pipeline; kolom per tahapan dengan jumlah lead + total nilai potensi, kartu lead dengan tombol pindah tahap cepat (←/→) dan dropdown tahapan.
- **Primitif komponen ala Notion** (`src/components/notion.tsx`): `PageHeader` (emoji besar + judul), `CalloutBlock` (4 tone berwarna lembut), `PropertyRow`/`PropertiesPanel` (properti metadata dengan pemisah putus-putus).
- **Properti metadata pada halaman detail**: detail lead terpilih dan header karyawan terpilih kini memakai panel properti ala Notion; reminder kontrak berubah menjadi callout warning.
- Fase 7 selesai penuh (entitlement, guard, launcher, design system, kanban pipeline + kandidat, properti & emoji judul).

### Added — Fase 7: Design System Notion-style (bagian 2 dari 3)

- **Token desain**: font Inter, teks hangat `#37352F`, border/hover sangat halus, radius kecil, sidebar abu lembut (`#f7f6f3`) — semua via CSS variables di `index.css`.
- **Dark mode paralel** dengan toggle 🌙/☀️ di sidebar (tersimpan di localStorage); aturan retro-fit memetakan kelas slate-* lama agar seluruh halaman ikut gelap tanpa rewrite per file.
- **Shell baru**: sidebar workspace dengan grup per aplikasi berlisensi (aksen warna khas tiap app pada item aktif), topbar breadcrumb (Workspace / App / Halaman + emoji), tombol ⌘K.
- **Command palette ⌘K**: cari & lompat ke halaman/aplikasi apa pun, navigasi panah + Enter, termasuk aksi ganti tema.
- Irisan tersisa Fase 7 (polish): view papan (kanban pipeline), callout block, properti metadata ala Notion.

### Added — Fase 7: Entitlement Multi-App (bagian 1 dari 3)

- **App registry** (`app/core/apps.py`): 7 aplikasi portofolio (Sales CRM, Recruitment, HR & Payroll, Operations & Billing, Finance & Accounting, E-Sign, AI Add-on) dengan metadata, dependensi, dan pemetaan prefix route — single source of truth.
- **Lisensi per tenant**: tabel `tenant_app_licenses` (status `trial/aktif/kedaluwarsa`, trial 14 hari sekali per aplikasi). Migrasi `a1b2c3d4e5f6`; tenant lama di-seed paket penuh.
- **Guard backend 403**: endpoint aplikasi tanpa lisensi ditolak; dipasang via `include_router(dependencies=[...])`. Tenant provisioning baru kini mulai tanpa lisensi — admin mengaktifkan trial mandiri dari menu Aplikasi; tenant default/dev tetap full package.
- **API**: `GET /apps` (nav dinamis + launcher), `POST /apps/{key}/trial` (admin/management), `GET|PATCH /platform/tenants/{id}/licenses/{app_key}` (platform admin).
- **Frontend**: halaman "Aplikasi" (launcher + upsell trial 14 hari), nav sidebar dinamis mengikuti lisensi, editor lisensi per tenant di halaman platform.
- Tes: pemetaan registry, guard 403 + pemulihan, alur trial/provisioning/expiry.

> Irisan berikutnya Fase 7: design system Notion-style (shell baru, ⌘K, dark mode) — sesi terpisah.

### Added — Lampiran Surat Sakit, Koreksi Absensi, dan Email Notifikasi

- **Lampiran pengajuan cuti**: karyawan dapat mengunggah berkas pendukung (mis. surat dokter, maks. 10 MB) pada pengajuan berstatus menunggu via `POST /me/leave-requests/{id}/attachment`; unduh lewat `/me/.../attachment/download-url` (karyawan) atau `/employees/leave-requests/{id}/attachment/download-url` (HR). Migrasi `e8b4c7d1a952`.
- **Koreksi absensi oleh karyawan**: alur ajukan → approval HR. Karyawan mengusulkan angka hadir/lembur per periode (`POST /me/attendance-corrections`); saat disetujui angka diterapkan ke rekap absensi dan approval klien di-reset agar diverifikasi ulang. Duplikat pending per periode ditolak. Migrasi `f9c2e6b8d314`.
- **Email notifikasi (opsional)**: isi `SMTP_HOST` (+ port/user/password/from) untuk meneruskan notifikasi keputusan/pengajuan ke email penerima; dikirim fire-and-forget di thread terpisah, gagal SMTP tidak memengaruhi bisnis. Tanpa SMTP_HOST fitur nonaktif.
- UI: kartu "Koreksi Absensi" di Portal Saya; tabel "Koreksi Absensi (Portal)" di halaman Karyawan; tombol lampiran di kedua sisi.
- Tes: alur lampiran (upload/unduh/isolasi/kunci setelah diputus) dan koreksi absensi (approve menerapkan angka, reset approval klien, duplikat 409).

### Added — Notifikasi & Ekspor CSV

- Modul `notifications` (tabel `notifications`, migrasi `d6e3f2a8c471`) dengan endpoint `/me/notifications`: daftar, unread-count, tandai dibaca per item, dan read-all.
- Pengajuan cuti/izin kini menotifikasi semua akun admin & HR tenant; keputusan HR (setujui/tolak) menotifikasi karyawan pemohon lewat portal.
- Ekspor CSV untuk HR di `/employees/reports/*` (pola sama dengan ekspor BPJS, delimiter `;`):
  - `GET /employees/reports/leave?year=` — rekap pengajuan cuti satu tahun.
  - `GET /employees/reports/attendance?year=&month=` — rekap kehadiran/lembur.
- Tombol unduh CSV di kartu "Pengajuan Cuti / Izin" halaman Karyawan; kartu "Notifikasi" di Portal Saya.

### Added — Jatah Cuti Tahunan (kuota)

- Model `LeaveBalance` (per karyawan per tahun) + migrasi `c5d1f8a9b263`.
- HR: `POST|GET /employees/{id}/leave-balance` untuk mengatur/melihat jatah; UI form di halaman Karyawan.
- Approval cuti tahunan otomatis memotong kuota dan ditolak (422) bila sisa tidak cukup; izin/sakit/unpaid bebas kuota; tanpa baris balance, approval tidak dibatasi (opt-in HR).
- Portal: kartu "Sisa Cuti Tahunan" via `GET /me/leave-balance`.
- Tes: alur potong kuota, penolakan melebihi jatah, kenaikan jatah, proteksi jatah di bawah pemakaian.

### Added — Portal Self-Service Karyawan (v2)

- Modul backend `ess` dengan endpoint `/api/v1/me/*`:
  - `GET /me/profile` — data pribadi karyawan.
  - `GET /me/contracts`, `GET /me/contracts/{id}/download-url` — kontrak kerja.
  - `GET /me/documents`, `GET /me/documents/{id}/download-url` — dokumen HR.
  - `GET /me/payslips` — slip gaji dari payroll run final saja.
  - `GET /me/attendance` — rekap kehadiran bulanan sendiri.
  - `POST|GET /me/leave-requests`, `POST /me/leave-requests/{id}/cancel` — pengajuan cuti/izin beserta pembatalan saat masih menunggu.
- Endpoint HR di `/api/v1/employees/*`:
  - `PATCH /employees/{id}` kini menerima `user_id` untuk menaut/melepas akun login self-service (validasi role, tenant, dan kepemilikan).
  - `GET /employees/selfservice-accounts` — daftar akun role karyawan yang belum tertaut.
  - `GET /employees/leave-requests?status=` dan `PATCH /employees/leave-requests/{id}/decision` — approval cuti/izin.
- Halaman frontend **Portal Saya** (`/portal-saya`) untuk role `karyawan`: profil, kontrak, dokumen, slip gaji, rekap kehadiran, form cuti/izin, dan ganti password sendiri. Login role karyawan langsung diarahkan ke portal.
- Halaman **Karyawan**: kartu "Akun Portal Karyawan" (aktifkan/lepas tautan) dan tabel "Pengajuan Cuti / Izin" (setujui/tolak).
- Migrasi: `a7f2d94c1e58` (kolom `employees.user_id`), `b3c8e5a2f741` (tabel `leave_requests`).
- Tes: `backend/tests/test_ess.py` mencakup isolasi data antar karyawan, blokir platform_admin, alur cuti lengkap, dan tautan akun via HR.

### Security

- Semua endpoint `/me/*` hanya melayani data milik akun login (resolusi via `Employee.user_id`), tanpa parameter employee_id dari klien; akses lintas karyawan mengembalikan 404.
- Unduhan dokumen/kontrak lewat portal diverifikasi kepemilikannya dan tercatat sebagai event audit (`ess.*`).

## [0.2.0]

### Added

- Modul HRD, Payroll (+ mesin PPh21 TER/Pasal 17), BPJS, E-Sign, Akunting, Finance, Audit, AI (RAG kontrak & forecast).
- Multi-tenant shared-schema dengan RLS PostgreSQL dan middleware konteks tenant.
- Platform admin: provisioning tenant via `/platform/*`.
