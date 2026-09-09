"""Reverse geocoding best-effort (Fase 36) -- ubah koordinat GPS absensi
jadi alamat yang bisa dibaca manusia.

Pakai Nominatim (OpenStreetMap), gratis tanpa API key. Timeout pendek dan
semua kegagalan ditangkap di sini -- caller (`ess/service.py::mobile_clock`)
TIDAK BOLEH gagal gara-gara geocoding lambat/rusak, absensi lebih penting
daripada alamat yang cuma pemanis.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(5.0, connect=3.0)
_USER_AGENT = "AI-Enterprise-OS/1.0"


def reverse_geocode(lat: float, lng: float) -> str | None:
    try:
        resp = httpx.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lng, "format": "jsonv2"},
            headers={"User-Agent": _USER_AGENT},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        display_name = resp.json().get("display_name")
        return str(display_name) if display_name else None
    except Exception:  # noqa: BLE001 - best-effort, tidak boleh mematahkan absensi
        logger.warning("Reverse geocoding gagal untuk (%s, %s)", lat, lng, exc_info=True)
        return None
