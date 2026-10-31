"""Avatar video pewawancara AI (PoC self-hosted) -- logika keputusan.

Modul ini TANPA import LiveKit supaya bisa dites tanpa infra suara (pola
sama dengan interview_flow.py). Lem ke LiveKit ada di `avatar.py`.

Prinsip: avatar itu TAMBAHAN. Apa pun yang gagal (flag salah, worker mati,
kapasitas GPU penuh, avatar tidak join tepat waktu) berakhir di mode
voice-only seperti sebelum fitur ini ada -- dengan log warning, bukan crash
dan bukan sesi kandidat yang menggantung.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import logging
from collections.abc import Awaitable, Mapping
from dataclasses import dataclass

import httpx

logger = logging.getLogger("ai-interview-agent.avatar")

# "none" = voice-only (default, perilaku lama). "self" = worker avatar
# sendiri (`avatar-worker/`). Integrasi vendor (mis. Tavus) belum ada di repo.
AVATAR_PROVIDERS = ("none", "self")

# Identitas peserta avatar di room. Satu room = satu avatar, jadi konstan.
AVATAR_IDENTITY = "ai-interview-avatar"

# Header tanda tangan agent -> avatar-worker. Pola sama dengan
# X-Agent-Signature agent -> backend: HMAC LIVEKIT_API_SECRET atas nama room.
SIGNATURE_HEADER = "X-Avatar-Signature"


def parse_provider(raw: str | None) -> str:
    value = (raw or "none").strip().lower()
    if value in AVATAR_PROVIDERS:
        return value
    logger.warning("AVATAR_PROVIDER=%r tidak dikenal -- dipakai 'none' (voice-only)", raw)
    return "none"


def _float(env: Mapping[str, str], key: str, default: float) -> float:
    try:
        return float(env.get(key) or default)
    except ValueError:
        logger.warning("%s bukan angka -- dipakai default %s", key, default)
        return default


@dataclass(frozen=True)
class AvatarSettings:
    provider: str = "none"
    worker_url: str = ""
    # Batas tunggu avatar join + publikasi video sebelum sesi dimulai.
    join_timeout: float = 15.0
    # Batas waktu permintaan HTTP ke worker. Worker baru menjawab setelah
    # renderer siap (FlashHead: koneksi ke server GPU), jadi lebih longgar.
    request_timeout: float = 20.0
    # Batas tunggu kandidat masuk room sebelum sapaan (mode avatar saja).
    # Kandidat yang keburu pergi tidak boleh menahan job & slot avatar.
    candidate_timeout: float = 120.0

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> AvatarSettings:
        return cls(
            provider=parse_provider(env.get("AVATAR_PROVIDER")),
            worker_url=(env.get("AVATAR_WORKER_URL") or "http://avatar-worker:8090").rstrip("/"),
            join_timeout=_float(env, "AVATAR_JOIN_TIMEOUT", 15.0),
            request_timeout=_float(env, "AVATAR_REQUEST_TIMEOUT", 20.0),
            candidate_timeout=_float(env, "AVATAR_CANDIDATE_TIMEOUT", 120.0),
        )

    @property
    def enabled(self) -> bool:
        return self.provider == "self" and bool(self.worker_url)


def sign(secret: str, room: str) -> str:
    return hmac.new(secret.encode(), room.encode(), hashlib.sha256).hexdigest()


@dataclass(frozen=True)
class AvatarDecision:
    enabled: bool
    reason: str
    identity: str = AVATAR_IDENTITY


async def fetch_reference_image(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: Mapping[str, str],
    timeout: float = 5.0,
) -> bytes | None:
    """Foto avatar milik tenant dari backend (`GET .../voice/avatar-image`).
    None = pakai foto bawaan worker (env AVATAR_REFERENCE_IMAGE): tenant belum
    punya foto (404), backend error, atau timeout. Tidak pernah raise --
    foto avatar tidak boleh menggagalkan interview."""
    try:
        resp = await client.get(url, headers=dict(headers), timeout=timeout)
    except httpx.HTTPError as exc:
        logger.warning("Foto avatar tenant gagal diambil (%s) -- foto bawaan", type(exc).__name__)
        return None
    if resp.status_code == 404:
        logger.info("Tenant belum punya foto avatar -- foto bawaan worker dipakai")
        return None
    if resp.status_code != 200 or not resp.content:
        logger.warning("Foto avatar tenant: backend HTTP %d -- foto bawaan", resp.status_code)
        return None
    return resp.content


async def request_avatar(
    client: httpx.AsyncClient,
    settings: AvatarSettings,
    *,
    room: str,
    agent_identity: str,
    secret: str,
    reference_image: bytes | None = None,
) -> AvatarDecision:
    """Minta worker menyiapkan avatar untuk `room`. Tidak pernah raise.
    `reference_image` = foto avatar tenant (JPEG dari backend); dikirim
    sebagai base64 di body. Tanda tangan tetap atas nama room saja -- port
    worker tidak dibuka ke host, hanya agen di jaringan internal yang bicara."""
    body: dict[str, str] = {"room": room, "agent_identity": agent_identity}
    if reference_image:
        body["reference_image_b64"] = base64.b64encode(reference_image).decode("ascii")
    try:
        resp = await client.post(
            f"{settings.worker_url}/sessions",
            json=body,
            headers={SIGNATURE_HEADER: sign(secret, room)},
            # Connect dibatasi ketat: worker yang mati tidak boleh menunda
            # sapaan ke kandidat (uji E2E: DNS Docker untuk container mati
            # baru gagal ~9 dtk). Respons boleh lama -- renderer sedang siap.
            timeout=httpx.Timeout(settings.request_timeout, connect=3.0),
        )
    except httpx.HTTPError as exc:
        return AvatarDecision(False, f"worker avatar tidak terjangkau ({type(exc).__name__})")
    if resp.status_code == 503:
        # Kapasitas GPU penuh / renderer tidak siap: sesi baru voice-only,
        # BUKAN ditolak (keputusan PoC).
        return AvatarDecision(False, f"worker avatar penuh/tidak siap: {_detail(resp)}")
    if resp.status_code not in (200, 201):
        return AvatarDecision(False, f"worker avatar menjawab HTTP {resp.status_code}")
    try:
        identity = str(resp.json().get("identity") or AVATAR_IDENTITY)
    except ValueError:
        identity = AVATAR_IDENTITY
    return AvatarDecision(True, "ok", identity=identity)


async def release_avatar(
    client: httpx.AsyncClient,
    settings: AvatarSettings,
    *,
    room: str,
    secret: str,
    timeout: float = 5,
) -> None:
    """Lepas slot avatar di worker. Kegagalan hanya dicatat -- worker juga
    melepas slot sendiri saat agent keluar dari room."""
    try:
        await client.delete(
            f"{settings.worker_url}/sessions/{room}",
            headers={SIGNATURE_HEADER: sign(secret, room)},
            timeout=timeout,
        )
    except httpx.HTTPError:
        logger.warning("Gagal melepas slot avatar untuk room %s", room, exc_info=True)


async def wait_ready(ready: Awaitable[object], timeout: float) -> bool:
    """True bila `ready` selesai dalam `timeout` detik; False bila habis
    waktu atau gagal (keduanya berarti: jalan voice-only)."""
    try:
        await asyncio.wait_for(ready, timeout=timeout)
    except TimeoutError:
        return False
    except Exception:  # noqa: BLE001 - apa pun alasannya, jatuh ke voice-only
        logger.warning("Menunggu avatar gagal", exc_info=True)
        return False
    return True


def _detail(resp: httpx.Response) -> str:
    try:
        return str(resp.json().get("detail") or resp.text)
    except ValueError:
        return resp.text
