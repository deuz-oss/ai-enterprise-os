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

Prinsip gabungan: **Rippling/Deel untuk kerapian & kepadatan data,
BambooHR untuk modul yang disentuh user awam, LinovHR sebagai lantai
minimum yang harus dilewati.**

## 3. Warna Aksen — STATUS: BELUM FINAL

Keputusan eksplisit: **tidak meniru satu referensi manapun secara
langsung** — referensi di atas dipakai sebagai bahan, bukan cetakan.

**Kandidat sejauh ini:** teal gelap `#0F6E56` (+ terang `#5DCAA5`).
Alasan dipilih sebagai kandidat:
- Tidak dipakai satupun dari 4 referensi di atas (Rippling/Deel≈hitam,
  BambooHR≈hijau, LinovHR≈biru) — beda sekilas dilihat berdampingan.
- Dibandingkan terhadap identitas SPC (parent company: biru cobalt
  `#1B6FC4` + merah crimson `#D32E36`, hue ≈210°) — teal di hue ≈165°,
  beda ±45°, cukup jauh untuk dibedakan tapi masih satu keluarga besar
  "dingin/profesional". Ini trade-off yang perlu diputuskan sadar: mau
  produk ini kerasa "evolusi dari SPC" (teal oke) atau "berdiri sendiri
  total" (perlu warna yang benar-benar berlawanan, mis. coral/oranye
  hangat — belum dieksplor lebih jauh).

**Belum diputuskan final** — jangan diasumsikan teal adalah keputusan
akhir di bagian kode manapun. Begitu final, update baris `--accent` di
`frontend/src/index.css` (satu baris) — seluruh component library
(§4) otomatis ikut berubah tanpa disentuh.

## 4. Component Library

Lokasi: `frontend/src/components/ui/`. Detail lengkap di `PRD.md`
Fase 22. Ringkasan:

| Komponen | Status | Sumber warna |
|---|---|---|
| `Button` | ✅ Ada (reuse `.btn`/`.btn-secondary`, + varian baru `ghost`/`danger`) | `var(--accent)` — ikut berubah kalau §3 final |
| `Badge` | ✅ Ada (reuse `.pill`/`.p-*`, API `tone` semantik) | **SENGAJA independen dari `--accent`** — warna status (sukses=hijau, dst.) universal, tidak boleh ikut goyah |
| `Card` | ✅ Ada (reuse `.card`) | Netral, tidak terpengaruh §3 |
| `ProgressStep` | ✅ Ada (baru, dipakai tracker `PlacementStatus` di PRD Fase 21) | `var(--accent)` — ikut berubah kalau §3 final |

**Aturan wajib** (selaras `AEP-014` §17): jangan bikin komponen baru
kalau yang sesuai sudah ada di tabel ini. Kalau butuh varian baru,
extend komponen existing, jangan duplikat.

## 5. Progress Migrasi Token

Dari 41 file frontend yang ditemukan bypass token saat audit awal:

| Halaman | Status |
|---|---|
| `Login.tsx` | ✅ Migrasi selesai (2026-09-03) |
| `ForgotPassword.tsx` | ✅ Migrasi selesai (2026-09-03) |
| `ResetPassword.tsx` | ✅ Migrasi selesai (2026-09-03) |
| 38 file lain | ⬜ Belum disentuh |

Migrasi dilakukan bertahap per halaman saat halaman itu disentuh untuk
alasan lain (bukan proyek migrasi besar sekaligus) — update tabel ini
setiap ada halaman baru yang dimigrasi.

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
