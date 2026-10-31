# Scripts

Skrip operasional untuk deployment dan maintenance akan ditempatkan di sini
seiring kebutuhan. Saat ini seluruh operasi harian dilakukan lewat `Makefile`
di root repo (`make dev`, `make test`, `make lint`, dst).

## Benchmark validasi GPU

Dipakai oleh [runbook validasi GPU](../docs/04-engineering/gpu-validation-runbook.md)
(cara pakai, ambang lulus/gagal, dan rencana penurunan ada di sana). Kedua skrip
**tidak** mengubah perilaku produksi; keduanya hanya klien terhadap service yang
sudah berjalan.

| Skrip | Mengukur | Dependensi host |
|---|---|---|
| `bench_voice_latency.py` | per giliran: STT (faster-whisper), LLM TTFT, TTS TTFB, total; CSV + `.summary.json` p50/p95; exit 1 bila p95 STT > `--stt-p95-target-ms` (default 500) | `pip install httpx` |
| `bench_avatar.py` | flashhead-server via WebSocket `/stream`: fps, latensi frame pertama, backlog, VRAM (`nvidia-smi`), sesi paralel & `busy`; sesi default 10 menit | `pip install aiohttp numpy` |
| `bench_common.py` | persentil, CSV/JSON, evaluasi ambang, metadata GPU | – |

Metadata hasil mencatat GPU dari `nvidia-smi` mesin yang menjalankan skrip. Di
mesin tanpa GPU tercatat `none/CPU`, jadi angka CPU tidak tertukar dengan angka
GPU.

Uji: `python -m pytest scripts/tests -q`. Server palsu untuk mencoba
`bench_avatar.py` tanpa GPU:
`python scripts/tests/fake_flashhead.py --port 8010 --infer-ms 400 --max-sessions 3`
(angkanya tidak bermakna untuk performa).
