"""Baca KTP/NPWP saat kandidat mengunggah di onboarding self-service
(peluang AI #9 audit 2026-10-08).

Aturan:
- Hanya bila kandidat MENCENTANG izin pemrosesan AI untuk unggahan itu
  (foto KTP = data pribadi, UU PDP; persetujuan form baru dicentang saat
  submit, jadi tidak bisa dipakai di sini).
- Hasil TIDAK disimpan: dikembalikan ke browser sebagai draf yang kandidat
  periksa lalu masukkan ke form sendiri. Yang tersimpan tetap isian form yang
  disubmit kandidat.
- AI hanya membaca; nomor divalidasi deterministik (NIK 16 digit + tanggal
  lahir yang terkandung di NIK, NPWP 15/16 digit, nama vs nama kandidat).
"""

from __future__ import annotations

import base64
import re
from datetime import date

EXTRACTABLE_TYPES = {"ktp", "npwp"}
EXTRACTABLE_MIME = {"image/png", "image/jpeg"}

_PROMPTS = {
    "ktp": (
        "Anda mesin pembaca KTP Indonesia. Baca gambar KTP dan kembalikan HANYA JSON: "
        '{"nik": string|null, "nama": string|null, "tempat_lahir": string|null, '
        '"tanggal_lahir": "YYYY-MM-DD"|null, "alamat": string|null, "rt_rw": string|null, '
        '"kelurahan": string|null, "kecamatan": string|null, "kota": string|null, '
        '"provinsi": string|null}. Gunakan null untuk yang tidak terbaca jelas. '
        "Jangan menebak atau melengkapi angka yang buram."
    ),
    "npwp": (
        "Anda mesin pembaca kartu NPWP Indonesia. Baca gambar dan kembalikan HANYA JSON: "
        '{"npwp": string|null, "nama": string|null}. Gunakan null untuk yang tidak '
        "terbaca jelas. Jangan menebak angka yang buram."
    ),
}


def _digits(value: object) -> str:
    return re.sub(r"\D", "", str(value or ""))


def _text(value: object, limit: int = 200) -> str | None:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit] or None


def _parse_date(value: object) -> date | None:
    try:
        return date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def nik_birth_date_matches(nik: str, birth: date) -> bool:
    """Digit 7-12 NIK = DDMMYY lahir; perempuan: DD + 40."""
    day, month, yy = int(nik[6:8]), int(nik[8:10]), int(nik[10:12])
    if day > 40:
        day -= 40
    return (day, month, yy) == (birth.day, birth.month, birth.year % 100)


def _name_tokens(name: str | None) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", (name or "").lower()) if len(t) > 1}


def extract_identity(
    document_type: str, data: bytes, mime_type: str, *, candidate_name: str | None
) -> dict:
    """Draf isian dari foto KTP/NPWP. Tidak pernah melempar: gagal = status."""
    from app.core.llm import ai_configured, vision_completion

    if document_type not in EXTRACTABLE_TYPES:
        return {"status": "unsupported", "fields": {}, "warnings": []}
    if mime_type not in EXTRACTABLE_MIME:
        return {
            "status": "unsupported",
            "fields": {},
            "warnings": ["Isi otomatis hanya untuk foto PNG/JPEG, bukan PDF."],
        }
    if not ai_configured():
        return {"status": "ai_off", "fields": {}, "warnings": []}
    try:
        raw = vision_completion(
            system=_PROMPTS[document_type],
            user="Baca dokumen ini.",
            image_b64=base64.b64encode(data).decode(),
            mime_type=mime_type,
            feature=f"onboarding.extract_{document_type}",
        )
    except Exception:  # noqa: BLE001 - isi otomatis opsional, unggahan tetap berhasil
        return {
            "status": "failed",
            "fields": {},
            "warnings": ["Dokumen tidak bisa dibaca otomatis -- isi manual."],
        }
    got: dict = raw if isinstance(raw, dict) else {}
    fields: dict = {}
    warnings: list[str] = []

    if document_type == "ktp":
        nik = _digits(got.get("nik"))
        if len(nik) == 16:
            fields["ktp_no"] = nik
            birth = _parse_date(got.get("tanggal_lahir"))
            if birth and not nik_birth_date_matches(nik, birth):
                warnings.append(
                    "Tanggal lahir di NIK tidak sama dengan tanggal lahir yang terbaca -- "
                    "periksa NIK."
                )
        elif nik:
            warnings.append(f"NIK terbaca {len(nik)} digit (harus 16) -- tidak diisikan.")
        address = {
            "province": _text(got.get("provinsi")),
            "city": _text(got.get("kota")),
            "district": _text(got.get("kecamatan")),
            "detail": _text(
                ", ".join(
                    p
                    for p in (
                        _text(got.get("alamat")),
                        f"RT/RW {_text(got.get('rt_rw'))}" if _text(got.get("rt_rw")) else None,
                        _text(got.get("kelurahan")),
                    )
                    if p
                ),
                limit=500,
            ),
        }
        address = {k: v for k, v in address.items() if v}
        if address:
            fields["citizen_address"] = address
    else:
        npwp = _digits(got.get("npwp"))
        if len(npwp) in (15, 16):
            fields["npwp_no"] = npwp
        elif npwp:
            warnings.append(f"NPWP terbaca {len(npwp)} digit (harus 15/16) -- tidak diisikan.")

    read_name = _text(got.get("nama"))
    if read_name:
        fields["name_on_document"] = read_name
        if candidate_name and not (_name_tokens(read_name) & _name_tokens(candidate_name)):
            warnings.append(
                f'Nama di dokumen ("{read_name}") berbeda dari nama kandidat ("{candidate_name}").'
            )
    status = "ok" if any(k != "name_on_document" for k in fields) else "failed"
    if status == "failed" and not warnings:
        warnings.append("Tidak ada data yang terbaca jelas -- isi manual.")
    return {"status": status, "fields": fields, "warnings": warnings}
