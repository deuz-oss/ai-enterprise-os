"""Regression guard untuk kelas bug yang SUDAH DUA KALI terjadi nyata di
kolom yang berbeda -- ditulis persis dengan urutan kejadiannya supaya
pelajarannya tidak hilang:

1. `JobOrderBusinessStatus` (nama anggota `open` -> nilai `"dibuka"` dst.)
   sempat tertukar karena `create_job_order()`/`update_job_order()`
   memakai `payload.model_dump()` yang membuka-bungkus enum jadi NILAI
   string mentah sebelum disimpan — tanpa `values_callable`, ini
   menyebabkan `GET /job-orders` crash 500 untuk SEMUA baris. Diperbaiki
   dengan menambah `values_callable` ke kolom itu.

2. Sesi ini (2026-09-02) sempat mengulang "perbaikan" yang SAMA ke kolom
   `JobOrder.status` (`JobOrderStatus.interview` = `"interview_klien"`,
   nama != nilai juga, pola kelihatan identik) — TERNYATA SALAH ARAH:
   baris `JobOrder` yang sudah ada di Postgres tersimpan berbasis NAMA
   ("interview", bukan "interview_klien"). Menambah `values_callable`
   membuat baris LAMA itu gagal dibaca (`LookupError`), ketahuan lewat
   verifikasi Docker+Postgres nyata SEBELUM sempat commit, lalu di-revert.
   Pelajarannya: dua kolom bisa terlihat identik strukturnya
   (native_enum=False, nama != nilai di salah satu anggota) tapi beda
   status keamanannya tergantung APA yang SUDAH tersimpan di data
   nyata -- tidak cukup dilihat dari definisi enum-nya saja.

Test ini mengunci PERILAKU SAAT INI untuk kedua kolom (business_status
DENGAN values_callable, status TANPA) lewat API sungguhan, supaya
perubahan berikutnya ke salah satunya (values_callable ditambah/dicabut)
ketahuan di sini dulu, bukan di Postgres produksi."""

from tests.conftest import _auth_header
from tests.test_recruitment import _client_id, _create_jo


def test_job_order_status_semua_nilai_roundtrip(client):
    """`JobOrderStatus.interview` bernilai `"interview_klien"` (beda dari
    nama anggotanya) -- kandidat paling mungkin kena bug kelas
    business_status kalau `values_callable`-nya tidak ada/berubah."""
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)

    for value in ["open", "screening", "interview_klien", "offering", "filled", "closed"]:
        patch = client.patch(
            f"/api/v1/recruitment/job-orders/{jo_id}",
            headers=headers,
            json={"status": value},
        )
        assert patch.status_code == 200, f"PATCH status={value}: {patch.text}"
        assert patch.json()["status"] == value

        listing = client.get("/api/v1/recruitment/job-orders", headers=headers)
        assert listing.status_code == 200, f"GET setelah status={value}: {listing.text}"
        row = next(jo for jo in listing.json() if jo["id"] == jo_id)
        assert row["status"] == value


def test_job_order_business_status_semua_nilai_roundtrip(client):
    """business_status (`values_callable` sudah dipasang sejak bug ini
    pertama ditemukan) -- dikunci di sini supaya fix-nya tidak pernah
    ke-revert tanpa ketahuan."""
    headers = _auth_header(client)
    cid = _client_id(client, headers)
    jo_id = _create_jo(client, headers, cid)

    for value in ["dibuka", "ditahan", "dibatalkan", "terisi"]:
        patch = client.patch(
            f"/api/v1/recruitment/job-orders/{jo_id}",
            headers=headers,
            json={"business_status": value},
        )
        assert patch.status_code == 200, f"PATCH business_status={value}: {patch.text}"
        assert patch.json()["business_status"] == value

        listing = client.get("/api/v1/recruitment/job-orders", headers=headers)
        assert listing.status_code == 200, f"GET setelah business_status={value}: {listing.text}"
        row = next(jo for jo in listing.json() if jo["id"] == jo_id)
        assert row["business_status"] == value
