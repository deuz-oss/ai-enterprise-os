# flashhead-server — SoulX-FlashHead di server GPU (PoC)

Renderer GPU untuk `avatar-worker` (`AVATAR_RENDERER=flashhead`). Isinya
model talking-head **SoulX-FlashHead 1.3B** dari repo dan checkpoint resmi:
- kode: [Soul-AILab/SoulX-FlashHead](https://github.com/Soul-AILab/SoulX-FlashHead), dikunci ke commit `9bc03de` (2026-05-28);
- bobot: [Soul-AILab/SoulX-FlashHead-1_3B](https://huggingface.co/Soul-AILab/SoulX-FlashHead-1_3B), revisi `5fbd2e4`;
- audio encoder: `facebook/wav2vec2-base-960h`, revisi `22aad52`.

> **CATATAN KEJUJURAN.** Service ini ditulis di mesin dev **tanpa GPU
> NVIDIA**. Image-nya **belum pernah dibangun, apalagi dijalankan**. Yang
> sudah diuji hanya klien di `avatar-worker` (terhadap server palsu dengan
> protokol yang sama) dan gerbang lisensi. Semua angka performa di bawah
> adalah **klaim README resmi**, belum diukur.

## Lisensi — hasil cek 2026-10-23

| Komponen | Lisensi | Komersial? |
|---|---|---|
| Kode repo | Apache-2.0 | ✅ |
| Bobot DiT FlashHead 1.3B | Apache-2.0 | ✅ |
| wav2vec2-base-960h | Apache-2.0 | ✅ |
| VAE Wan 2.1 — dipakai varian **pro** | Apache-2.0 | ✅ |
| VAE LTX-Video 0.9 — dipakai varian **lite** | RAIL-M Lightricks (22 Nov 2024) | ❌ "academic or research purposes only", komersialisasi dikecualikan eksplisit |

- **Varian lite memakai VAE LTX.** Diverifikasi di kode resmi
  `flash_head_pipeline.py`: `use_ltx = model_type == "lite"`, lalu bobot dimuat
  dari `VAE_LTX`.
- **Attachment A lisensi LTX** juga melarang impersonasi tanpa persetujuan
  (#8), keputusan otomatis yang merugikan hak seseorang (#9), dan diskriminasi
  dalam ketenagakerjaan (#15). Ini relevan untuk rekrutmen.
- **Ini bukan nasihat hukum.** Pastikan ke legal sebelum dipakai ke kandidat
  sungguhan.

**Keputusan (disetujui 2026-10-23):**
- Default **`pro`**.
- **`lite`** hanya jalan dengan `FLASHHEAD_ACK_NONCOMMERCIAL=1`, khusus untuk
  PoC/riset internal, **bukan** untuk kandidat sungguhan di produk komersial.
- Gerbang ada di `license_gate.py` dan dicek sebelum model dimuat.
- Untuk varian `pro`, bobot `VAE_LTX`/`Model_Lite` **tidak diunduh** sama sekali.

## Kebutuhan hardware & batas sesi paralel

Target: **1× NVIDIA RTX 4090 (24 GB)**, driver NVIDIA +
[nvidia-container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/),
dan ruang disk untuk image (CUDA devel + torch, belasan GB) serta bobot.

| Varian | Klaim README resmi (1× RTX 4090) | Konsekuensi di Aeos |
|---|---|---|
| `pro` (komersial OK) | 10,8 FPS, **tidak real-time** (real-time butuh 2× RTX 5090 + SageAttention) | antrean langsung tertinggal → `FlashHeadRenderer` turun ke StaticRenderer setelah `FLASHHEAD_MAX_BACKLOG` chunk. Di 1× 4090, praktis **tidak berguna untuk interview langsung** |
| `lite` (riset saja) | 96 FPS, atau **3 sesi paralel** real-time (25+ FPS) | `FLASHHEAD_MAX_SESSIONS=3` dan `AVATAR_MAX_SESSIONS=3` |

- **Server ini hanya single-GPU.** Mode multi-GPU resmi (Pro di 2× RTX 5090,
  `inference_script_multi_gpu_pro.sh`, `torchrun`) belum didukung.
- **Satu slot = satu instance pipeline.** Pipeline resmi menyimpan state per
  stream (gambar referensi, latent gerak, generator acak), jadi bobot dimuat
  `FLASHHEAD_MAX_SESSIONS` kali. Panggilan GPU diserialkan satu kunci.
  **Kebutuhan VRAM untuk 3 instance belum diukur.**
- **Samakan `AVATAR_MAX_SESSIONS` (worker) dengan `FLASHHEAD_MAX_SESSIONS`.**
  Kalau worker menerima lebih banyak, server menjawab `busy`, lalu worker
  menjawab 503 dan sesi itu jalan voice-only. Kandidat tidak ditolak.

## Menyalakan di server GPU

```
# .env
AVATAR_PROVIDER=self
AVATAR_RENDERER=flashhead
AVATAR_REFERENCE_IMAGE=/srv/avatar/reference.jpg   # file di ./deploy/avatar/ (lihat izin foto)
FLASHHEAD_MODEL_TYPE=pro          # atau lite + FLASHHEAD_ACK_NONCOMMERCIAL=1 (riset saja)
FLASHHEAD_MAX_SESSIONS=1
AVATAR_MAX_SESSIONS=1

docker compose --profile voice --profile avatar --profile avatar-gpu up -d --build
docker compose --profile avatar-gpu logs -f flashhead-server   # start pertama: unduh bobot + muat model
```

- **Build image** mengompilasi `flash_attn==2.8.0.post2` dari source untuk
  `TORCH_CUDA_ARCH_LIST=8.9` (RTX 4090). Untuk GPU lain, ubah build arg itu.
- **Bobot** diunduh ke volume `flashhead_models` pada start pertama
  (healthcheck memberi waktu 15 menit).
- **Saat server mati, belum siap, atau penuh**, sesi tetap jalan: voice-only,
  atau StaticRenderer kalau gagalnya terjadi di tengah sesi.
- Profile `avatar-gpu` **tidak** ikut `--profile voice` maupun `--profile avatar`.

Sebelum memakai `AVATAR_RENDERER=flashhead`, cek dulu `GET /health` dari
dalam jaringan compose. Isinya `model_type`, `free_slots`, dan `max_sessions`.

## Cara kerja (mengikuti repo resmi)

`server.py` berjalan **dari dalam checkout resmi** (config dibuka dengan path
relatif). Ia hanya memanggil fungsi resmi `flash_head.inference`:
`get_pipeline`, `get_base_data`, `get_infer_params`, `get_audio_embedding`,
dan `run_pipeline`. Urutannya meniru loop streaming `gradio_app_streaming.py`:
1. Deque audio 16 kHz sepanjang `cached_audio_duration` (8 dtk), diisi nol di
   awal.
2. Per potongan `frame_num − motion_frames_num` frame (33 − 5 = **28 frame ≈
   1,12 dtk** untuk VAE Wan), embedding dihitung pada jendela
   `[audio_end_idx − frame_num, audio_end_idx)`.
3. Hasilnya `video[motion_frames_num:]`.

Protokol WebSocket ke `avatar-worker` ada di docstring `server.py`. Frame
dikirim sebagai JPEG, 512×512, warna RGB seperti keluaran resmi.

**Latensi bawaan:** wajah baru bisa mulai bergerak setelah satu potongan
audio penuh terkumpul (≈ 1,12 dtk), ditambah waktu inferensi dan transfer.
AvatarRunner menahan audio sampai frame-nya siap, jadi **suara AI ikut
tertunda sebesar itu**. Saat AI diam, frame terakhir diulang (tidak ada
inferensi idle), sehingga wajah membeku saat diam.

## Belum teruji (wajib divalidasi di server GPU)

- Build image (CUDA devel + kompilasi flash_attn) dan start server.
- Kualitas lip-sync untuk **Bahasa Indonesia**. Bahasa data latih model
  tidak saya verifikasi. Contoh resmi memakai audio Mandarin
  (`podcast_sichuan_16k.wav`), dan encoder audio wav2vec2-base-960h dilatih
  pada LibriSpeech (bahasa Inggris).
- Latensi nyata dari ucapan sampai bibir bergerak, dan apakah turn-taking
  masih terasa wajar.
- FPS nyata per varian dan **jumlah sesi paralel nyata** + VRAM untuk N instance.
- `FLASHHEAD_FACE_CROP=1` (crop wajah resmi berbasis mediapipe) dengan foto Aeos.
- Perilaku `torch.compile` varian lite saat start (waktu kompilasi pertama).

## Versi dependensi

`requirements.lock` dibuat untuk Linux x86_64, Python 3.10, CUDA 12.8.
Basisnya `requirements.txt` resmi; gradio/flask dibuang karena tidak dipakai
server ini.

Requirements resmi saling bertabrakan: torch 2.7.1 mengunci
`nvidia-nccl-cu12==2.26.2`, sedangkan requirements.txt resmi meminta 2.27.3.
Urutan instal resmi (torch dulu, lalu requirements.txt via pip) berakhir di
2.27.3. `overrides.txt` mereproduksi hasil itu secara eksplisit. Regenerasi:

```
uv pip compile requirements.in --override overrides.txt --python-version 3.10 \
  --python-platform x86_64-manylinux_2_28 \
  --index-url https://download.pytorch.org/whl/cu128 --extra-index-url https://pypi.org/simple \
  --index-strategy unsafe-best-match -o requirements.lock
```

`flash_attn` tidak masuk lock karena butuh torch saat build. Versinya
dipasang terkunci di Dockerfile.
