# Plan Pengerjaan: Notion UI Parity

> Tujuan: menyamakan implementasi frontend (`frontend/`) dengan mockup desain
> [`mockup-notion-ui.html`](./mockup-notion-ui.html) dan PRD §Fase 7
> (`docs/02-product/PRD.md` baris 125–149).
>
> Prinsip urutan: **murah + dampak visual besar dulu**, paling berat (block editor) terakhir.
> Setiap fase diakhiri verifikasi visual manual vs mockup + `npm run build` tanpa error.

---

## Fase A — Chrome Shell & Layout (prioritas tertinggi) — ✅ Selesai (2026-08-26)

Estimasi: 1–2 hari. Dampak visual paling besar, tanpa dependency baru.

| # | Task | File | Status |
|---|------|------|--------|
| A1 | Konten center kolom baca `max-width: 900px` | `frontend/src/components/Layout.tsx` | ✅ Default centered; rute data/board via `WIDE_PREFIXES` opt-out full width |
| A2 | Topbar chrome ala Notion: tombol biru **Bagikan**, menu **•••**, ☆ favorit, "Diedit baru saja" | `Layout.tsx` | ✅ ☆ favorit per-route (localStorage), 💬→/chat, 🌙, ••• popover (favorit/salin tautan/tema), Bagikan=copy link. "Diedit baru saja" disembunyikan (belum ada sumber updated_at global) |
| A3 | Sidebar: 🔍 Pencarian (⌘K), 🔔 Kotak Masuk + badge, chip user avatar+role | `Layout.tsx` | ✅ Badge dari `GET /notifications/unread-count`; panel inbox 5 item + tandai dibaca; chip user avatar inisial + role |
| A4 | Kartu upsell di sidebar | `Layout.tsx` | ✅ Kondisional app belum terpasang (prioritas E-Sign → AI → pertama); tombol trial langsung aktif |
| A5 | App Launcher modal dari workspace switcher | `components/AppLauncherGrid.tsx` (baru), `Apps.tsx`, `Layout.tsx` | ✅ Grid diekstrak bersama; badge ✓ Terpasang / + Install; footer Full Package; workspace switcher membuka modal |

## Fase B — Design Token & Konsistensi Visual — ✅ Selesai (2026-08-26)

Estimasi: 1–2 hari. Tanpa fitur baru, murni parity tampilan.

| # | Task | File | Status |
|---|------|------|--------|
| B1 | Palet pill Notion persis hex mockup | `index.css` (`.pill .p-*`), `Leads.tsx`, `Candidates.tsx`, `JobOrders.tsx` | ✅ 7 warna Notion + `.p-indigo` lokal (#5B5BD6) untuk tahap Presentasi; dark: teks pill dicerahkan. Badge lain (PaymentRequests, Chat, dst.) menyusul bertahap |
| B2 | Skala judul H1 38px, emoji 56px, properti 168px | `components/notion.tsx` | ✅ PageHeader + PropertyRow mengikuti mockup L145–155; subtitle 15px |
| B3 | Aksen per-app via token shell | `Layout.tsx`, `index.css`, `notion.tsx`, `AppLauncherGrid.tsx` | ✅ Token `--accent`/`--accent-tint` di-set dari app halaman aktif; dipakai `.btn`, `.input:focus`, tombol Bagikan/upsell/install, callout info |
| B4 | Bersihkan retro-fit dark `!important` | `Dashboard.tsx`, `Leads.tsx` | 🟨 Mulai: Dashboard & Leads penuh token (tanpa slate legacy). Halaman lain bertahap — blok override global masih diperlukan |
| B5 | Dark token samakan mockup | `index.css` | ✅ bg #191919, elevated #1F1F1F, sidebar #202020, border/hover/text sesuai mockup, accent tetap #2383E2 |

## Fase C — Fungsionalitas Mockup — ✅ Selesai (2026-08-26)

Estimasi: 2–4 hari. Butuh koordinasi API ringan.

| # | Task | File | Status |
|---|------|------|--------|
| C1 | ⌘K cari entitas + quick actions | `CommandPalette.tsx`, `Layout.tsx` | ✅ Debounce 250 ms ke klien/kandidat/job order/halaman (maks 12 hit, grup berlabel); section "Aksi cepat": halaman baru, chat, absensi, PR, talent pool |
| C2 | View Kalender | `pages/Attendance.tsx` | ✅ Toggle ▤ Tabel / ◔ Kalender pada Absensi — grid bulanan Senin-based, titik warna per status + tooltip nama karyawan + legend. Payroll menyusul bila terpakia nyata |
| C3 | Kanban drag-and-drop | `pages/Leads.tsx` | ✅ HTML5 DnD native; optimis update cache lalu mutasi dengan rollback onError; highlight kolom tujuan; panah ←/→ tetap ada |
| C4 | FAB "✨ Tanya AEOS AI" + help chip | `Layout.tsx` | ✅ FAB accent app aktif → /chat (sembunyi di halaman Chat); help chip ⌘K/@AEOS dapat ditutup permanen (localStorage) |

## Fase D — Block Editor (paling berat)

Estimasi: 3–5 hari. Satu-satunya fase yang menambah dependency.

| # | Task | File | Catutan |
|---|------|------|---------|
| D1 | Pasang TipTap + Starter Kit; ganti `<textarea>` editor halaman | `pages/Pages.tsx:151-193`, `package.json` | Simpan HTML/JSON; migrasi konten string lama → paragraf otomatis. |
| D2 | Blok dasar: heading, bullet/numbered list, todo, quote, divider, callout (reuse `CalloutBlock` style) | komponen baru `components/editor/*` | Toolbar minimal + slash command `/`. |
| D3 | Render read-only blok untuk view halaman + emoji picker judul | `Pages.tsx` | Emoji picker sederhana (daftar statis cukup). |

---

## Definition of Done (parity checklist vs mockup)

- [x] Kolom konten center ≤900px; wide hanya untuk board/tabel lebar. *(Fase A)*
- [x] Topbar: breadcrumb · ☆ · 💬 · 🌙 · ••• · **Bagikan**. *(Fase A; "Diedit baru saja" disembunyikan sampai ada sumber updated_at)*
- [x] Sidebar: workspace switcher→modal launcher, 🔍 Pencarian, 🔔 Kotak Masuk+badge, grup aplikasi+page tree, upsell card, chip user. *(Fase A)*
- [x] Tabel/Papan/Kalender toggle aktif. *(Fase C2 — Absensi; halaman lain mengikuti pola yang sama)*
- [x] Pill 7 warna hex Notion (+1 indigo lokal); H1 38px + emoji 56px; properties 168px. *(Fase B; badge halaman lain menyusul)*
- [x] Aksen per-app menerus ke button/callout/active state. *(Fase B3 — token `--accent` shell)*
- [x] ⌘K mencari entitas lintas app + quick actions. *(Fase C1)*
- [x] Kanban drag-and-drop. *(Fase C3)*
- [ ] Editor blok (TipTap) menggantikan textarea. *(Fase D)*
- [ ] Tidak ada lagi override dark `!important`; semua warna via token. *(Fase B4)*
- [ ] `npm run build` + lint bersih; cek visual light & dark vs mockup.

## Out of scope (dulu)

- Komentar/discussion thread sungguhan (butuh API backend).
- Realtime multiplayer cursor.
- Mobile app (`mobile/`).
