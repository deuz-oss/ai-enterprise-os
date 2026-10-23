"""Uji E2E wiring avatar dengan KANDIDAT SINTETIS (pola uji Fase 66 PRD).

Peserta LiveKit sungguhan memakai token dari `voice/start`, mendengarkan
pewawancara (deteksi selesai bicara dari energi audio), memutar jawaban lisan
hasil TTS, lalu memeriksa hasil di backend: transkrip, penilaian, dan kedua
kanal audio.ogg (0 = kandidat, 1 = pewawancara AI).

Yang dicatat: apakah video avatar diterima (jumlah frame + 1 frame disimpan
sebagai PNG), dari peserta mana suara pewawancara datang tiap giliran
(avatar vs agen langsung = fallback), dan energi per kanal rekaman.

Prasyarat: `docker compose --profile voice --profile avatar up -d` dengan
AVATAR_PROVIDER=self, `.env` terisi (ADMIN_*, LIVEKIT_*, AI_*). Jalankan
dengan venv agent (punya livekit rtc, httpx, numpy, PyAV):

    agent/.venv/Scripts/python avatar-worker/scripts/e2e_synthetic_candidate.py \
        [--kill-avatar-after-first-turn] [--out DIR]

Alat uji pengembang, bukan bagian image produksi.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
import numpy as np
from livekit import rtc

ROOT = Path(__file__).resolve().parents[2]
API = "http://localhost:8000/api/v1"
ANSWER = (
    "Di pekerjaan saya sebelumnya sebagai staf layanan pelanggan, saya menangani sekitar "
    "tiga puluh keluhan per hari. Saya mendengarkan dulu, mencatat masalahnya, lalu "
    "menawarkan solusi dan menindaklanjutinya dalam satu hari kerja."
)
SPEECH_RMS = 300  # ambang energi "sedang bicara" (int16)


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"')
    return env


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


class Listener:
    """Memantau energi audio yang diterima, per peserta pengirim."""

    def __init__(self) -> None:
        self.last_speech = 0.0
        self.speech_by: dict[str, float] = {}  # identitas -> detik bicara terdengar
        self.video_frames = 0
        self.saved_frame = False
        self.avatar_identity: str | None = None
        self.tasks: list[asyncio.Task] = []

    async def audio(self, track: rtc.Track, identity: str) -> None:
        async for ev in rtc.AudioStream(track, sample_rate=24000, num_channels=1):
            pcm = np.frombuffer(bytes(ev.frame.data), dtype=np.int16)
            if len(pcm) and np.sqrt(np.mean(pcm.astype(np.float32) ** 2)) > SPEECH_RMS:
                self.last_speech = time.monotonic()
                self.speech_by[identity] = self.speech_by.get(identity, 0) + ev.frame.duration

    async def video(self, track: rtc.Track, out_dir: Path) -> None:
        from PIL import Image

        async for ev in rtc.VideoStream(track):
            self.video_frames += 1
            if self.video_frames == 50 and not self.saved_frame:
                f = ev.frame.convert(rtc.VideoBufferType.RGBA)
                img = Image.frombuffer("RGBA", (f.width, f.height), bytes(f.data))
                img.convert("RGB").save(out_dir / "avatar_frame.png")
                self.saved_frame = True

    async def wait_turn_done(self, silence: float, timeout: float) -> bool:
        """Tunggu pewawancara bicara lalu diam `silence` detik."""
        start = time.monotonic()
        heard_since = self.last_speech
        while time.monotonic() - start < timeout:
            await asyncio.sleep(0.2)
            spoke = self.last_speech > max(heard_since, start - 1)
            if spoke and time.monotonic() - self.last_speech > silence:
                return True
        return False


async def tts_pcm(env: dict[str, str], text: str) -> np.ndarray:
    async with httpx.AsyncClient(timeout=60) as http:
        resp = await http.post(
            f"{env['AI_BASE_URL'].rstrip('/')}/audio/speech",
            headers={"Authorization": f"Bearer {env['AI_API_KEY']}"},
            json={
                "model": env.get("AI_TTS_MODEL") or "gpt-4o-mini-tts",
                "voice": "alloy",
                "input": text,
                "response_format": "pcm",  # int16 mono 24 kHz
            },
        )
        resp.raise_for_status()
        return np.frombuffer(resp.content, dtype=np.int16)


async def play(source: rtc.AudioSource, pcm: np.ndarray) -> None:
    step = 240  # 10 ms
    for i in range(0, len(pcm), step):
        chunk = pcm[i : i + step]
        if len(chunk) < step:
            chunk = np.pad(chunk, (0, step - len(chunk)))
        await source.capture_frame(rtc.AudioFrame(chunk.tobytes(), 24000, 1, step))


def setup_interview(env: dict[str, str]) -> tuple[str, str, dict]:
    with httpx.Client(base_url=API, timeout=30) as http:
        login = http.post(
            "/auth/login", json={"email": env["ADMIN_EMAIL"], "password": env["ADMIN_PASSWORD"]}
        )
        login.raise_for_status()
        admin = {"Authorization": f"Bearer {login.json()['access_token']}"}
        tag = uuid.uuid4().hex[:6]
        cand = http.post(
            "/recruitment/candidates",
            json={"full_name": f"Kandidat Sintetis Avatar {tag}"},
            headers=admin,
        )
        cand.raise_for_status()
        tpl = http.post(
            "/ai-interview/templates",
            json={
                "title": f"Uji E2E Avatar {tag}",
                "objective": "Uji wiring avatar video (kandidat sintetis).",
                "mode": "realtime_voice",
                "questions": [
                    {
                        "id": "q1",
                        "order": 1,
                        "prompt": "Ceritakan pengalaman Anda menangani keluhan pelanggan.",
                        "criterion_keys": ["pengalaman"],
                        "follow_up_max": 0,
                    }
                ],
                "criteria": [
                    {
                        "key": "pengalaman",
                        "label": "Relevansi pengalaman",
                        "description": "Contoh konkret menangani keluhan pelanggan.",
                    }
                ],
            },
            headers=admin,
        )
        tpl.raise_for_status()
        http.patch(
            f"/ai-interview/templates/{tpl.json()['id']}", json={"status": "aktif"}, headers=admin
        ).raise_for_status()
        inv = http.post(
            f"/ai-interview/templates/{tpl.json()['id']}/invite",
            json={"candidate_ids": [cand.json()["id"]]},
            headers=admin,
        )
        inv.raise_for_status()
        item = inv.json()["invited"][0]
        return item["invite_token"], item["response_id"], admin


def analyse_recording(data: bytes) -> dict[str, float]:
    """Detik aktif per kanal audio.ogg (jendela 0,5 dtk, opus didekode ke
    float [-1, 1]). Kanal 0 = kandidat, kanal 1 = pewawancara AI."""
    import av

    with av.open(io.BytesIO(data)) as container:
        rate = container.streams.audio[0].rate
        pcm = np.concatenate(
            [f.to_ndarray().astype(np.float64) for f in container.decode(audio=0)], axis=1
        )
    win = rate // 2
    usable = pcm[:, : pcm.shape[1] // win * win]
    rms = np.sqrt(np.mean(usable.reshape(pcm.shape[0], -1, win) ** 2, axis=2))
    return {f"kanal_{i}_detik_aktif": float((r > 0.01).sum() * 0.5) for i, r in enumerate(rms)}


async def main(args: argparse.Namespace) -> int:
    env = load_env()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    report: dict = {"kill_avatar": args.kill_avatar_after_first_turn}

    token, response_id, admin = setup_interview(env)
    report["response_id"] = response_id
    async with httpx.AsyncClient(base_url=API, timeout=30) as http:
        (await http.post(f"/ai-interview/session/{token}/consent")).raise_for_status()
        voice = (await http.post(f"/ai-interview/session/{token}/voice/start")).json()
    log(f"voice/start -> {voice['url']}")

    listener = Listener()
    room = rtc.Room()
    agent_left = asyncio.Event()

    @room.on("track_subscribed")
    def _on_track(track, _pub, participant):
        attrs = dict(participant.attributes)
        is_avatar = bool(attrs.get("lk.publish_on_behalf"))
        if is_avatar:
            listener.avatar_identity = participant.identity
            report["avatar_attributes"] = attrs
            report["avatar_kind"] = int(participant.kind)
        log(f"track {track.kind} dari {participant.identity} (avatar={is_avatar})")
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            listener.tasks.append(asyncio.create_task(listener.audio(track, participant.identity)))
        elif track.kind == rtc.TrackKind.KIND_VIDEO:
            listener.tasks.append(asyncio.create_task(listener.video(track, out_dir)))

    @room.on("participant_disconnected")
    def _on_left(participant):
        log(f"peserta keluar: {participant.identity}")
        if participant.identity != listener.avatar_identity and not participant.attributes.get(
            "lk.publish_on_behalf"
        ):
            agent_left.set()

    answer_pcm = await tts_pcm(env, ANSWER)
    log(f"jawaban TTS siap ({len(answer_pcm) / 24000:.1f} dtk)")
    if args.join_delay:
        # Kandidat lambat masuk (mis. izin mikrofon): sapaan tidak boleh
        # terucap ke room kosong.
        log(f"menunda masuk room {args.join_delay:.0f} dtk")
        await asyncio.sleep(args.join_delay)
    await room.connect(voice["url"], voice["token"])
    source = rtc.AudioSource(24000, 1)
    await room.local_participant.publish_track(
        rtc.LocalAudioTrack.create_audio_track("mic", source),
        rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE),
    )
    log("kandidat sintetis terhubung; menunggu sapaan + pertanyaan")

    if not await listener.wait_turn_done(silence=args.silence, timeout=180):
        log("GAGAL: pewawancara tidak pernah selesai bicara")
        report["error"] = "no_greeting"
    else:
        report["speech_turn1"] = dict(listener.speech_by)
        if args.kill_avatar_after_first_turn:
            log("mematikan avatar-worker (uji fallback di tengah sesi)")
            subprocess.run(
                [
                    "docker",
                    "compose",
                    "--profile",
                    "voice",
                    "--profile",
                    "avatar",
                    "stop",
                    "-t",
                    "0",
                    "avatar-worker",
                ],
                cwd=ROOT,
                check=False,
            )
            await asyncio.sleep(2)
        before = dict(listener.speech_by)
        log("memutar jawaban kandidat")
        await play(source, answer_pcm)
        await play(source, np.zeros(24000, np.int16))
        try:
            await asyncio.wait_for(agent_left.wait(), timeout=420)
        except TimeoutError:
            report["error"] = "agent_never_left"
        after = dict(listener.speech_by)
        report["speech_after_answer"] = {
            k: round(after.get(k, 0) - before.get(k, 0), 2) for k in after
        }
    report["avatar_video_frames"] = listener.video_frames
    for t in listener.tasks:
        t.cancel()
    await room.disconnect()

    # Hasil di backend: transkrip, skor, rekaman.
    async with httpx.AsyncClient(base_url=API, timeout=60) as http:
        resp_data: dict = {}
        for _ in range(60):
            try:
                resp_data = (
                    await http.get(f"/ai-interview/responses/{response_id}", headers=admin)
                ).json()
            except httpx.HTTPError:  # backend sibuk menilai -- coba lagi
                await asyncio.sleep(5)
                continue
            if resp_data.get("has_recording") and resp_data.get("ai_score_overall") is not None:
                break
            await asyncio.sleep(5)
        report["status"] = resp_data.get("status")
        report["ai_score"] = resp_data.get("ai_score_overall")
        report["transcript"] = resp_data.get("transcript_text")
        rec = await http.get(f"/ai-interview/responses/{response_id}/recording-url", headers=admin)
        if rec.status_code == 200:
            audio = await http.get(rec.json()["url"])
            (out_dir / "audio.ogg").write_bytes(audio.content)
            report["recording"] = analyse_recording(audio.content)
        else:
            report["recording"] = f"HTTP {rec.status_code}: {rec.text[:200]}"

    print(json.dumps(report, indent=2, ensure_ascii=False))
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if "error" not in report else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kill-avatar-after-first-turn", action="store_true")
    parser.add_argument("--out", default="e2e-avatar-out")
    # Jeda antarkalimat TTS bisa > 3 dtk di jaringan dev; terlalu kecil ->
    # kandidat sintetis memotong pertanyaan yang belum selesai diputar.
    parser.add_argument("--silence", type=float, default=6.0)
    parser.add_argument("--join-delay", type=float, default=0.0)
    sys.exit(asyncio.run(main(parser.parse_args())))
