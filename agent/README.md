# AI Interview Fase 2 — Voice Agent (self-hosted)

Percakapan suara real-time untuk AI Interview (lihat `docs/02-product/PRD.md`
§5 "Berikutnya" dan plan file kerja sesi ini). **Opt-in** — tidak start
dengan `docker compose up` biasa.

## Isi direktori

- `main.py` — worker LiveKit Agents (join room, jalankan STT→LLM→TTS,
  kirim transkrip ke backend saat selesai). Proses long-running pertama
  di codebase ini.
- `tts-server/` — wrapper OpenAI-compatible `/v1/audio/speech` di sekitar
  `facebook/mms-tts-ind` (Meta MMS, satu-satunya model TTS self-hosted
  yang benar-benar mendukung Bahasa Indonesia — **Kokoro TIDAK dipakai**,
  tidak dukung Indonesia sama sekali, lihat komentar di `tts-server/main.py`).

## Menjalankan

```
docker compose --profile voice up -d --build
```

Menyalakan 4 service tambahan: `livekit`, `stt-server` (faster-whisper,
image siap pakai), `tts-server` (dibangun dari repo ini), `ai-interview-agent`.

**Wajib diisi di `.env`** (lihat `.env.example`) sebelum service ini bisa
dipakai — `LIVEKIT_URL`/`LIVEKIT_API_KEY`/`LIVEKIT_API_SECRET`/
`STT_BASE_URL`/`TTS_BASE_URL`. Tanpa ini, endpoint backend
`POST /ai-interview/session/{token}/voice/start` sengaja memberi 503
(pola sama seperti `AI_BASE_URL` kosong).

LLM/reasoning **TIDAK** dikonfigurasi terpisah di sini — worker memakai
`AI_BASE_URL`/`AI_API_KEY`/`AI_MODEL` yang SAMA dengan backend (lihat
alasan di PRD §14 "Pengecualian khusus voice real-time").

## Keterbatasan yang jujur perlu diketahui (per 2026-09-02)

Ditulis di mesin dev **tanpa GPU NVIDIA** — jadi:

- Wiring (koneksi LiveKit, dispatch agent, panggilan REST ke backend,
  skema request/response OpenAI-compatible ke stt-server/tts-server) sudah
  diverifikasi benar terhadap SDK yang benar-benar ter-install (bukan
  tebakan dari dokumentasi saja).
- **Latensi percakapan nyata** dan **kualitas suara Bahasa Indonesia**
  dari `facebook/mms-tts-ind` **belum pernah diuji langsung** — CPU jauh
  lebih lambat dari real-time, tidak representatif. Validasi ulang wajib
  dilakukan begitu ada akses server ber-GPU, sebelum fitur ini dianggap
  siap dipakai kandidat sungguhan.
- Turn-taking/voice-activity-detection (kapan AI tahu kandidat selesai
  bicara) baru bisa dinilai "terasa natural atau tidak" lewat pengujian
  manusia dengan latensi asli — tidak bisa diverifikasi lewat automated
  test.

## Model TTS pertama kali start

`tts-server` mengunduh `facebook/mms-tts-ind` (~puluhan MB) dari
HuggingFace saat container pertama kali start — startup pertama lambat,
di-cache ke volume `tts_model_cache` untuk start berikutnya.
