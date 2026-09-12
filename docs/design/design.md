# Design — Arah Visual & Component Library

> Menggantikan `notion-ui-parity-plan.md` (dihapus 2026-09-03) — dokumen
> itu men-track migrasi ke tema "Notion UI" yang sudah tidak relevan.
> Arah visual saat ini SaaS-admin bersih (lihat komentar di
> `frontend/src/index.css`), dan dokumen ini dibangun ulang dari nol
> untuk arah itu, bukan revisi dokumen lama.
>
> Status: **living document** — diupdate tiap ada keputusan desain baru,
> bukan ditulis sekali lalu dibiarkan usang seperti pendahulunya.

---

## 1. Konteks & Masalah yang Mau Diselesaikan

Audit 2026-09-03 menemukan: 32/41 file frontend bypass token `var(--...)`
dengan warna Tailwind mentah, tidak ada component library (`Button`/
`Card`/`Badge` tidak ada di `components/`), 3 halaman auth 100% tidak
merespons dark mode, dan border-radius/warna kategori tersebar tanpa
aturan jelas. Detail lengkap ada di riwayat audit — dokumen ini fokus ke
**arah ke depan**, bukan mengulang temuan.

Tujuan besar: Aeos naik kelas dari "terlihat internal tool" jadi
"terlihat produk SaaS komersial", karena rencana produk ini akan dijual
lintas industri (lihat `PRD.md` §1 arah v4.0), bukan cuma dipakai
internal SPC.

## 2. Referensi Benchmark

Diriset dan dibahas eksplisit (2026-09-03), masing-masing untuk konteks
berbeda — bukan satu app ditiru mentah-mentah:

| Referensi | Kekuatan diambil | Dipakai untuk |
|---|---|---|
| **Rippling** | Data-dense tapi lega: card border tipis (bukan shadow), tabel jadi "wajah produk", satu warna aksen dipakai pelit, tipografi kecil tapi weight jelas | Modul admin/ops-heavy: Finance, Payroll, Recruitment |
| **BambooHR** | "Lightness": whitespace lega, navigasi predictable, config kompleks dipecah jadi wizard step-by-step | Portal Karyawan (ESS) — audiens beda dari staf ops |
| **Deel** | Unifikasi kompleksitas ke satu dashboard, pre-flight check sebelum aksi besar (payroll run), compliance alert jadi elemen visual utama | Onboarding klien, dashboard lintas modul, payroll review |
| **LinovHR** | **Kompetitor langsung** (sama pasar Indonesia, sama regulasi) — jadi *benchmark minimum*, bukan tujuan akhir. Kekuatannya: multi-entity clarity, dashboard analitik. Secara visual sendiri sudah terasa agak dated dibanding standar SaaS 2026 | Sinyal "jangan sampai kalah dari ini" saat sales pitch |
| **Dashboard admin generik (2026-09-12)** | 10 preview dashboard (Real Estate, CRM, E-Commerce, HR, Finance, Healthcare, Marketing, Project Management, dll) dari satu desainer/design system yang sama — KPI card row dengan ikon lingkaran, donut chart center-label + legend, status pill semantik, tabel padat `tabular-nums`, sidebar ikon minimalis konsisten. Diambil sebagai **pola komponen lintas 10 vertikal industri**, BUKAN identitas visual/brand satu produk tertentu — beda karakter dari 4 referensi di atas yang masing-masing satu produk SaaS spesifik | Component Spec — Dashboard Pattern (§4a): `KpiCard`, `DonutChart`, `StatusPill`, `HeaderCanvas`, pola tabel, restyle sidebar |

Prinsip gabungan: **Rippling/Deel untuk kerapian & kepadatan data,
BambooHR untuk modul yang disentuh user awam, LinovHR sebagai lantai
minimum yang harus dilewati.**

## 3. Warna Aksen — STATUS: FINAL (2026-09-04)

**Teal gelap `#0F6E56`** (+ terang `#5DCAA5`, + varian aktif/gelap
`#0A4D3C`) — dikonfirmasi lewat 2 jalur independen: (1) hasil
eksplorasi Claude Design/Stitch kembali ke hex yang sama persis tanpa
diminta ulang, (2) dibandingkan terhadap identitas SPC (parent
company, biru `#1B6FC4`+merah `#D32E36`) — beda ±45° hue, cukup jauh
dibedakan tapi masih terasa "evolusi", bukan "berlawanan total" (lihat
riwayat keputusan di bawah untuk konteks lengkap trade-off ini).

**Palet lengkap (final):**
- Aksen: `#0F6E56` (primer), `#5DCAA5` (terang/hover), `#0A4D3C` (aktif/gelap)
- Latar: `#F8FAFC` (canvas), `#FFFFFF` (card/surface)
- Border: `#E2E8F0` (normal), `#F1F5F9` (subtle)
- Teks: `#0F172A` (utama), `#64748B` (muted), `#94A3B8` (subtle)
- Status semantik (independen dari aksen, TETAP dipakai di semua kondisi):
  Sukses `#10B981` (bg `#ECFDF5`, border `#A7F3D0`) · Warning `#F59E0B`
  (bg `#FFFBEB`, border `#FDE68A`) · Error `#EF4444` (bg `#FEF2F2`,
  border `#FECACA`) · Info `#3B82F6` (bg `#EFF6FF`, border `#BFDBFE`)

**Riwayat keputusan (untuk konteks, bukan status aktif):** sempat
dibandingkan dengan opsi coral/terracotta sebagai alternatif yang
lebih "berlawanan total" dari SPC — tidak dieksplor lebih lanjut
karena teal sudah dikonfirmasi lewat 2 tool desain independen.

## 3a. Tipografi & Skala (dikonfirmasi via Stitch, selaras Inter yang sudah dipakai Aeos)

- Font: Inter (sudah jadi default Aeos di `tailwind.config.ts`, tidak berubah)
- Skala: Judul halaman 20-24px/600 · Header section 16px/600 ·
  Table/label 11-13px/400-500 — skala kecil-tapi-tegas ini yang
  dimaksud "data-dense" di §2 (referensi Rippling)
- Angka finansial: tabular-nums, rata kanan di tabel (belum ada aturan
  eksplisit soal ini sebelumnya — sekarang wajib diterapkan di semua
  tabel yang menampilkan nominal Rupiah)

## 3b. Spacing & Tinggi Baris

- Skala spacing: 4/8/12/16/20/24px — jangan pakai angka di luar skala ini
- Tinggi baris tabel standar: 32-36px *(direvisi dari 36-40px semula,
  2026-09-05, setelah review implementasi nyata — lihat
  `component-implementation-spec.md` §1.6 untuk detail & alasan;
  prinsip dasarnya tetap sama: "tabel adalah wajah produk" dari
  Rippling, §2)*
- Radius: sm 4px (badge kecil), md 6px (input/button), lg 8px (card)
  — catatan: ini SEDIKIT beda dari radius yang sudah ada di
  `index.css`/Tailwind config Aeos sekarang (`rounded-lg`/`rounded-xl`
  campur di banyak halaman, temuan audit awal); saat migrasi token
  berlanjut (§5), pakai skala sm/md/lg ini sebagai acuan penyeragaman.

## 4. Component Library

Lokasi: `frontend/src/components/ui/`. Detail lengkap di `PRD.md`
Fase 22. Ringkasan:

| Komponen | Status | Sumber warna |
|---|---|---|
| `Button` | ✅ Ada (reuse `.btn`/`.btn-secondary`, + varian baru `ghost`/`danger`) | `var(--accent)` — ikut berubah kalau §3 final |
| `Badge` | ✅ Ada (reuse `.pill`/`.p-*`, API `tone` semantik) | **SENGAJA independen dari `--accent`** — warna status (sukses=hijau, dst.) universal, tidak boleh ikut goyah |
| `Card` | ✅ Ada (reuse `.card`) | Netral, tidak terpengaruh §3 |
| `ProgressStep` | ✅ Ada (baru, dipakai tracker `PlacementStatus` di PRD Fase 21) | `var(--accent)` — ikut berubah kalau §3 final |
| `KpiCard` | ✅ Ada, ditambah ikon lingkaran + delta indicator (2026-09-12, §4a) | Ikon: tone `Badge` (independen accent); delta: `text-emerald-700 dark:text-emerald-300` / `text-red-700 dark:text-red-300` |
| `StatusPill` | ✅ Ada (baru 2026-09-12, §4a) | Wrapper `Badge` — independen accent, sama seperti `Badge` |
| `HeaderCanvas` | ✅ Ada (baru 2026-09-12, §4a) | Netral + `var(--accent)` untuk teks aktif date-range picker |
| `DonutChart` | ✅ Ada (baru 2026-09-12, §4a) — library **recharts**, dipilih via skill `/pick-ui-library` (kategori "General charts") | Legend custom pakai `var(--cat-*)` sebagai fallback warna slice; center-label render manual (bukan fitur recharts) |

**Aturan wajib** (selaras `AEP-014` §17): jangan bikin komponen baru
kalau yang sesuai sudah ada di tabel ini. Kalau butuh varian baru,
extend komponen existing, jangan duplikat.

## 4a. Component Spec — Dashboard Pattern (2026-09-12)

Ditambahkan mengikuti 10 referensi preview dashboard admin generik
(Real Estate, CRM, E-Commerce, HR, Finance, Healthcare, Marketing,
Project Management, dll — satu desainer, satu design system yang
konsisten lintas 10 vertikal industri berbeda; dipakai sebagai
referensi **pola komponen**, BUKAN identitas visual/brand — lihat
entri baru di §2). Melanjutkan backlog audit UI/UX sebelumnya (quick
win #7 tinggi baris tabel, #6/#8 native select & dialog).

**KpiCard** (`components/ui/KpiCard.tsx`)
- Struktur: ikon (lingkaran, `rounded-full`, latar tinted dari tone `Badge`) →
  nilai (`tabular-nums`, bold, besar) → label (kecil, `var(--text-muted)`,
  uppercase) → delta indicator opsional (panah ↑/↓ + persen, warna semantik
  hijau/merah — lihat catatan §0 di bawah)
- **Delta TIDAK dipasang di manapun saat ini** — backend `/overview` (dan
  endpoint sejenis) belum menyediakan angka perbandingan periode
  sungguhan sama sekali. Prop `delta` disediakan di komponen supaya siap
  dipakai begitu backend punya datanya, TAPI belum ada satu pun pemanggil
  yang mengisinya — mengarang angka delta cuma supaya kartu "terlihat
  lengkap" melanggar §0 (data harus asli). Kalau ada entri lain yang
  bilang delta "aktif" di halaman tertentu tanpa dicek ke kode, itu keliru.
- Warna icon tone re-use `ICON_TONE_CLASS` (sama pemetaan dengan `Badge`)
  — SENGAJA independen dari `--accent` per prinsip §6.3 (bukan warna
  kategori sidebar, itu urusan `--cat-*` yang berbeda lagi).
- Dipakai di: Dashboard (4 kartu ringkasan lintas kategori) + 14 halaman
  lain yang sudah pakai versi sebelumnya (Employees, PaymentRequests,
  Agreements, Quotations, Leads, Clients, TalentPool, PlatformTenants,
  Payroll, JobOrders, Blacklist, Users, Finance, Referral) — perubahan
  ikon lingkaran otomatis berlaku di semua pemakaian existing ini karena
  cuma ubah komponen bersama, bukan API-nya (backward-compatible, prop
  baru semua opsional).

**DonutChart** (`components/ui/DonutChart.tsx`, baru)
- Struktur: total value di tengah lingkaran (center-label, `<div>` absolute
  overlay — recharts sendiri TIDAK punya fitur center-label bawaan) +
  legend list di samping (dot warna + label + `count · persen%`)
- Library: **recharts**, dipilih via skill `/pick-ui-library` (dijalankan
  manual oleh user setelah tool `Skill` Claude Code gagal dengan
  `disable-model-invocation` — skill ini sengaja di-gate slash-command
  saja). Kategori "General charts (static/interactive dashboards)", bukan
  Liveline (itu untuk data streaming real-time, bukan kasus di sini).
  Legend custom ditulis sendiri (bukan `<Legend>` bawaan recharts) supaya
  bisa konsisten pakai token `var(--...)` tema.
- Warna slice: fallback ke `--cat-crm`/`--cat-recruitment`/dst. berurutan
  kalau pemanggil tidak kirim warna eksplisit per slice — reuse token
  kategori yang sudah ada, tidak menambah palet warna baru.
- **Catatan instalasi:** `recharts` butuh `react-is` sebagai dependency
  transitif yang TIDAK ter-install otomatis oleh `npm install recharts`
  sendirian (ketahuan lewat error esbuild "`Could not resolve react-is`"
  saat Vite pre-bundle deps, dev server sempat crash sampai `react-is`
  di-`npm install` eksplisit). Kalau upgrade recharts di masa depan
  bikin dev server blank/500 lagi, cek dependency ini duluan.
- Dipakai di: Dashboard.tsx, section "Job Order & Kandidat" → "Status
  Kandidat" (dulu daftar pill datar tanpa proporsi visual, sekarang donut
  + legend persentase per status kandidat).

**StatusPill** (`components/ui/StatusPill.tsx`, baru)
- Struktur: pill penuh (reuse `.pill` lewat `Badge`), background tinted +
  teks warna solid — 3 tone inti hijau=sukses/selesai, kuning=proses,
  merah=gagal/ditolak, plus `neutral`/`info` untuk status transisi yang
  genuinely bukan salah satu dari 3 itu (lihat catatan cakupan di bawah)
- **Beda dari `Badge`:** `Badge` adalah primitif generik (`tone` manual per
  pemanggil); `StatusPill` tahu ARTI status per domain — pemanggil kirim
  string status mentah dari backend (`status="menunggu_atasan"`), bukan
  menghafal warnanya sendiri. Pemetaan status→tone per domain sekarang
  di SATU tempat (`StatusPill.tsx`), bukan diduplikasi tiap halaman.
- Domain yang sudah dimigrasikan (baca-saja, bukan `<select>` interaktif):
  `payment_request` (dulu `STATUS_BADGE` lokal di `PaymentRequests.tsx`),
  `invoice` (dulu `INVOICE_STATUS_PILL` lokal di `Dashboard.tsx`),
  `margin` (dulu threshold inline persen margin per klien di `Dashboard.tsx`),
  `employee` (dulu badge ad-hoc status aktif/resign di `Employees.tsx`)
- **SENGAJA TIDAK mencakup** (batasan cakupan, bukan celah yang terlewat):
  (1) `business_status` job order di `JobOrders.tsx` — itu `<select>`
  interaktif buat ganti status inline, memaksanya jadi StatusPill baca-saja
  akan menghapus kemampuan edit; (2) status pipeline `PlacementStatus`
  (9+ tahap: Sourcing→Screening→...→Onboarded) — sudah benar
  disentralisasi terpisah di `lib/pipelineStages.ts` dengan warna dot
  per-tahap sendiri-sendiri, memaksa 9+ tahap itu ke 3 tone StatusPill
  akan menghilangkan informasi tahap yang genuinely berbeda. Ad-hoc pill
  di ~16 file lain (`"pill p-*"` mentah untuk tag sumber lead, role user,
  dst — bukan "status" dalam makna badge selesai/proses/gagal) juga TIDAK
  disentuh, di luar cakupan permintaan ini.

**Pola Layout "Header Canvas"** (`components/ui/HeaderCanvas.tsx`, baru)
- Struktur: greeting kontekstual (berdasar jam lokal: Pagi <11:00, Siang
  <15:00, Sore <18:00, Malam sisanya) + nama user (dari `/auth/me`,
  opsional) + headline 1 kalimat (bold, besar) + subtext deskriptif
  (abu-abu, 1 baris) + date-range picker (kanan atas)
- **Date-range picker PRESENTASIONAL SAJA** — backend `/overview` (dan
  endpoint dashboard lain) belum menerima parameter rentang tanggal sama
  sekali, jadi memilih rentang di dropdown TIDAK memfilter data apa pun.
  Sama persis dengan tombol "Periode tampilan (segera dapat difilter)"
  yang sudah lebih dulu ada di topbar `Layout.tsx` — bukan pola baru,
  cuma versi lebih baik (dropdown asli, bukan tombol statis). Prop
  `onRangeChange` disediakan supaya gampang diwujudkan nyata begitu
  backend terkait mendukung filter tanggal.
- Status penerapan: **Dashboard.tsx saja.** Job Orders/Employees/Payroll
  BELUM menerapkan pola ini — waktu di sesi ini tidak cukup untuk
  menjangkau ketiganya setelah scope Bagian 1 lain (KpiCard, StatusPill,
  restyle tabel, sidebar) selesai. Menggantikan `PageHeader` lama di
  `components/workspace.tsx` HANYA di Dashboard; `PageHeader` sendiri
  TIDAK dihapus, masih dipakai halaman lain yang belum disentuh pola ini.

**Pola Tabel Data**
- Struktur baris: avatar/ikon (lingkaran, inisial) + nama (kolom pertama)
  → data lain → StatusPill (kolom terakhir)
- Sel numerik: `tabular-nums` (Tailwind utility, setara `font-variant-
  numeric: tabular-nums`), rata kanan
- Tinggi baris target: **32-36px**, konsisten dengan standar yang sudah
  final di §3b/`component-implementation-spec.md` §1.6 (bukan angka
  baru — kalimat awal yang menulis "32-40px" di sini keliru mengutip
  instruksi mentah tanpa cek standar existing, dikoreksi) — dicek lewat
  `getBoundingClientRect()` di browser sungguhan, bukan cuma baca CSS
- Status penerapan: **`Employees.tsx`** (tabel utama daftar karyawan) —
  avatar inisial + `StatusPill` domain `employee` + padding diketatkan
  dari `py-2.5` (default `.td` shared, ~40-44px dengan avatar) ke
  `py-1.5` lokal supaya avatar 20px tetap pas di tinggi baris target;
  diverifikasi 34.67px lewat `getBoundingClientRect()` langsung di
  browser. **`Dashboard.tsx`** tabel invoice — `tabular-nums` + `StatusPill`
  diterapkan, avatar TIDAK relevan (baris invoice, bukan baris orang).
  Tabel lain di app (~18+ tabel data lain, termasuk 2 tabel lain di
  `Employees.tsx` sendiri: koreksi absensi & yang belum disebut) BELUM
  disentuh — restyle di sesi ini dibatasi ke 2 tabel di atas sebagai
  implementasi representatif, bukan sapuan menyeluruh semua tabel app.

**Sidebar — Icon & Warna (restyle, bukan restrukturisasi)**
- Icon set: **lucide-react** (satu library, sudah dipakai eksklusif sejak
  sebelumnya — dikonfirmasi tidak ada icon set lain tercampur; semua
  ikon outline-style konsisten by design karena itu satu-satunya gaya
  yang diekspor lucide-react)
- Warna label + ikon aktif: **direstyle** dari fill solid `var(--accent)`
  + teks `var(--accent-contrast)` (sebelumnya) menjadi tint lembut
  `var(--accent-tint)` sebagai background + `var(--accent)` sebagai
  warna teks — selaras prinsip "aksen dipakai pelit" (§2, referensi
  Rippling) yang sebelumnya cuma diterapkan ke elemen lain, belum ke nav
  aktif sendiri. Warna kategori ikon (`--cat-crm`/dst.) sekarang TETAP
  tampil sekalipun item lagi aktif (sebelumnya disembunyikan jadi netral
  saat aktif) — tint background sudah cukup menandai "ini halaman aktif"
  tanpa perlu menyembunyikan warna kategorinya.
- Warna label non-aktif: `var(--text-muted)` (tidak berubah dari sebelumnya)
- Kontras diverifikasi manual (rumus luminance relatif WCAG) DAN lewat
  `getComputedStyle` di browser sungguhan, kedua tema: teks aktif
  `var(--accent)` di atas `var(--accent-tint)` — light ≈5.6:1, dark
  ≈6.5:1 (keduanya lolos AA 4.5:1); ikon kategori (mis. violet CRM
  `#c4b5fd` dark) di atas tint yang sama ≈7.1:1 (lolos AA non-teks 3:1)
- **CATATAN EKSPLISIT: struktur navigasi, kategori, dan urutan menu TIDAK
  berubah** — `NAV_ITEMS`, `CATEGORY_ORDER`, dan routing di `Layout.tsx`
  sama persis seperti sebelumnya. Perubahan ini murni visual/styling
  (background + warna teks nav link), tidak menyentuh array/struktur data
  navigasi sama sekali.

## 5. Progress Migrasi Token

Dari 41 file frontend yang ditemukan bypass token saat audit awal.
**Diperbarui 2026-09-12** setelah audit UI/UX menyeluruh (screenshot +
DOM audit live, bukan cuma baca kode) — tabel "38 file belum disentuh"
sebelumnya menyesatkan: sebagian besar file itu sebenarnya sudah aman
(dark mode benar-benar berfungsi saat diuji live), sisanya masuk salah
satu dari 3 kategori di bawah, bukan satu tumpukan "belum dikerjakan".

| Halaman | Status |
|---|---|
| `Login.tsx` | ✅ Migrasi selesai (2026-09-03) |
| `ForgotPassword.tsx` | ✅ Migrasi selesai (2026-09-03) |
| `ResetPassword.tsx` | ✅ Migrasi selesai (2026-09-03) |
| `JobOrderDetail.tsx`, `TalentPool.tsx`, `TalentPoolDetail.tsx` | ✅ Warna+label tahap `PlacementStatus` (dulu di-hardcode 3× identik) disatukan ke `frontend/src/lib/pipelineStages.ts` (2026-09-12) |
| Sisa file dengan warna Tailwind kategori (biru/violet/emerald/amber) | ✅ Bukan bug — ini warna kategori sidebar yang SENGAJA independen dari `--accent` (lihat komentar `index.css` §"Warna kategori") |
| `components/ui/PreflightAlert.tsx`, banner urgensi `Dashboard.tsx` | ✅ Bukan bug — warna dipatok persis dari `component-implementation-spec.md` §1.4, SENGAJA sama di light & dark mode (alert compliance/urgensi tinggi, bukan elemen tema) |
| `Pages.tsx`, `Payroll.tsx`, `MyPortal.tsx`, `Billing.tsx` | ✅ Sisa hex kecil (teks "Tersimpan", warning net-pay negatif, checkmark, kredit transaksi) diganti ke utility Tailwind semantik (`text-emerald-600/700`, `text-amber-700`) yang sudah jadi konvensi di file lain — bukan token `var(--...)` (memang bukan warna brand), tapi tidak lagi hex lepas (2026-09-12) |

Migrasi dilakukan bertahap per halaman saat halaman itu disentuh untuk
alasan lain (bukan proyek migrasi besar sekaligus) — update tabel ini
setiap ada halaman baru yang dimigrasi.

## 5a. Progress Komponen Pola Dashboard (2026-09-12)

Status **aktual** per akhir sesi implementasi ini (disiplin sama seperti
koreksi §5 di atas: laporkan apa yang benar-benar jalan, bukan rencana):

| Item | Status |
|---|---|
| `KpiCard` — ikon lingkaran + prop `delta` | ✅ Komponen selesai, berlaku otomatis di 15 halaman existing yang sudah pakai (lihat §4a). Prop `delta` TIDAK dipasang di mana pun (belum ada sumber data delta asli). |
| `StatusPill` (baru) | ✅ Komponen selesai. Migrasi baca-saja: `payment_request`, `invoice`, `margin`, `employee` (4 domain, 4 file). Job Order status (select interaktif) dan Placement pipeline (sistem dot multi-tahap) sengaja tidak dimigrasikan — lihat §4a. |
| `HeaderCanvas` (baru) | ✅ Komponen selesai. Diterapkan: **Dashboard.tsx**. Belum diterapkan: Job Orders, Employees, Payroll (waktu tidak cukup di sesi ini). |
| `DonutChart` (baru) | ✅ Selesai — library recharts (dipilih via `/pick-ui-library` yang dijalankan user). Diterapkan di Dashboard.tsx "Status Kandidat". Diverifikasi live light & dark mode. |
| Restyle tabel (avatar+nama, `tabular-nums`, `StatusPill`, tinggi baris 32-36px) | ✅ **`Employees.tsx`** tabel utama (34.67px diverifikasi live) dan **`Dashboard.tsx`** tabel invoice (parsial — tanpa avatar, tidak relevan untuk baris invoice). Tabel lain di app (~18+) belum disentuh. |
| Sidebar — restyle ikon & warna | ✅ Ikon: konfirmasi sudah 100% lucide-react konsisten (tidak ada perubahan library, sudah benar sebelumnya). Warna nav aktif: fill solid → tint lembut + teks `var(--accent)`, ikon kategori tetap tampil saat aktif. Struktur/urutan menu tidak berubah (diverifikasi baca kode `NAV_ITEMS`/`CATEGORY_ORDER` tidak tersentuh). |

**Verifikasi yang sudah dilakukan** (bukan cuma baca kode): `npx tsc
--noEmit` bersih di setiap tahap; live browser check Dashboard, Employees,
Leads, PaymentRequests di light DAN dark mode (termasuk DonutChart);
kontras warna aktif sidebar dihitung manual (rumus luminance WCAG) lalu
dicocokkan ke `getComputedStyle` sungguhan; tinggi baris tabel diukur
via `getBoundingClientRect()`, bukan diasumsikan dari CSS. Instalasi
`recharts` sempat bikin dev server blank/crash (dependency `react-is`
hilang, lihat catatan di §4a) — ketahuan & diperbaiki lewat pengecekan
network request + log dev server, bukan diasumsikan "pasti kepasang
otomatis".

**Yang masih terbuka untuk sesi lanjutan:** HeaderCanvas di 3 halaman
lain (Job Orders, Employees, Payroll), restyle tabel di halaman selain
Employees/Dashboard, dan migrasi StatusPill ke domain lain kalau
ditemukan status baca-saja lain yang genuinely 3-5 state datar (bukan
select interaktif atau sistem multi-tahap). DonutChart sudah selesai
(lihat baris di atas) — satu-satunya item Bagian 1 yang sempat blocked
di sesi ini, sekarang tuntas setelah user menjalankan `/pick-ui-library`.

Semua item di atas + fix kontras §5b di bawah digabung jadi satu commit
(`4334225`) karena keduanya menumpuk file yang sama sebelum sempat
di-commit terpisah — lihat PRD.md Fase 39 untuk ringkasan produk.
Belum di-push ke remote.

## 5b. Fix Kontras Warna Semantik Hardcoded (2026-09-12)

Gap yang ditemukan lewat siklus "cek all gap" (ronde ke-3, lihat riwayat
audit UI/UX — PRD.md Fase 38) sempat dicatat tapi sengaja tidak
diperbaiki saat itu ("catat saja" — scope-nya jauh lebih besar dari
ronde sebelumnya). Diperbaiki di sesi berikutnya setelah user konfirmasi
lanjut ("ya").

**Masalah**: `text-red-600`, `text-rose-600`, `text-emerald-700`,
`text-amber-600` (dan varian 500/700 lain yang ditemukan sepanjang
pengerjaan) dipakai sebagai warna teks BACA-SAJA (bukan di dalam
badge/pill) di puluhan file — masing-masing warna dikalibrasi untuk
dipasangkan dengan latar tinted yang cocok (mis. `bg-amber-50
text-amber-600`), bukan untuk duduk langsung di atas `--bg`/
`--bg-elevated`/`--hover` netral. Akibatnya tiap warna gagal WCAG AA
di SATU tema (dihitung exact via rumus luminance WCAG, bukan tebakan):
`red-600`/`rose-600` gagal spesifik di atas `--hover` meski lolos putih
polos; `emerald-600`/`amber-600` gagal light mode SAMA SEKALI (bukan
kasus sempit).

**Fix**: `red-600`/`red-700`/`rose-600`/`rose-700` → tambah
`dark:text-{hue}-400` (base classnya sendiri tetap, sudah aman di
light mode/`--bg-elevated`); `emerald-600` → base **dinaikkan** ke
`emerald-700 dark:text-emerald-400`; `amber-600` → base **dinaikkan**
ke `amber-700 dark:text-amber-400` (2 yang terakhir HARUS naik base,
bukan cuma tambah `dark:`, karena gagal light mode outright).

**Skala**: ~140 titik di 33 file. Dikerjakan via subagent fork
(mekanis, sudah dispesifikasi presis) untuk menjaga context utama
tetap ringkas, lalu diverifikasi independen: `tsc` ulang, diff manual
4 file paling rumit, cek live `getComputedStyle` di app sungguhan
kedua tema.

**SENGAJA TIDAK disentuh** (pola beda, bukan bug kontras ini):
`CalloutBlock`/`CALLOUT_TONES` di `components/workspace.tsx` — teks
pesan aslinya sudah pakai `style={{color: "var(--text)"}}`, cuma ikon
yang inherit warna tone, dan ikon cuma butuh kontras non-teks 3:1 yang
tetap lolos. Juga badge `bg-{hue}-50/100` + teks `{hue}-600/700` yang
match (`AccountingAi.tsx` status badge, `TalentPoolPanels.tsx:255`,
`Finance.tsx` kotak risiko/rekomendasi/aging) — itu masalah "belum
pernah dimigrasi dark mode sama sekali" (kedua sisi statis, tidak ada
`dark:` di manapun), beda kategori dari kontras-teks-di-atas-latar-netral
yang diperbaiki di sini. Dicatat sebagai gap terbuka berikutnya.

## 6. Prinsip Kerja Ke Depan

1. **Token dulu, styling manual belakangan.** Warna, radius, spacing
   baru selalu lewat `var(--...)` atau komponen `ui/`, tidak pernah hex
   langsung di halaman.
2. **Satu keputusan warna, satu tempat.** `--accent` di `index.css`
   adalah satu-satunya sumber kebenaran warna brand.
3. **Warna makna ≠ warna brand.** Status (sukses/gagal/warning) pakai
   token semantik tetap, tidak pernah ikut ganti kalau `--accent` ganti.
4. **Radius & spacing ikut skala yang sudah ada** — jangan angka baru
   yang belum ada di `index.css`/Tailwind config tanpa alasan
   terdokumentasi di sini.
5. **Dokumen ini diupdate, bukan dibiarkan usang.** Kalau arah desain
   berubah drastis (seperti kasus `notion-ui-parity-plan.md`), tulis
   ulang bagian yang relevan di sini — jangan biarkan jadi jejak sejarah
   yang menyesatkan developer berikutnya.

## 7. Perubahan Model Komersial (2026-09-04) — Dampak ke Frontend

**Keputusan bisnis (detail penuh menyusul di PRD, dicatat di sini
karena efeknya langsung ke cara UI dibangun):** Opsi F (bundle
per-Cloud yang harus "diaktifkan" satu-satu sebelum bisa dipakai)
digantikan model baru — **semua fitur di semua Cloud terbuka penuh**
untuk tenant `commercial`, dimonetisasi lewat **saldo credit** yang
diisi dari subscription bulanan (3 tier: Rp500rb/2jt/5jt) + top-up
manual kalau habis.

### Yang HILANG dari checklist frontend (jangan dibangun lagi)

Sebelumnya, hampir tiap halaman/komponen perlu mikirin: *"apakah Cloud
ini dilisensikan buat tenant ini?"* — locked-state overlay, blur,
redirect ke halaman upgrade, dst. **Ini SUDAH TIDAK RELEVAN.** Kalau
ada kode/desain lama yang masih melakukan pengecekan lisensi per-Cloud
di level UI, itu perlu dihapus, bukan dipertahankan "siapa tahu
kepakai lagi."

### Yang TETAP ada — dan yang BARU

Cuma 2 kategori state yang masih perlu ditangani di UI, dan
keduanya BEDA KARAKTER, jangan dicampur jadi satu komponen:

**A. Permission-denied (RBAC — tidak berubah dari sebelumnya)**
Ini soal *siapa boleh lihat apa di dalam tenant yang sama* — sama
sekali tidak berkaitan dengan billing/saldo. Contoh: Ops coba buka
data karyawan internal. Harus tampil pesan eksplisit ("Anda tidak
punya akses ke data ini"), bukan halaman kosong.

**B. Indikator saldo credit (BARU — wajib ada, bukan opsional)**
Karena semua fitur metered dan saldo bisa habis, UI WAJIB kasih tau
posisi saldo — bukan cuma nolak transaksi pas udah kepotong nanti.
Dua level:
- **Indikator ringkas** di header/topbar — selalu terlihat, 3 state:
  Normal (teal, >20% tersisa) → Peringatan (amber, ≤20%) → Habis
  (merah, auto-reload aktif atau minta top-up manual).
- **Halaman detail billing** — breakdown pemakaian, riwayat transaksi,
  tombol top-up manual.

Pengecualian: **Govern Cloud (Akunting)** — akses dasarnya bisa
"gratis" (termasuk di Tier 2/3, atau bayar Rp300rb/user di Tier 1),
TAPI fitur AI di dalamnya (OCR, rekonsiliasi, dst.) tetap motong
saldo credit yang sama. Jangan bikin state "gratis" yang mengira
seluruh modul termasuk AI-nya bebas biaya — cuma akses dasarnya yang
gratis.

**Kesimpulan buat siapa pun yang develop frontend ke depan:** logic
"apakah fitur ini boleh diakses" sekarang jauh lebih sederhana —
satu-satunya gate adalah RBAC (permission), bukan licensing per-Cloud.
Yang perlu effort desain justru pindah ke **visibilitas saldo**
(state B) supaya user tidak kaget di-charge.

### Struktur Sidebar Final — Hilangkan Branding "Cloud" (2026-09-04)

Nama "Talent Cloud", "Workforce Cloud", "Revenue Cloud", "Govern
Cloud" **dihapus dari tampilan** — diganti 5 kategori berdasarkan
fungsi nyata (nama modul kode `apps.py` TIDAK berubah, ini murni
label & pengelompokan UI):

- **CRM** — Pipeline, Klien, Quotation, Agreement, Lead Sourcing
- **Recruitment** — Job Orders (termasuk tab "Candidates" per-JO,
  Kanban — Talent Pool adalah satu-satunya database kandidat, "Kandidat"
  BUKAN item sidebar terpisah, koreksi 2026-09-05), Talent Pool, AI Interview,
  Black Lists, **Referral** (ditambahkan 2026-09-05 — program referral
  karyawan→kandidat, penempatan dikonfirmasi masuk akal di sini)
- **Workforce** — Karyawan, kontrak, BPJS+asuransi, Absensi, ESS,
  TTE, **Payroll** (Saltab, PPh21 — sengaja di sini, bukan di Finance,
  karena ini soal karyawan)
- **Finance & Accounting** — Invoice, e-Faktur, Kas-Bank, Pembelian,
  Aset Tetap, Payment Request, Tutup Buku, Jurnal, Laporan,
  Tanya-Laporan AI (gabungan bekas Revenue Cloud + seluruh Govern Cloud)
- **Administration** — Settings, **Rate Configuration** (rename dari
  "Tarif & Rate": tarif PPh21/BPJS/bank yang dipakai Payroll)

Asumsi kerja (koreksi bila salah): Chat tetap top-level di luar 5
kategori ini; dashboard/pengaturan saldo credit masuk Administration.

Detail lengkap model komersial di baliknya (tier, model data,
payment gateway) ada di PRD §4.4 (Opsi G) — tidak diulang di sini,
dokumen ini fokus ke implikasi visual/struktural saja.
