# AI Interview Fase 2 — Voice Agent (self-hosted STT + LiveKit)

Percakapan suara real-time untuk AI Interview (lihat `docs/02-product/PRD.md`
§5 "Berikutnya" dan plan file kerja sesi ini). **Opt-in** — tidak start
dengan `docker compose up` biasa.

## Isi direktori

- `main.py` — worker LiveKit Agents (join room, jalankan STT→LLM→TTS,
  kirim transkrip ke backend saat selesai). Proses long-running pertama
  di codebase ini.

STT (`faster-whisper`, image `fedirz/faster-whisper-server` siap pakai,
lihat `docker-compose.yml`) dan LLM (`AI_BASE_URL` yang sama dipakai
fitur teks lain) self-hosted/reuse. **TTS TIDAK self-hosted** —
`facebook/mms-tts-ind` dicoba lebih dulu (wrapper FastAPI custom di
`tts-server/`, sekarang sudah dihapus) tapi kualitas suaranya dinilai
jelek setelah didengar langsung, jadi diganti TTS OpenAI
(`gpt-4o-mini-tts`, lewat `AI_BASE_URL`/`AI_API_KEY` yang sama dengan
LLM) — lihat catatan lengkap di docstring `main.py`.

## Menjalankan

```
docker compose --profile voice up -d --build
```

Menyalakan 3 service tambahan: `livekit`, `stt-server` (faster-whisper,
image siap pakai), `ai-interview-agent` (dibangun dari repo ini).

**Wajib diisi di `.env`** (lihat `.env.example`) sebelum service ini bisa
dipakai — `LIVEKIT_URL`/`LIVEKIT_API_KEY`/`LIVEKIT_API_SECRET`/
`STT_BASE_URL`, plus `AI_BASE_URL`/`AI_API_KEY` (dipakai juga untuk TTS).
Tanpa ini, endpoint backend `POST /ai-interview/session/{token}/voice/start`
sengaja memberi 503 (pola sama seperti `AI_BASE_URL` kosong).

`AI_TTS_MODEL`/`AI_TTS_VOICE` opsional (default `gpt-4o-mini-tts`/`ash`
kalau kosong).

## Keterbatasan yang jujur perlu diketahui (per 2026-09-02)

Ditulis di mesin dev **tanpa GPU NVIDIA** — jadi:

- Wiring (koneksi LiveKit, dispatch agent, panggilan REST ke backend,
  sesi WebRTC nyata, sintesis TTS) sudah diverifikasi jalan lewat
  `docker compose --profile voice up` sungguhan — bukan cuma build image.
- **Latensi percakapan nyata** dengan STT self-hosted di CPU **belum
  pernah diuji** — CPU jauh lebih lambat dari real-time, tidak
  representatif. Validasi ulang wajib dilakukan begitu ada akses server
  ber-GPU, sebelum fitur ini dianggap siap dipakai kandidat sungguhan.
- Turn-taking/voice-activity-detection (kapan AI tahu kandidat selesai
  bicara) baru bisa dinilai "terasa natural atau tidak" lewat pengujian
  manusia dengan latensi asli — tidak bisa diverifikasi lewat automated
  test.
- Kualitas suara TTS OpenAI untuk Bahasa Indonesia sudah bisa dinilai
  manusia (bukan cuma dugaan) karena tidak butuh GPU untuk didengar —
  jauh lebih baik dari percobaan self-hosted sebelumnya.
