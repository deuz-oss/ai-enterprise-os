"""flashhead-server -- inferensi SoulX-FlashHead streaming di server GPU.

Dijalankan dari DALAM checkout repo resmi Soul-AILab/SoulX-FlashHead (commit
dikunci di Dockerfile): `flash_head/inference.py` membuka
`flash_head/configs/infer_params.yaml` dengan path relatif.

Model hanya dipanggil lewat fungsi resmi `flash_head.inference`
(get_pipeline, get_base_data, get_infer_params, get_audio_embedding,
run_pipeline), mengikuti loop streaming `gradio_app_streaming.py` resmi:
deque audio 16 kHz sepanjang `cached_audio_duration`, embedding pada jendela
[audio_end_idx - frame_num, audio_end_idx), lalu `video[motion_frames_num:]`.
Tidak ada API model yang dikarang.

Sesi paralel: pipeline resmi menyimpan state per stream (gambar referensi,
latent gerak, generator acak), jadi tiap slot = SATU instance pipeline
(FLASHHEAD_MAX_SESSIONS instance, bobot dimuat berulang). Panggilan GPU
diserialkan satu kunci. BELUM DIUKUR di GPU sungguhan -- lihat README.

Protokol WebSocket `/stream` (klien: avatar-worker/renderers.py):
  -> {"type":"start","image":<base64>,"seed":int}
  <- {"type":"ready","slice_frames":n,"fps":25,"sample_rate":16000,...}
     atau {"type":"error","code":"busy"|"bad_image","detail":...}
  -> biner: PCM int16 mono 16 kHz, tepat slice_frames*640 sampel
  <- biner JPEG per frame (slice_frames buah), lalu {"type":"chunk_done"}
  -> {"type":"reset"}  (kandidat memotong: konteks audio dikosongkan)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import tempfile
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np
from aiohttp import WSMsgType, web
from license_gate import check_license

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("flashhead-server")

MODEL_TYPE = check_license(
    os.environ.get("FLASHHEAD_MODEL_TYPE"), os.environ.get("FLASHHEAD_ACK_NONCOMMERCIAL")
)
CKPT_DIR = os.environ.get("FLASHHEAD_CKPT_DIR", "/models/SoulX-FlashHead-1_3B")
WAV2VEC_DIR = os.environ.get("FLASHHEAD_WAV2VEC_DIR", "/models/wav2vec2-base-960h")
MAX_SESSIONS = int(os.environ.get("FLASHHEAD_MAX_SESSIONS") or 1)
USE_FACE_CROP = (os.environ.get("FLASHHEAD_FACE_CROP") or "0") == "1"
JPEG_QUALITY = int(os.environ.get("FLASHHEAD_JPEG_QUALITY") or 85)

# Import berat SETELAH gerbang lisensi (model tidak dimuat bila ditolak).
import cv2  # noqa: E402
import torch  # noqa: E402
from flash_head.inference import (  # noqa: E402
    get_audio_embedding,
    get_base_data,
    get_infer_params,
    get_pipeline,
    run_pipeline,
)


class Engine:
    def __init__(self) -> None:
        logger.info("Memuat %d pipeline FlashHead (%s)...", MAX_SESSIONS, MODEL_TYPE)
        self.pipelines = [
            get_pipeline(
                world_size=1, ckpt_dir=CKPT_DIR, model_type=MODEL_TYPE, wav2vec_dir=WAV2VEC_DIR
            )
            for _ in range(MAX_SESSIONS)
        ]
        # get_pipeline mengisi motion_frames_num di infer_params global.
        p = get_infer_params()
        self.sample_rate = int(p["sample_rate"])
        self.fps = int(p["tgt_fps"])
        self.frame_num = int(p["frame_num"])
        self.motion_frames_num = int(p["motion_frames_num"])
        self.slice_frames = self.frame_num - self.motion_frames_num
        self.slice_samples = self.slice_frames * self.sample_rate // self.fps
        self.cached_samples = self.sample_rate * int(p["cached_audio_duration"])
        self.audio_end_idx = int(p["cached_audio_duration"]) * self.fps
        self.audio_start_idx = self.audio_end_idx - self.frame_num
        self.width, self.height = int(p["width"]), int(p["height"])
        self.free: list[int] = list(range(MAX_SESSIONS))
        self.gpu_lock = threading.Lock()
        logger.info(
            "Siap: slice %d frame (%d sampel 16 kHz), %d slot",
            self.slice_frames,
            self.slice_samples,
            MAX_SESSIONS,
        )

    def acquire(self) -> int | None:
        return self.free.pop() if self.free else None

    def release(self, slot: int) -> None:
        self.free.append(slot)

    def prepare(self, slot: int, image_path: str, seed: int) -> None:
        with self.gpu_lock:
            get_base_data(
                self.pipelines[slot],
                cond_image_path_or_dir=image_path,
                base_seed=seed,
                use_face_crop=USE_FACE_CROP,
            )

    def infer(self, slot: int, audio: np.ndarray) -> np.ndarray:
        pipeline = self.pipelines[slot]
        with self.gpu_lock:
            emb = get_audio_embedding(pipeline, audio, self.audio_start_idx, self.audio_end_idx)
            video = run_pipeline(pipeline, emb)
            video = video[self.motion_frames_num :]
            torch.cuda.synchronize()
            return video.cpu().numpy().astype(np.uint8)  # (frame, H, W, 3) RGB


def _jpeg(frame: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(
        ".jpg", cv2.cvtColor(frame, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
    )
    if not ok:
        raise RuntimeError("encode JPEG gagal")
    return buf.tobytes()


async def stream(request: web.Request) -> web.WebSocketResponse:
    engine: Engine = request.app["engine"]
    ws = web.WebSocketResponse(max_msg_size=0, heartbeat=20)
    await ws.prepare(request)
    msg = await ws.receive()
    try:
        start = json.loads(msg.data) if msg.type == WSMsgType.TEXT else {}
    except ValueError:
        start = {}
    if start.get("type") != "start":
        await ws.close()
        return ws
    slot = engine.acquire()
    if slot is None:
        await ws.send_json({"type": "error", "code": "busy", "detail": "semua slot GPU terpakai"})
        await ws.close()
        return ws

    tmp = Path(tempfile.mkstemp(suffix=".png")[1])
    try:
        try:
            tmp.write_bytes(base64.b64decode(start["image"]))
            await asyncio.to_thread(engine.prepare, slot, str(tmp), int(start.get("seed", 9999)))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Foto referensi ditolak: %r", exc)
            await ws.send_json({"type": "error", "code": "bad_image", "detail": str(exc)})
            await ws.close()
            return ws
        await ws.send_json(
            {
                "type": "ready",
                "slice_frames": engine.slice_frames,
                "fps": engine.fps,
                "sample_rate": engine.sample_rate,
                "width": engine.width,
                "height": engine.height,
            }
        )
        # Sama dengan inference_worker resmi: deque berisi nol sepanjang
        # cached_audio_duration, diisi audio float [-1, 1] per potongan.
        dq: deque[float] = deque([0.0] * engine.cached_samples, maxlen=engine.cached_samples)
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                pcm = np.frombuffer(msg.data, dtype=np.int16).astype(np.float32) / 32768.0
                if len(pcm) != engine.slice_samples:
                    await ws.send_json({"type": "error", "code": "bad_chunk"})
                    break
                dq.extend(pcm.tolist())
                t0 = time.monotonic()
                frames = await asyncio.to_thread(engine.infer, slot, np.array(dq))
                for frame in frames:
                    await ws.send_bytes(_jpeg(frame))
                await ws.send_json(
                    {"type": "chunk_done", "seconds": round(time.monotonic() - t0, 3)}
                )
            elif msg.type == WSMsgType.TEXT and json.loads(msg.data).get("type") == "reset":
                dq.extend([0.0] * engine.cached_samples)
            elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                break
    finally:
        tmp.unlink(missing_ok=True)
        engine.release(slot)
    return ws


async def health(request: web.Request) -> web.Response:
    engine: Engine = request.app["engine"]
    return web.json_response(
        {"model_type": MODEL_TYPE, "free_slots": len(engine.free), "max_sessions": MAX_SESSIONS}
    )


def main() -> None:
    app = web.Application()
    app["engine"] = Engine()
    app.add_routes([web.get("/stream", stream), web.get("/health", health)])
    web.run_app(app, port=int(os.environ.get("PORT") or 8010))


if __name__ == "__main__":
    main()
