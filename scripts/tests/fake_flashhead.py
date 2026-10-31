"""flashhead-server PALSU untuk menguji bench_avatar.py tanpa GPU.

Protokol sama dengan `flashhead-server/server.py` (start/ready/busy, chunk PCM
tepat slice_frames*640 sampel -> slice_frames JPEG + chunk_done, reset,
/health dengan free_slots). "Inferensi" = sleep `infer_ms` di bawah SATU kunci
global (meniru gpu_lock server asli), jadi N sesi paralel saling mengantre.
Tidak ada model, tidak ada VRAM -- angka dari server ini tidak bermakna untuk
performa GPU.

    python scripts/tests/fake_flashhead.py --port 8010 --infer-ms 400 --max-sessions 3
"""

from __future__ import annotations

import argparse
import asyncio
import json

from aiohttp import WSMsgType, web

# JPEG minimal yang sah secara penanda (SOI ... EOI); isi tidak di-decode bench.
FAKE_JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64 + b"\xff\xd9"


def make_app(
    *,
    slice_frames: int = 28,
    infer_ms: float = 100.0,
    max_sessions: int = 1,
    ready_ms: float = 0.0,
    drop_after_chunks: int | None = None,
) -> web.Application:
    state = {"free": max_sessions, "lock": asyncio.Lock(), "chunks": 0, "resets": 0}

    async def stream(request: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(max_msg_size=0, heartbeat=20)
        await ws.prepare(request)
        msg = await ws.receive()
        start = json.loads(msg.data) if msg.type == WSMsgType.TEXT else {}
        if start.get("type") != "start" or not start.get("image"):
            await ws.close()
            return ws
        if state["free"] <= 0:
            await ws.send_json({"type": "error", "code": "busy", "detail": "slot penuh"})
            await ws.close()
            return ws
        state["free"] -= 1
        try:
            await asyncio.sleep(ready_ms / 1000)
            await ws.send_json(
                {
                    "type": "ready",
                    "slice_frames": slice_frames,
                    "fps": 25,
                    "sample_rate": 16000,
                    "width": 512,
                    "height": 512,
                }
            )
            done = 0
            async for msg in ws:
                if msg.type == WSMsgType.BINARY:
                    if len(msg.data) != slice_frames * 640 * 2:
                        await ws.send_json({"type": "error", "code": "bad_chunk"})
                        break
                    if drop_after_chunks is not None and done >= drop_after_chunks:
                        break
                    async with state["lock"]:
                        await asyncio.sleep(infer_ms / 1000)
                    for _ in range(slice_frames):
                        await ws.send_bytes(FAKE_JPEG)
                    await ws.send_json({"type": "chunk_done", "seconds": infer_ms / 1000})
                    done += 1
                    state["chunks"] += 1
                elif msg.type == WSMsgType.TEXT and json.loads(msg.data).get("type") == "reset":
                    state["resets"] += 1
                elif msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                    break
        finally:
            state["free"] += 1
        await ws.close()
        return ws

    async def health(request: web.Request) -> web.Response:
        return web.json_response(
            {"model_type": "fake", "free_slots": state["free"], "max_sessions": max_sessions}
        )

    app = web.Application()
    app["state"] = state
    app.add_routes([web.get("/stream", stream), web.get("/health", health)])
    return app


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--port", type=int, default=8010)
    p.add_argument("--slice-frames", type=int, default=28)
    p.add_argument("--infer-ms", type=float, default=100.0)
    p.add_argument("--max-sessions", type=int, default=1)
    p.add_argument("--ready-ms", type=float, default=0.0)
    a = p.parse_args()
    web.run_app(
        make_app(
            slice_frames=a.slice_frames,
            infer_ms=a.infer_ms,
            max_sessions=a.max_sessions,
            ready_ms=a.ready_ms,
        ),
        host="127.0.0.1",
        port=a.port,
    )


if __name__ == "__main__":
    main()
