# ADR-0006 Guard Lisensi Payrol per Jenis Payrol (run_type)

- Status: **Superseded by ADR-0007** (2026-09-04) — lihat catatan di bawah
- Date: 2026-08-25
- Deciders: Brian (Product), Platform Engineering

> **Catatan supersedensi (2026-09-04):** keputusan bisnis Opsi G (PRD
> §4.4) menghapus model lisensi per-SKU secara keseluruhan, sehingga
> guard `assert_run_license` yang dirancang ADR ini tidak lagi
> berlaku. Isi ADR ini TIDAK diedit/dihapus — dipertahankan utuh
> sebagai catatan sejarah keputusan pada masanya. Lihat **ADR-0007**
> untuk keputusan pengganti.

## Context

Fase 7 memetakan guard lisensi di level **prefix router**: seluruh `/payroll`
dan `/bpjs` dilindungi lisensi aplikasi `hr_payroll`. PRD Fase 9 memecah payrol
menjadi dua jalur dengan pasar lisensi berbeda:

- **Payrol internal** → bagian aplikasi 💼 HR & Payroll (divalidasi HR).
- **Payrol proyek** → bagian aplikasi 🏗️ Operations & Billing (approval klien,
  masuk Saltab/invoice).

Konsekuensinya, guard prefix tunggal tidak lagi akurat:

1. Tenant yang hanya berlangganan *Operations & Billing* tetap harus bisa
   menjalankan payrol proyek — tetapi saat ini terblokir 403 karena
   `/payroll` menuntut `hr_payroll`.
2. Sebaliknya, tenant hanya berlangganan *HR & Payroll* tidak seharusnya
   mendapat fitur billing proyek secara gratis.
3. Kedua jalur memakai tabel dan mesin perhitungan yang sama
   (`PayrollRun`, `Payslip`, mesin PPh21/BPJS) — memecah router menjadi
   `/payroll/internal/*` vs `/payroll/projects/*` akan menduplikasi kode dan
   merusak frontend yang sudah stabil.

## Decision

1. **Prefix router tetap satu** (`/payroll`, `/bpjs`) — tidak ada pemecahan route.
2. **Guard shell menjadi OR**: `require_any_licensed_app("hr_payroll",
   "operations_billing")` — cukup salah satu lisensi untuk membuka modul.
3. **Guard data-driven per objek**: setiap operasi yang membuat/mengubah
   `PayrollRun` wajib memvalidasi `run_type` terhadap lisensi tenant melalui
   helper service `assert_run_license(db, tenant_id, run)`:
   - `run_type = internal` → wajib lisensi `hr_payroll`;
   - `run_type = proyek` → wajib lisensi `operations_billing`.
4. **BPJS recap tetap any-of** — iuran BPJS adalah infrastruktur bersama yang
   menjadi masukan slip gaji kedua jalur maupun invoice; ia bukan produk jualan
   terpisah.
5. **Grandfathering**: kolom `PayrollRun.run_type` (Fase 9 irisan a) default
   `internal`; run lama tidak dimigrasi paksa.

## Implementation Notes

- Helper diletakkan di modul `platform.service` (sudah memilikinya
  `is_licensed`) agar tidak ada dependensi siklik dengan modul payroll.
- Endpoint `POST /payroll/runs`, `POST /payroll/runs/{id}/generate`, dan
  `POST /payroll/runs/{id}/finalize` adalah titik pemeriksaan wajib;
  endpoint read-only mengikuti guard shell OR.
- Frontend sudah siap: pola nav any-of (`apps: [...]`) dipakai menu Absensi;
  menu Payroll nanti cukup diganti ke `apps: ["hr_payroll",
  "operations_billing"]`.

## Consequences

- ✅ Packaging fleksibel tanpa duplikasi route/kode; frontend tidak berubah besar.
- ✅ Aturan lisensi teruji lewat unit test yang sama dengan guard Fase 7.
- ⚠️ Satu query lisensi tambahan per operasi mutasi payrol (diterima; murah dan
  ter-cache oleh session).
- ⚠️ Error 403 kini bisa muncul di level objek (bukan prefix) — pesan error
  wajib menyebut aplikasi mana yang belum berlisensi agar tidak membingungkan.

## Related

- PRD §4 (Portofolio & Packaging), §5 Fase 9, §11 (Keamanan: RBAC per jenis payrol)
- ADR-0002 Service Boundaries · TRACEABILITY-MATRIX §12.6
