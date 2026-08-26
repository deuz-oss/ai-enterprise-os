"""Klien LLM minimal dengan skema API kompatibel OpenAI (Chat Completions).

Provider mana pun yang mengikuti skema OpenAI didukung: OpenAI, vLLM,
Ollama (endpoint /v1), LM Studio, Groq, dsb. Konfigurasi lewat env:

- AI_BASE_URL : alamat dasar, mis. https://api.openai.com/v1
- AI_API_KEY  : opsional (provider lokal biasanya tidak perlu)
- AI_MODEL    : nama model, mis. gpt-4o-mini

Prinsip kerahasiaan (PRD): cukup arahkan AI_BASE_URL ke model yang
di-host sendiri agar data tidak keluar dari infrastruktur internal.
"""

from __future__ import annotations

import json
import logging
import re

import httpx
from fastapi import HTTPException

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TIMEOUT = httpx.Timeout(120.0, connect=10.0)
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def ai_configured() -> bool:
    return get_settings().ai_configured


def chat_completion(system: str, user: str, *, json_mode: bool = True) -> dict | str:
    """Panggil endpoint /chat/completions dan kembalikan isinya.

    json_mode=True memaksa keluaran JSON object dan hasil dikembalikan
    sebagai dict yang sudah di-parse. Gagal apapun dilempar sebagai
    HTTPException (503 belum dikonfigurasi, 502 provider bermasalah).
    """
    settings = get_settings()
    if not settings.ai_configured:
        raise HTTPException(
            status_code=503,
            detail="Fitur AI belum aktif. Set AI_BASE_URL (dan AI_API_KEY) di .env.",
        )
    payload: dict = {
        "model": settings.ai_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    return _post_chat(payload, json_mode=json_mode)


def vision_completion(
    system: str, user: str, *, image_b64: str, mime_type: str = "image/png"
) -> dict | str:
    """Chat completion multimodal (satu panggilan OCR + ekstraksi, PRD §10.4).

    Gambar dikirim sebagai data URL base64 pada content bagian `image_url`.
    """
    settings = get_settings()
    if not settings.ai_configured:
        raise HTTPException(
            status_code=503,
            detail="Fitur AI belum aktif. Set AI_BASE_URL (dan AI_API_KEY) di .env.",
        )
    payload: dict = {
        "model": settings.ai_model,
        "messages": [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_b64}"},
                    },
                ],
            },
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    return _post_chat(payload, json_mode=True)


def _post_chat(payload: dict, *, json_mode: bool) -> dict | str:
    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.ai_api_key:
        headers["Authorization"] = f"Bearer {settings.ai_api_key}"

    url = settings.ai_base_url.rstrip("/") + "/chat/completions"  # type: ignore[union-attr]
    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=_TIMEOUT)
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as exc:
        logger.error("LLM HTTP %s: %s", exc.response.status_code, exc.response.text[:500])
        raise HTTPException(status_code=502, detail="Provider AI mengembalikan error") from exc
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        logger.error("LLM request gagal: %s", exc)
        raise HTTPException(status_code=502, detail="Gagal menghubungi provider AI") from exc

    if not json_mode:
        return str(content)

    cleaned = _FENCE_RE.sub("", str(content)).strip()
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error("LLM bukan JSON valid: %s", cleaned[:300])
        raise HTTPException(status_code=502, detail="Respons AI bukan JSON valid") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=502, detail="Respons AI berformat tak terduga")
    return parsed


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Hitung vektor embedding via endpoint /embeddings (skema OpenAI)."""
    settings = get_settings()
    if not settings.ai_configured:
        raise HTTPException(
            status_code=503,
            detail="Fitur AI belum aktif. Set AI_BASE_URL (dan AI_API_KEY) di .env.",
        )
    headers = {"Content-Type": "application/json"}
    if settings.ai_api_key:
        headers["Authorization"] = f"Bearer {settings.ai_api_key}"
    url = settings.ai_base_url.rstrip("/") + "/embeddings"  # type: ignore[union-attr]
    try:
        resp = httpx.post(
            url,
            headers=headers,
            json={"model": settings.ai_embedding_model, "input": texts},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = sorted(resp.json()["data"], key=lambda item: item["index"])
        vectors: list[list[float]] = [item["embedding"] for item in data]
    except httpx.HTTPStatusError as exc:
        logger.error("Embedding HTTP %s: %s", exc.response.status_code, exc.response.text[:500])
        raise HTTPException(status_code=502, detail="Provider AI mengembalikan error") from exc
    except (httpx.HTTPError, KeyError, IndexError, TypeError) as exc:
        logger.error("Permintaan embedding gagal: %s", exc)
        raise HTTPException(status_code=502, detail="Gagal menghitung embedding") from exc
    if len(vectors) != len(texts):
        raise HTTPException(status_code=502, detail="Jumlah embedding tidak sesuai")
    return vectors
