"""Gerbang lisensi varian SoulX-FlashHead -- dicek SEBELUM model dimuat.

Hasil cek lisensi (2026-10-23, lihat flashhead-server/README.md):
- Kode repo, bobot DiT 1.3B, VAE Wan 2.1, wav2vec2-base-960h: Apache-2.0.
- Varian `lite` memuat VAE LTX-Video 0.9 (`model_type == "lite"` ->
  `VAE_LTX` di flash_head_pipeline.py) yang berlisensi RAIL-M Lightricks:
  "academic or research purposes only", komersialisasi DIKECUALIKAN.
- Varian `pro` hanya memakai VAE Wan (Apache-2.0), tapi menurut README resmi
  hanya 10,8 FPS di 1x RTX 4090 (real-time butuh 2x RTX 5090).

Keputusan PoC: default `pro`. `lite` hanya jalan dengan pengakuan eksplisit
FLASHHEAD_ACK_NONCOMMERCIAL=1 -- untuk riset/PoC internal, BUKAN untuk
kandidat sungguhan di produk komersial.
"""

from __future__ import annotations

MODEL_TYPES = ("pro", "lite")


class LicenseError(RuntimeError):
    pass


def check_license(model_type: str | None, ack_noncommercial: str | None) -> str:
    """Kembalikan model_type yang boleh dipakai, atau raise LicenseError."""
    value = (model_type or "pro").strip().lower()
    if value not in MODEL_TYPES:
        raise LicenseError(f"FLASHHEAD_MODEL_TYPE={model_type!r} tidak dikenal (pro|lite)")
    if value == "lite" and (ack_noncommercial or "").strip() != "1":
        raise LicenseError(
            "Varian lite memakai VAE LTX-Video 0.9 (RAIL-M Lightricks: hanya riset/akademik, "
            "komersialisasi dilarang). Set FLASHHEAD_ACK_NONCOMMERCIAL=1 hanya untuk PoC/riset "
            "internal, atau pakai FLASHHEAD_MODEL_TYPE=pro."
        )
    return value
