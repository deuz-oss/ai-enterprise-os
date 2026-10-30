"""Batas sesi interview suara: durasi maksimum & aturan coba-ulang unggahan.

Modul murni (tanpa import LiveKit) supaya bisa dites tanpa infra suara.

Uji 2026-10-29: sesi yang ditinggal kandidat dengan panggilan masih terbuka
berjalan 2 jam (VAD sesekali terpicu derau, agen terus menunggu). Rekamannya
melebihi batas backend (MAX_RECORDING_BYTES 60 MB ~ 60 menit) sehingga
ditolak 413 -- tiga kali, karena agen mencoba ulang semua kegagalan -- lalu
salinan lokal dihapus: rekaman hilang.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("ai-interview-agent")

# Di bawah batas rekaman backend (~60 menit) dengan jarak aman; interview
# terstruktur biasa jauh lebih pendek dari ini.
DEFAULT_MAX_MINUTES = 45.0

# Diucapkan apa adanya lewat TTS (tanpa LLM) saat batas waktu tercapai.
TIME_UP_LINE = (
    "Mohon maaf, waktu interview sudah habis, jadi sesi ini saya akhiri sekarang. "
    "Jawaban yang sudah Anda berikan tersimpan dan akan ditinjau oleh tim rekrutmen. "
    "Terima kasih atas waktu Anda."
)


def parse_max_minutes(raw: str | None) -> float:
    """AI_INTERVIEW_MAX_MINUTES; 0 atau negatif = tanpa batas (tidak dianjurkan:
    rekaman > ~60 menit ditolak backend)."""
    try:
        return float(raw) if raw else DEFAULT_MAX_MINUTES
    except ValueError:
        logger.warning("AI_INTERVIEW_MAX_MINUTES=%r bukan angka -- dipakai default", raw)
        return DEFAULT_MAX_MINUTES


def retryable_status(status: int) -> bool:
    """Coba ulang unggahan hanya untuk kegagalan sementara: 5xx, 408 (timeout),
    429 (dibatasi). 4xx lain (413 terlalu besar, 422 ditolak, 401 tanda
    tangan) akan gagal persis sama di percobaan berikutnya."""
    return status >= 500 or status in (408, 429)
