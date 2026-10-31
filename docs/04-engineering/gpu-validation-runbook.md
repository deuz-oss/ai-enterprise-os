# Runbook Validasi GPU — Interview Suara (Fase 30) & PoC Avatar (Fase 67)

Runbook untuk **satu** server GPU NVIDIA sewaan. Tujuannya mengukur untuk
pertama kali hal yang sampai hari ini hanya diklaim:

- **Fase 30** (PRD §"Fase 30"): interview suara real-time = LiveKit +
  faster-whisper (STT, GPU) + LLM OpenAI + TTS OpenAI `gpt-4o-mini-tts`.
- **Fase 67** (PRD §"Fase 67", `flashhead-server/README.md`,
  `avatar-worker/README.md`): wajah video pewawancara lewat SoulX-FlashHead.

> **CATATAN KEJUJURAN.** Runbook ini ditulis di mesin dev Windows **tanpa GPU
> NVIDIA**. Belum ada satu langkah pun yang dijalankan di server GPU. Perintah
> di bawah disusun dari isi file compose, Dockerfile, dan kode di repo (dicek
> 2026-10-30), bukan dari pengalaman menjalankannya. **Semua angka performa
> yang dikutip adalah klaim** (README resmi SoulX-FlashHead, komentar di
> compose/DEPLOYMENT.md) **atau perkiraan** dan ditandai begitu. Penandaan
> yang dipakai:
>
> - **[sumber: …]**: angka dari file/dokumen yang disebut.
> - **[perkiraan]**: tebakan teknis saya, belum diukur. Ganti dengan angka nyata
>   setelah validasi.
> - **[usulan]**: ambang lulus/gagal yang saya usulkan, bukan dari pengguna.
> - **[dari brief]**: ambang yang diminta pengguna.

Runbook ini **tidak mengubah perilaku produksi**. Tidak ada file compose,
Dockerfile, kode, atau `.env.example` yang diubah. Tidak ada file compose baru:
semua yang dibutuhkan bisa dicapai dengan menggabungkan file yang sudah ada
(lihat [§2](#2-temuan-konfigurasi-baca-sebelum-menyewa)).

---

## 0. Ringkasan alur

| Urutan | Jalur | File compose | Yang divalidasi | Perkiraan waktu |
|---|---|---|---|---|
| 1 | **A — suara saja, jalur produksi** | `docker-compose.prod.yml` + `docker-compose.prod.gpu.yml`, `--profile voice` | override GPU produksi (belum pernah dijalankan), latensi STT/LLM/TTS, E2E mikrofon dari HP via data seluler | 2–3 jam [perkiraan] |
| 2 | **B — suara + avatar** | `docker-compose.yml` + `docker-compose.prod.gpu.yml`, `--profile voice --profile avatar --profile avatar-gpu` | build flashhead-server (pertama kali), fps/VRAM/sesi paralel, lip-sync Bahasa Indonesia, STT saat GPU dipakai bersama | 3–5 jam, termasuk build 1–2 jam [perkiraan] |

Kedua jalur **tidak bisa jalan bersamaan** di satu server, karena keduanya
mempublikasikan port `7881/tcp` (LiveKit). Matikan jalur A (`down`, tanpa
`-v`) sebelum memulai jalur B.

---

## 1. Spesifikasi server

### 1.1 GPU

| Kebutuhan | Minimum | Disarankan | Dasar |
|---|---|---|---|
| Suara saja (whisper `large-v3` float16) | GPU NVIDIA ≥ 8 GB VRAM dengan dukungan float16 (Turing/T4 ke atas) | 16–24 GB | VRAM large-v3 float16 ≈ 3–5 GB [perkiraan, dari ukuran model CTranslate2 ± aktivasi]; sisanya cadangan |
| Suara + avatar (FlashHead) | **1× RTX 4090 24 GB** atau GPU Ampere/Ada/Hopper ≥ 24 GB | 1× RTX 4090 24 GB (target README) | [sumber: `flashhead-server/README.md`] target 1× RTX 4090 24 GB. flash_attn 2 butuh arsitektur ≥ sm_80, jadi **T4 (sm_75) dan V100 (sm_70) tidak bisa** untuk avatar |

Catatan pemilihan GPU:

- **Klaim fps README resmi hanya untuk RTX 4090** [sumber:
  `flashhead-server/README.md`]: `pro` 10,8 FPS (tidak real-time), `lite` 96
  FPS / 3 sesi paralel ≥ 25 FPS. Di GPU lain (L4, A10, A100, H100) angka itu
  **tidak berlaku**. L4 se-arsitektur dengan 4090 (Ada, 8.9) tapi jauh lebih
  hemat daya, jadi kemungkinan lebih lambat [perkiraan].
- Kalau hanya bisa menyewa satu jenis GPU, pilih **RTX 4090 24 GB**, karena
  hanya di GPU itu hasilnya bisa dibandingkan dengan klaim README.
- `flashhead-server` hanya **single-GPU**. Mode resmi 2× RTX 5090 belum
  didukung [sumber: `flashhead-server/README.md`]. Menyewa 2 GPU tidak
  membantu.

**`TORCH_CUDA_ARCH_LIST` untuk build flashhead-server.** Default Dockerfile
`8.9` = RTX 4090. Nilai untuk GPU lain [sumber: tabel compute capability
NVIDIA, cek ulang di developer.nvidia.com/cuda-gpus]:

| GPU | Arsitektur | `TORCH_CUDA_ARCH_LIST` | Bisa untuk FlashHead? |
|---|---|---|---|
| RTX 4090, L4, L40S, RTX 6000 Ada | Ada | `8.9` | ya (default) |
| A10 / A10G, RTX 3090, A40 | Ampere GA10x | `8.6` | ya |
| A100 | Ampere GA100 | `8.0` | ya |
| H100 / H200 | Hopper | `9.0` | ya |
| RTX 5090 / Blackwell | Blackwell | `12.0` (5090) | **tidak diketahui**: dukungan flash_attn 2.8.0.post2 untuk sm_120 belum saya verifikasi |
| T4 | Turing | `7.5` | **tidak** (flash_attn 2 butuh ≥ sm_80); masih bisa untuk STT saja |

Cara override **tanpa mengubah file** ada di [§3.5](#35-jalur-b--suara--avatar).

### 1.2 CPU, RAM, disk

| Komponen | Minimum | Disarankan | Dasar |
|---|---|---|---|
| vCPU | 8 | 16+ | build flash_attn di Dockerfile memakai `MAX_JOBS=4` [sumber: `flashhead-server/Dockerfile`]; agen (VAD Silero + turn detector), avatar-worker (encode video), backend, Postgres, dan LiveKit **berjalan di CPU**, bukan di GPU |
| RAM | 32 GB | 64 GB | kompilasi CUDA flash_attn dengan 4 job paralel bisa memakan beberapa GB per job [perkiraan]; ditambah stack aplikasi |
| Disk | 150 GB | 200 GB SSD/NVMe | image CUDA devel + torch cu128 untuk flashhead-server ≈ 20–30 GB [perkiraan]; cache build Docker belasan GB [perkiraan]; bobot FlashHead + wav2vec2 "beberapa GB" [sumber: komentar `docker-compose.yml`]; whisper large-v3 ≈ 3 GB [perkiraan]; image lain (fedirz CUDA, backend, frontend, agen) ≈ 10–15 GB [perkiraan] |

### 1.3 OS, driver, CUDA

| Item | Nilai | Dasar |
|---|---|---|
| OS | Ubuntu 22.04 atau 24.04 LTS, **VM atau bare metal** (bukan container) | `deploy/setup-vps.sh` menolak selain Ubuntu |
| Driver NVIDIA | **≥ 570** (cabang yang mendukung CUDA 12.8) | `flashhead-server/Dockerfile` memakai `nvidia/cuda:12.8.1-cudnn-devel-ubuntu22.04` dan torch `cu128`. CUDA 12.8 butuh driver Linux ≥ 570.26 [sumber: CUDA Toolkit Release Notes NVIDIA, cek ulang] |
| CUDA di host | tidak perlu toolkit; cukup driver | CUDA ada di dalam image |
| NVIDIA Container Toolkit | wajib, dan runtime Docker dikonfigurasi (`nvidia-ctk runtime configure`) | `deploy.resources.reservations.devices` di `docker-compose.prod.gpu.yml` dan `docker-compose.yml` |
| Docker Engine + plugin compose v2 | wajib | `deploy/setup-vps.sh` memasangnya dari repo resmi Docker |

**Image STT tidak dikunci.** `fedirz/faster-whisper-server:latest-cuda` memakai
tag `latest`, jadi versi CUDA di dalamnya bisa berubah kapan saja. Catat
digest dan versi CUDA-nya setelah pull (perintahnya di [§3.4](#34-jalur-a--suara-saja-jalur-produksi)).

### 1.4 Port jaringan

Media WebRTC **harus** bisa masuk langsung lewat UDP ke IP publik server,
dengan nomor port yang sama (tanpa remap port).

**Jalur A (produksi)** [sumber: `docker-compose.prod.yml`, `deploy/livekit.yaml`,
`docs/DEPLOYMENT.md` §5b]:

| Port | Protokol | Fungsi |
|---|---|---|
| 22 (atau port SSH penyedia) | TCP | SSH |
| 80, 443 | TCP | Caddy (TLS otomatis, situs + `livekit.<DOMAIN>` + `files.<DOMAIN>`) |
| 7881 | TCP | WebRTC cadangan bila UDP diblokir |
| 50000–50100 | UDP | media WebRTC |
| 3478 | UDP | TURN |
| 40000–40100 | UDP | relai TURN |

**Jalur B (compose dev)** [sumber: `docker-compose.yml`]:

| Port | Protokol | Buka ke internet? |
|---|---|---|
| 22 | TCP | ya |
| 7881 | TCP | ya (WebRTC cadangan) |
| 51000–51020 | UDP | ya (media WebRTC; hanya 21 port, cukup untuk beberapa sesi) |
| 3000, 8000, 7880, 9000 | TCP | **JANGAN.** Akses lewat tunnel SSH ([§3.5](#35-jalur-b--suara--avatar)). `docker-compose.yml` mempublikasikan 3000, 8000, dan 7880 ke `0.0.0.0`, dan Docker melewati ufw, jadi **firewall penyedia (security group) wajib menutupnya** |

### 1.5 Jebakan penyedia sewa GPU — syarat yang wajib diminta

Banyak penawaran GPU murah berbentuk **container** (kita mendapat shell di
dalam container milik penyedia), bukan VM. Di lingkungan seperti itu stack ini
**tidak bisa jalan**. Sebelum membayar, pastikan:

1. **VM atau bare metal dengan akses root**, dan bisa memasang Docker Engine
   sendiri. Container tanpa Docker-in-Docker tidak bisa menjalankan
   `docker compose`.
2. **IP publik IPv4 statis milik instance**, dengan port masuk **UDP** yang
   bisa dibuka sesuai nomor di §1.4. Penyedia yang hanya meneruskan
   HTTP/TCP lewat proxy, atau meremap port ke nomor acak, mematahkan
   LiveKit: browser kandidat tidak pernah tersambung (pelajaran uji
   2026-09-26, [sumber: komentar `deploy/livekit.yaml`]).
3. **Firewall/security group yang bisa diatur sendiri.**
4. Driver NVIDIA ≥ 570 sudah terpasang atau boleh dipasang sendiri.
5. Disk ≥ 150 GB yang **ikut terhapus** saat instance dihancurkan.
6. Pusat data: rekaman suara uji adalah data biometrik (UU PDP). Pakai suara
   sendiri/sintetis saja ([§4.1](#41-data-uji)); lokasi pusat data kurang
   penting selama tidak ada data kandidat sungguhan. Untuk latensi
   LLM/TTS OpenAI yang realistis bagi kandidat Indonesia, region Asia
   Tenggara lebih representatif [perkiraan].

Contoh kategori yang **biasanya** memenuhi syarat (cek ulang, belum saya
verifikasi per penyedia): instance GPU VM di cloud besar (mis. AWS
`g6`/L4, `g5`/A10G; GCP `g2`/L4) atau server GPU dedicated/bare metal.
Marketplace GPU berbasis container sering gagal di syarat 1 dan 2. Tanyakan
secara eksplisit: *"apakah saya dapat VM dengan Docker dan port UDP inbound
50000–50100 pada IP publik?"*

**Jebakan ufw.** `deploy/setup-vps.sh` menjalankan `ufw allow OpenSSH`
(port 22) lalu `ufw --force enable`. Kalau SSH penyedia **bukan di port 22**,
koneksi SSH Anda **terkunci**. Cek dulu `ss -tlnp | grep sshd`; kalau bukan
22, jalankan `ufw allow <port>/tcp` sebelum skrip.

---

## 2. Temuan konfigurasi (baca sebelum menyewa)

Hasil pengecekan repo per 2026-10-30. Celah ini **tidak** saya perbaiki,
karena tugasnya hanya menulis runbook.

1. **`docker-compose.prod.gpu.yml` hanya meng-override `stt-server`**:
   image `latest-cuda`, `WHISPER__COMPUTE_TYPE` default `float16`, dan
   reservasi 1 GPU. Komentarnya sendiri menyatakan "belum diuji di mesin GPU".
2. **Avatar tidak ada di jalur produksi.** Service `avatar-worker` (profile
   `avatar`) dan `flashhead-server` (profile `avatar-gpu`) **hanya ada di
   `docker-compose.yml`**, tidak ada di `docker-compose.prod.yml`. Akibatnya:
   - `--profile avatar` / `--profile avatar-gpu` dengan file prod **tidak
     menyalakan apa pun**;
   - kalau `.env.production` berisi `AVATAR_PROVIDER=self`, agen produksi
     memanggil `http://avatar-worker:8090` (default `AVATAR_WORKER_URL` di
     `agent/avatar_fallback.py`) yang tidak ada, lalu jatuh ke voice-only
     setelah batas koneksi 3 dtk. Tidak rusak, tapi juga tidak menguji
     apa-apa.

   Karena itu validasi avatar (jalur B) memakai `docker-compose.yml` (stack
   dev: tanpa Caddy/TLS, LiveKit `--dev` tanpa TURN), digabung dengan
   override GPU produksi untuk STT. **Hasil jalur B membuktikan model dan
   wiring di GPU, bukan kesiapan deploy avatar ke produksi.** Itu butuh
   pekerjaan compose terpisah setelah validasi.
3. **Override GPU bisa dipakai dengan compose dev.** `docker-compose.prod.gpu.yml`
   hanya menyentuh `stt-server`, yang juga ada (dengan profile `voice`) di
   `docker-compose.yml`, jadi
   `docker compose -f docker-compose.yml -f docker-compose.prod.gpu.yml …`
   menggabungkannya dengan benar. Ini alasan **tidak perlu** file
   `docker-compose.gpu-validation.yml` baru. Verifikasi hasil penggabungannya
   dengan `docker compose … config` sebelum `up` (§3.5).
4. **Port service internal tidak dipublikasikan.** `stt-server` di prod
   tidak punya `ports`, sedangkan `flashhead-server` di dev juga tidak. Skrip
   benchmark yang jalan di host menjangkaunya lewat IP container di jaringan
   bridge Docker (§4). Ini hanya jalan di Linux, tidak di Docker Desktop.
5. **Tuning agen hanya bisa di jalur A.** Di prod, agen membaca
   `env_file: .env.production`, sehingga `VAD_MIN_SILENCE`,
   `ENDPOINTING_MIN_DELAY`, `ENDPOINTING_MAX_DELAY`, `STT_TIMEOUT_SEC`, dan
   `STT_LANGUAGE` ikut terbaca. Di compose dev, agen hanya menerima daftar
   `environment` eksplisit, dan variabel-variabel itu **tidak ada** di daftar
   tersebut. Hal yang sama berlaku untuk avatar-worker (`FLASHHEAD_CHUNK_TIMEOUT`,
   `FLASHHEAD_MAX_BACKLOG`, `FLASHHEAD_READY_TIMEOUT`, `AVATAR_START_TIMEOUT`):
   di jalur B semuanya memakai default kode.
6. **Klaim "jeda ~1–2 dtk di GPU"** (komentar `docker-compose.prod.gpu.yml`,
   `docs/DEPLOYMENT.md`) belum pernah diukur. Konfigurasi agen sendiri sudah
   menambah jeda sebelum agen mulai memproses: `VAD_MIN_SILENCE=1.2` dtk +
   `ENDPOINTING_MIN_DELAY=1.0` dtk [sumber: `agent/main.py`]. Jadi jeda yang
   **dirasakan** kandidat kemungkinan ≥ ~2,2 dtk ditambah STT + LLM TTFT +
   TTS TTFB, walaupun STT-nya cepat [perkiraan dari konfigurasi]. Uji E2E
   (§5) harus mengukur jeda yang dirasakan, bukan hanya angka skrip.
7. **`up --build` membatalkan build-arg custom.** Kalau flashhead-server
   dibangun dengan `--build-arg TORCH_CUDA_ARCH_LIST=…`, perintah
   `up --build` setelahnya akan membangun ulang dengan default `8.9`. Pakai
   `up` **tanpa** `--build` untuk service itu (§3.5).
8. **Dua service berbagi satu GPU.** `stt-server` dan `flashhead-server`
   sama-sama mereservasi `count: 1`. Di server 1 GPU keduanya memakai GPU 0
   yang sama. Reservasi compose tidak eksklusif dan tidak membatasi VRAM.
   Karena itu benchmark STT perlu diulang saat avatar aktif (§4.4).

---

## 3. Langkah deploy

### 3.1 Siapkan host

```bash
# Di server, sebagai root (sudo -i). Ubuntu 22.04/24.04.
nvidia-smi                       # driver sudah ada? catat versi driver & "CUDA Version"
# Kalau belum ada / < 570: pasang driver dari repo penyedia/NVIDIA, reboot, cek ulang.

# Docker Engine (kalau tidak memakai setup-vps.sh di jalur A):
curl -fsSL https://get.docker.com | sh

# NVIDIA Container Toolkit (ikuti docs.nvidia.com/datacenter/cloud-native/container-toolkit/
# bagian "Installing with Apt"), lalu:
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

df -h /var/lib/docker            # pastikan >= 150 GB kosong
nproc; free -g
```

### 3.2 Verifikasi GPU di dalam Docker

```bash
# Tag CUDA sama dengan basis flashhead-server (12.8.1). Kalau tag ini gagal di-pull,
# pakai tag 12.8.x-base-ubuntu22.04 lain yang ada di Docker Hub.
docker run --rm --gpus all nvidia/cuda:12.8.1-base-ubuntu22.04 nvidia-smi
```

Lulus = tabel GPU tampil dari dalam container. Kalau muncul
`could not select device driver "" with capabilities: [[gpu]]`, berarti
toolkit/runtime belum terkonfigurasi (ulangi §3.1). **Jangan lanjut sebelum
langkah ini lulus.**

### 3.3 Clone & identitas run

```bash
git clone https://github.com/deuz-oss/ai-enterprise-os.git /opt/aeos   # repo privat: deploy key
cd /opt/aeos
git rev-parse HEAD                    # catat di hasil
mkdir -p /root/gpu-results            # tempat semua CSV/log run ini (di luar repo)
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv | tee /root/gpu-results/gpu.csv
```

### 3.4 Jalur A — suara saja, jalur produksi

**DNS.** Stack prod butuh `DOMAIN` dengan TLS (Caddy) karena mikrofon browser
hanya aktif di HTTPS. Ada dua pilihan:

- subdomain milik sendiri, mis. `gpu-test.<domain-anda>`, dengan record A
  untuk `gpu-test…`, `files.gpu-test…`, dan `livekit.gpu-test…` → IP server;
- tanpa domain: `DOMAIN=<ip-dengan-strip>.sslip.io` (mis. `203-0-113-5.sslip.io`).
  sslip.io me-resolve subdomain apa pun ke IP yang tertulis di namanya, jadi
  `files.` dan `livekit.` ikut jalan. **Belum dicoba di proyek ini.** Kalau
  Let's Encrypt menolak (rate limit), pakai pilihan pertama.

**Pasang stack** dengan skrip resmi (`docs/DEPLOYMENT.md` §5):

```bash
# Cek port SSH dulu (jebakan ufw, §1.5)!
sudo bash deploy/setup-vps.sh
#   Domain: <DOMAIN di atas>
#   Aktifkan interview suara? y
#   Server punya GPU NVIDIA + NVIDIA Container Toolkit? y
```

Skrip membuat `.env.production` dengan secret acak, lalu menjalankan
`docker compose -f docker-compose.prod.yml -f docker-compose.prod.gpu.yml --env-file .env.production --profile voice up -d --build`.

**Lengkapi `.env.production`** (`chmod 600` sudah diatur skrip):

```dotenv
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=<kunci KHUSUS uji ini, dengan batas belanja; dicabut saat teardown>
AI_AGENT_MODEL=gpt-4.1-mini            # saran docs/DEPLOYMENT.md
STT_MODEL=Systran/faster-whisper-large-v3
STT_COMPUTE_TYPE=float16
STT_LOG_STATS=1                        # statistik per segmen (angka saja) untuk kalibrasi
# STT_NO_SPEECH_THRESHOLD kosong = 0.6, dikalibrasi untuk model `small`.
# Untuk large-v3 ambang ini BELUM dikalibrasi; biarkan default selama uji, lalu
# kumpulkan statistiknya dari log (STT_LOG_STATS=1).
AVATAR_PROVIDER=none                   # jalur A = voice-only (lihat §2 butir 2)
```

`STT_MODEL` dibaca dua kali: oleh `stt-server` (interpolasi compose dari
`--env-file`) dan oleh agen/backend (`env_file`). Karena itu **selalu**
sertakan `--env-file .env.production`.

```bash
cd /opt/aeos
C="docker compose -f docker-compose.prod.yml -f docker-compose.prod.gpu.yml --env-file .env.production --profile voice"
$C config | grep -A6 'stt-server:'      # harus: image ...:latest-cuda, WHISPER__COMPUTE_TYPE float16, devices nvidia
$C up -d --build
$C ps                                    # semua healthy / running
```

**Health check & log:**

```bash
$C logs livekit | grep "starting LiveKit"            # nodeIP = IP publik server
$C logs ai-interview-agent | grep "registered worker"
$C logs stt-server | tail -50                         # cari baris yang menyebut CUDA/device
$C exec stt-server nvidia-smi                         # GPU terlihat dari dalam container
docker image inspect fedirz/faster-whisper-server:latest-cuda \
  --format '{{index .RepoDigests 0}} {{range .Config.Env}}{{println .}}{{end}}' \
  | grep -E 'sha256|CUDA_VERSION' | tee /root/gpu-results/stt-image.txt
curl -fsS https://$DOMAIN/api/v1/health/live || curl -fsS https://<DOMAIN>/api/v1/health/live
```

**Unduhan model pertama.** faster-whisper-server mengunduh model saat
transkripsi pertama ke volume `stt_model_cache` [sumber: `docs/DEPLOYMENT.md`].
large-v3 berukuran ≈ 3 GB [perkiraan]. Panaskan dulu dengan satu request
sebelum benchmark, supaya waktu unduh tidak masuk ke angka latensi:

```bash
STT_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $($C ps -q stt-server))
curl -fsS http://$STT_IP:8000/health
# Request pemanasan (file wav pendek apa saja; tunggu sampai selesai, bisa beberapa menit):
curl -fsS http://$STT_IP:8000/v1/audio/transcriptions \
  -F file=@/path/ke/sampel.wav -F model=Systran/faster-whisper-large-v3 -F language=id
$C exec stt-server nvidia-smi        # VRAM terpakai setelah model dimuat -> catat
```

### 3.5 Jalur B — suara + avatar

```bash
cd /opt/aeos
docker compose -f docker-compose.prod.yml -f docker-compose.prod.gpu.yml --env-file .env.production --profile voice down
# (tanpa -v: data jalur A tetap ada kalau perlu kembali)
```

**`.env` di root repo** (compose dev memakai `.env` untuk interpolasi
**dan** `env_file` backend):

```bash
cp .env.example .env && chmod 600 .env
```

Lalu isi/ubah:

```dotenv
SECRET_KEY=<python3 -c "import secrets;print(secrets.token_hex(32))">
ADMIN_EMAIL=<email uji>
ADMIN_PASSWORD=<acak kuat>
POSTGRES_PASSWORD=<acak>
APP_DB_PASSWORD=<acak>
STORAGE_SECRET_KEY=<acak>
AI_BASE_URL=https://api.openai.com/v1
AI_API_KEY=<kunci uji yang sama>
AI_AGENT_MODEL=gpt-4.1-mini
LIVEKIT_URL=ws://livekit:7880
LIVEKIT_API_KEY=aeos<acak>
LIVEKIT_API_SECRET=<acak, >= 32 karakter>
LIVEKIT_NODE_IP=<IP publik server>     # WAJIB; default 127.0.0.1 hanya untuk dev lokal
STT_BASE_URL=http://stt-server:8000/v1
STT_MODEL=Systran/faster-whisper-large-v3
STT_COMPUTE_TYPE=float16               # tulis eksplisit; default compose dev = int8
STT_LOG_STATS=1
AVATAR_PROVIDER=self
AVATAR_RENDERER=flashhead
AVATAR_REFERENCE_IMAGE=/srv/avatar/reference.jpg
FLASHHEAD_MODEL_TYPE=pro               # mulai dari pro (komersial OK). lite: lihat §7
FLASHHEAD_ACK_NONCOMMERCIAL=
FLASHHEAD_MAX_SESSIONS=1
AVATAR_MAX_SESSIONS=1                  # SELALU sama dengan FLASHHEAD_MAX_SESSIONS
```

**Foto referensi.** FlashHead wajib foto. Taruh di
`deploy/avatar/reference.jpg`. Pakai **foto penguji sendiri** atau foto
dengan izin tertulis dari orangnya [sumber: `avatar-worker/README.md`].
Hapus saat teardown.

```bash
scp reference.jpg root@<server>:/opt/aeos/deploy/avatar/reference.jpg   # dari laptop
```

**Build flashhead-server** (pertama kali dalam sejarah proyek ini):

```bash
B="docker compose -f docker-compose.yml -f docker-compose.prod.gpu.yml --profile voice --profile avatar --profile avatar-gpu"
$B config | grep -A6 'stt-server:'      # harus latest-cuda + float16 + devices nvidia

# RTX 4090 / L4 / L40S: default 8.9, cukup:
time $B build flashhead-server 2>&1 | tee /root/gpu-results/flashhead-build.log
# GPU lain: override build-arg TANPA mengubah file (nilai di §1.1), mis. A100:
#   time $B build --build-arg TORCH_CUDA_ARCH_LIST=8.0 flashhead-server 2>&1 | tee ...
```

- Waktu build: kompilasi `flash_attn==2.8.0.post2` dari source dengan
  `MAX_JOBS=4` untuk satu arsitektur, **sekitar 30 menit hingga 2 jam**
  [perkiraan; sangat bergantung jumlah core]. Catat angka nyata dari `time`.
- Kalau build mati karena kehabisan RAM (`Killed`, `c++: fatal error`),
  RAM-nya kurang. `MAX_JOBS` tertanam di Dockerfile. Menurunkannya berarti
  mengubah Dockerfile, yang **di luar cakupan runbook ini**: catat sebagai
  temuan, lalu pakai server dengan RAM lebih besar.
- `docker system df` setelah build: catat ukuran image.

**Jalankan** (tanpa `--build` untuk flashhead-server kalau tadi memakai
build-arg custom, §2 butir 7):

```bash
$B build backend frontend ai-interview-agent avatar-worker
$B up -d
$B ps
$B logs -f flashhead-server        # start pertama: gerbang lisensi -> unduh bobot -> muat model
```

Start pertama mengunduh bobot ke volume `flashhead_models`. Healthcheck
memberi `start_period` 900 dtk [sumber: `docker-compose.yml`]. Kalau
`LicenseError` muncul, berarti `FLASHHEAD_MODEL_TYPE=lite` tanpa
`FLASHHEAD_ACK_NONCOMMERCIAL=1`. Itu perilaku yang benar.

```bash
FH_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $($B ps -q flashhead-server))
AW_IP=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $($B ps -q avatar-worker))
curl -fsS http://$FH_IP:8010/health   # {"model_type":"pro","free_slots":1,"max_sessions":1}
curl -fsS http://$AW_IP:8090/health   # {"renderer":"flashhead","active":0,"max_sessions":1}
nvidia-smi                            # VRAM setelah STT + FlashHead dimuat -> catat
du -sh /var/lib/docker/volumes/*flashhead_models*   # ukuran bobot nyata -> catat
```

**Akses dari laptop (tunnel SSH).** Frontend dev dibangun dengan
`VITE_API_URL=http://localhost:8000/api/v1`, dan default `LIVEKIT_PUBLIC_URL`
adalah `ws://localhost:7880`. Browser juga hanya mengizinkan mikrofon di
HTTPS atau `localhost`. Karena itu buka lewat tunnel:

```bash
# Di laptop:
ssh -N -L 3000:localhost:3000 -L 8000:localhost:8000 -L 7880:localhost:7880 -L 9000:localhost:9000 root@<server>
# lalu buka http://localhost:3000
```

Sinyal LiveKit lewat tunnel, sedangkan **media WebRTC langsung** ke
`<LIVEKIT_NODE_IP>:51000-51020/udp` (atau `7881/tcp`). Port-port itu harus
terbuka di firewall penyedia.

---

## 4. Benchmark

### 4.1 Data uji

- Pakai **audio sintetis** (`--generate-samples`) atau **suara penguji
  sendiri**. Jangan memakai rekaman kandidat sungguhan: itu data biometrik
  (UU PDP) dan tidak boleh disalin ke server sewaan.
- Simpan semua keluaran di `/root/gpu-results/` (di luar checkout repo).

### 4.2 Latensi suara — `scripts/bench_voice_latency.py`

Mengukur per giliran: STT, LLM TTFT, TTS TTFB, dan total, lalu menulis CSV
serta ringkasan p50/p95 (`<out>.summary.json`). Definisi `total_ms` = STT +
LLM TTFT + TTS TTFB, yaitu latensi pipeline sampai byte audio pertama, **tanpa**
VAD/endpointing dan transport WebRTC (lihat docstring skrip). Dependensi di
host: `pip install httpx`.

`--generate-samples` menyintesis 8 jawaban kandidat Bahasa Indonesia lewat TTS
(beserta teks referensinya untuk WER). Audio TTS lebih bersih dari mikrofon
sungguhan, jadi angka STT dari sampel ini **optimistis**. Tambahkan beberapa
rekaman suara penguji sendiri (`*.wav` + `*.txt` berisi teks yang dibacakan)
ke folder yang sama.

```bash
cd /opt/aeos
pip install httpx
python3 scripts/bench_voice_latency.py --help     # daftar flag lengkap

# 1) STT saja (bagian yang diuntungkan GPU), sampel dibuat sekali (butuh kunci TTS):
python3 scripts/bench_voice_latency.py --env-file .env.production \
  --stt-url http://$STT_IP:8000/v1 \
  --samples-dir /root/gpu-results/samples --generate-samples \
  --skip-llm --skip-tts --repeats 5 --warmup 2 \
  --stt-p95-target-ms 500 --max-error-rate 0 \
  --stt-compute-type float16 --stt-device "cuda <nama GPU>" \
  --label "large-v3 fp16" \
  --out /root/gpu-results/voice-stt-large-v3-fp16.csv

# 2) Pipeline lengkap (STT + LLM TTFT + TTS TTFB), ambang [usulan] §6.1:
python3 scripts/bench_voice_latency.py --env-file .env.production \
  --stt-url http://$STT_IP:8000/v1 \
  --samples-dir /root/gpu-results/samples --repeats 3 --warmup 2 \
  --stt-p95-target-ms 500 --max-error-rate 0.01 \
  --llm-ttft-p95-target-ms 1500 --tts-ttfb-p95-target-ms 1000 \
  --total-p95-target-ms 2500 \
  --label "large-v3 fp16 full" \
  --out /root/gpu-results/voice-full-large-v3-fp16.csv
```

- **Exit code** 0 = semua ambang yang diberikan lulus, 1 = ada yang gagal.
  Default `--max-error-rate` di skrip 0.05. Runbook memakai 0 (STT saja) dan
  0.01 (lengkap) sesuai §6.1.
- **Endpoint STT.** `--stt-url` (atau env `STT_BASE_URL`). `stt-server`
  tidak dipublikasikan di jalur A, jadi skrip di host memakai
  `http://$STT_IP:8000/v1` (§3.4). Di jalur B tersedia juga di
  `http://127.0.0.1:8001/v1`.
- **Kunci & model LLM/TTS** dibaca dari env yang sama dengan agen
  (`AI_BASE_URL`, `AI_API_KEY`, `AI_AGENT_MODEL`/`AI_MODEL`, `AI_TTS_MODEL`,
  `AI_TTS_VOICE`). `--env-file` memuatnya tanpa menaruh kunci di riwayat
  shell (jalur A: `.env.production`, jalur B: `.env`). Secara default LLM
  dipanggil dengan tool agen, seperti di sesi nyata (`--llm-no-tools` untuk
  mematikannya).
- **`compute_type` tidak bisa ditanyakan ke server**, jadi isi
  `--stt-compute-type`/`--stt-device`/`--label` dengan benar. Kalau tidak,
  metadata hasil tidak bisa dibedakan antar anak tangga §7.
- Metadata hasil mencatat GPU dari `nvidia-smi` mesin yang menjalankan
  skrip. Jalankan skrip **di host GPU** supaya hasil CPU tidak tertukar
  dengan hasil GPU.
- Jalankan **minimal 3 kali**. Run pertama setelah start sering lebih
  lambat (warm-up CUDA). Laporkan run 2–3.
- Ulangi untuk tiap anak tangga penurunan STT yang dicoba (§7). Beri nama
  file dengan model dan compute type.

### 4.3 Avatar — `scripts/bench_avatar.py`

Mengukur fps, latensi frame pertama, backlog, dan VRAM selama 10 menit,
langsung terhadap WebSocket `flashhead-server` (melewati LiveKit/avatar-worker).
Keluaran: `<out>.csv` (deret waktu per 10 dtk), `.chunks.csv`, `.gpu.csv`,
`.summary.json`, dan `.frame.jpg` (contoh frame untuk cek visual). Dependensi
di host: `pip install aiohttp numpy`. **Wajib dijalankan di host GPU**, karena
VRAM dibaca dari `nvidia-smi` mesin yang menjalankan skrip.

```bash
pip install aiohttp numpy
# Hentikan avatar-worker supaya slot flashhead tidak terpakai sesi lain:
$B stop avatar-worker

# 1 sesi, 10 menit (pakai foto referensi uji & rekaman suara Indonesia):
python3 scripts/bench_avatar.py --url ws://$FH_IP:8010/stream \
  --duration-sec 600 --sessions 1 \
  --image deploy/avatar/reference.jpg \
  --audio-file /root/gpu-results/samples/jawab_03_konflik.wav \
  --label "pro, MAX_SESSIONS=1, <nama GPU>" \
  --out /root/gpu-results/avatar-pro-s1.csv

# Paralel: N = FLASHHEAD_MAX_SESSIONS (ubah .env, lalu `$B up -d flashhead-server`;
# start ulang memuat N instance pipeline):
python3 scripts/bench_avatar.py --url ws://$FH_IP:8010/stream \
  --duration-sec 600 --sessions 3 --image deploy/avatar/reference.jpg \
  --label "lite, MAX_SESSIONS=3, <nama GPU>" \
  --out /root/gpu-results/avatar-lite-s3.csv

# Uji penolakan: N+1 sesi -> tepat 1 sesi harus menerima "busy":
python3 scripts/bench_avatar.py --url ws://$FH_IP:8010/stream \
  --duration-sec 60 --sessions 4 --expect-busy 1 \
  --image deploy/avatar/reference.jpg \
  --out /root/gpu-results/avatar-lite-s4-overflow.csv

$B start avatar-worker
```

- **Metrik frame pertama ada dua.** `first_frame_ms` = chunk pertama ucapan
  dikirim → JPEG pertama diterima (≈ waktu inferensi satu chunk; ini yang
  dijadikan ambang, default `--max-first-frame-ms 1000`).
  `utt_first_frame_ms` = awal ucapan → frame pertama, termasuk menunggu satu
  chunk audio penuh (~1,12 dtk). Ini tambahan jeda suara AI yang dirasakan
  kandidat; dilaporkan, tanpa ambang terpisah.
- **Ambang default skrip**: `--min-fps 25` (overall_fps sesi terburuk),
  `--max-first-frame-ms 1000`, `--max-vram-growth-mb 300` (baseline median
  60 dtk setelah warmup vs 60 dtk terakhir), `--max-backlog 3`
  (= `FLASHHEAD_MAX_BACKLOG`), error 0, slot `/health` kembali penuh. Exit 1
  bila ada yang gagal. Tanpa `nvidia-smi` cek VRAM tercatat **DILEWATI**,
  bukan lulus.
- `--ready-timeout` default 600 dtk memberi waktu `torch.compile` varian lite.
- Tanpa `--audio-file`, skrip memakai sinyal mirip ucapan sintetis: beban GPU
  sama, tapi isi bukan Bahasa Indonesia. Untuk menilai lip-sync, lihat
  `.frame.jpg` dan uji E2E §5.

- `FH_IP` berubah setiap container dibuat ulang. Ambil ulang setelah `up -d`.
- Selain angka VRAM dari skrip, rekam juga VRAM dari sisi host sebagai
  pembanding independen:
  `nvidia-smi --query-gpu=timestamp,memory.used,utilization.gpu --format=csv -l 5 > /root/gpu-results/nvsmi-<run>.csv &`
  (hentikan dengan `kill %1`).
- Pada varian **pro** di 1× 4090, kegagalan fps adalah hasil yang
  **diharapkan** menurut klaim README (10,8 FPS). Tujuannya mengonfirmasi
  klaim itu, bukan berharap lolos.

### 4.4 Kontensi GPU: STT saat avatar aktif

Jalankan ulang run STT-saja dari §4.2 **bersamaan** dengan `bench_avatar.py`
sesi N (dua terminal). Ini skenario nyata: dalam satu interview avatar, STT
dan FlashHead memakai GPU yang sama secara bergantian.

### 4.5 Yang TIDAK diukur skrip

Skrip mengukur komponen secara terpisah. Hal-hal berikut **tidak** tertangkap
dan wajib diuji manual (§5): VAD & endpointing (`VAD_MIN_SILENCE`,
`ENDPOINTING_*`), turn detector, jaringan WebRTC (UDP/TCP/TURN), buffering
AvatarRunner (suara AI tertunda ≈ 1 chunk), interupsi, dan rasa percakapan.

---

## 5. Uji E2E manual dengan mikrofon sungguhan

Halaman kandidat: `/ai-interview/session/:token` → komponen
`AIInterviewVoiceCall` (`frontend/src/pages/AIInterviewVoiceCall.tsx`).

**Persiapan (sekali per jalur):**

1. Login sebagai admin (`ADMIN_EMAIL`).
2. AI Interview → buat template dengan mode **"Suara real-time — kandidat
   ngobrol langsung dengan AI"**, 3–5 pertanyaan pendek.
3. Undang kandidat uji (email penguji sendiri) dan salin link sesinya.

**Jalur A:** buka link dari **HP dengan data seluler** (bukan Wi-Fi yang sama
dengan server) [sumber: `docs/DEPLOYMENT.md`, pelajaran 2026-09-26].
Ulangi sekali dari laptop di jaringan kantor (NAT ketat → menguji TURN).

**Jalur B:** buka link dari laptop lewat tunnel (`http://localhost:3000/…`).

**Yang diamati & dicatat** (lembar per sesi, simpan di `/root/gpu-results/e2e-<jalur>-<n>.md`):

- [ ] Panggilan tersambung dalam < 10 dtk [usulan]. Kalau gagal: cek
      `nodeIP` di log livekit dan port UDP.
- [ ] **Jeda yang dirasakan** (kandidat selesai bicara → suara AI mulai),
      diukur untuk ≥ 10 giliran dengan stopwatch, atau lebih baik dari
      rekaman layar + audio (hitung dari waveform). Catat p50 dan maksimum.
- [ ] Interupsi: bicara saat AI bicara. Apakah AI berhenti? Di mode avatar,
      `resume_false_interruption` mati [sumber: `avatar-worker/README.md`],
      jadi bandingkan rasanya dengan voice-only.
- [ ] Akurasi transkrip Bahasa Indonesia large-v3 vs pengalaman `small` di CPU:
      bacakan 5 kalimat yang sudah disiapkan, lalu bandingkan dengan transkrip
      di halaman hasil (hitung kata salah secara kasar).
- [ ] Hening 30 dtk: apakah transkrip berisi halusinasi ("Terima kasih…")?
      Lihat statistik segmen `STT_LOG_STATS` di log agen untuk kalibrasi
      `STT_NO_SPEECH_THRESHOLD` large-v3.
- [ ] Tombol "Bukan suara saya" masih bekerja.
- [ ] Setelah selesai: transkrip lengkap, skor muncul, dan `audio.ogg` bisa
      diputar dengan dua kanal (kandidat & AI).
- [ ] **Jalur B saja:** video avatar tampil di browser, label "avatar video
      buatan AI, bukan orang sungguhan" terlihat, lip-sync Bahasa Indonesia
      dinilai 1–5 oleh penguji, dan `$B logs avatar-worker` tidak
      menunjukkan turun ke StaticRenderer di tengah sesi (atau, kalau turun,
      kapan dan kenapa).
- [ ] **Jalur B saja:** sesi ke-(N+1) saat N slot penuh berjalan voice-only
      (tidak ditolak).

---

## 6. Kriteria lulus/gagal

Persentil dihitung dari run ke-2/ke-3 (setelah pemanasan), dengan ≥ 30
sampel per metrik [usulan].

### 6.1 Suara (Fase 30)

| Metrik | Lulus | Asal | Alasan |
|---|---|---|---|
| STT p95 (per ucapan, large-v3 float16) | **< 500 ms** | **[dari brief]** | target pengguna. Pembanding: di CPU jeda total ~10 dtk [sumber: komentar `docker-compose.prod.gpu.yml`] |
| STT p95 saat avatar aktif (§4.4) | < 750 ms | [usulan] | toleransi 1,5× untuk kontensi GPU. Lebih dari itu, avatar dan STT sebaiknya tidak berbagi GPU |
| LLM TTFT p95 | < 1.500 ms (p50 < 800 ms) | [usulan] | API eksternal: **GPU tidak berpengaruh**. Ambang ini menjaga total tetap < 3 dtk. Gagal di sini bukan kegagalan validasi GPU, tapi wajib dicatat |
| TTS TTFB p95 | < 1.000 ms | [usulan] | API eksternal, **GPU tidak berpengaruh**. Sudah diketahui ada jeda antar-kalimat TTS > 6 dtk di jaringan dev [sumber: `avatar-worker/README.md`]; catat apakah terulang |
| Total skrip (STT + LLM TTFT + TTS TTFB) p95 | < 2.500 ms | [usulan] | jumlah ambang komponen dengan sedikit slack. Belum termasuk VAD/endpointing |
| Jeda dirasakan E2E (§5) p50 / maks | ≤ 4 dtk / ≤ 6 dtk | [usulan] | = ~2,2 dtk dari konfigurasi VAD+endpointing (§2 butir 6) + total skrip. Lebih dari 6 dtk mendekati ambang di mana kandidat mengira giliran AI sudah lewat (uji sintetis memakai 8 dtk) |
| Error rate STT (non-200/timeout) | 0 dari semua sampel | [usulan] | server lokal tanpa jaringan publik: error apa pun adalah bug/konfigurasi |
| Error rate LLM/TTS | ≤ 1 % | [usulan] | API publik bisa sesekali gagal. Lebih dari 1 % dalam satu run kecil = masalah kunci/kuota/region |
| VRAM stt-server | stabil; tidak naik > 5 % antara awal dan akhir run | [usulan] | model tetap dimuat (`WHISPER__TTL=-1`), jadi pertumbuhan menandakan kebocoran |

### 6.2 Avatar (Fase 67)

| Metrik | Lulus | Asal | Alasan |
|---|---|---|---|
| fps berkelanjutan per sesi | **≥ 25**: `overall_fps` sesi terburuk ≥ 25 (gerbang skrip), **dan** `service_fps` p05 ≥ 25 (dibaca dari ringkasan, tidak digerbang skrip) | **[dari brief]**; 25 = fps keluaran protokol (`"fps":25` di `flashhead-server/server.py`) | di bawah 25, antrean tertinggal dan setelah `FLASHHEAD_MAX_BACKLOG`=3 chunk renderer turun ke StaticRenderer [sumber: `avatar-worker/README.md`]. Rata-rata saja tidak cukup, karena itu p05 juga dicek |
| Backlog (in-flight maks) | ≤ 3 | [usulan], = default `FLASHHEAD_MAX_BACKLOG` | di atas itu avatar-worker sungguhan sudah turun ke StaticRenderer |
| Latensi frame pertama (`first_frame_ms`, chunk dikirim → frame) | p95 ≤ 1.000 ms | [usulan], default skrip | 1 chunk = 1.120 ms audio. Di atas 1.120 ms GPU pasti tidak real-time; 1.000 ms menyisakan ~10 % ruang. Yang dirasakan kandidat = `utt_first_frame_ms` ≈ 1,12 dtk tunggu chunk + angka ini, yang langsung menambah jeda suara AI |
| VRAM puncak | ≤ 90 % VRAM total (≥ 2,4 GB sisa di 24 GB), **termasuk** stt-server | [usulan] | ruang untuk fragmentasi allocator dan lonjakan STT. Diukur saat N sesi + STT aktif |
| Pertumbuhan VRAM 10 menit | ≤ 300 MB (median 60 dtk pertama setelah warmup vs 60 dtk terakhir) | [usulan], default skrip `--max-vram-growth-mb` | sesi interview bisa 45 menit (`AI_INTERVIEW_MAX_MINUTES` default). Kebocoran kecil per menit jadi fatal |
| Sesi paralel | N = `FLASHHEAD_MAX_SESSIONS` sesi **bersamaan** semuanya memenuhi fps & frame pertama; sesi N+1 menerima `busy` | [usulan] | klaim README: `lite` 3 sesi di 4090, `pro` bahkan 1 sesi tidak real-time. N terbesar yang lulus = nilai yang direkomendasikan untuk `FLASHHEAD_MAX_SESSIONS`/`AVATAR_MAX_SESSIONS` |
| Error/putus WebSocket | 0 dalam 10 menit | [usulan] | setiap putus memicu fallback ke StaticRenderer di sesi nyata |
| Lip-sync Bahasa Indonesia (E2E) | skor penguji ≥ 3/5 | [usulan] | belum ada metrik objektif. wav2vec2 dilatih pada bahasa Inggris [sumber: `flashhead-server/README.md`], jadi kualitas untuk Bahasa Indonesia benar-benar belum diketahui |

### 6.3 Keputusan

- **Fase 30 lulus GPU** bila semua baris "[dari brief]" dan baris STT di 6.1
  lulus. Baris LLM/TTS yang gagal dicatat sebagai temuan terpisah (bukan
  urusan GPU).
- **Fase 67 lulus** hanya untuk kombinasi varian + N yang semua barisnya di
  6.2 lulus. Kalau yang lulus hanya `lite`, hasilnya **bukan** izin produksi
  (lisensi riset saja, §7).

---

## 7. Rencana penurunan (bila gagal)

Turun satu anak tangga, ulangi benchmark yang gagal, dan catat hasil tiap
anak tangga (termasuk yang gagal).

### 7.1 STT (GPU berpengaruh)

| # | Konfigurasi | Env | Catatan |
|---|---|---|---|
| 1 | large-v3, float16 | `STT_MODEL=Systran/faster-whisper-large-v3`, `STT_COMPUTE_TYPE=float16` | target |
| 2 | large-v3, int8_float16 | `STT_COMPUTE_TYPE=int8_float16` | bobot int8, komputasi fp16. Lebih hemat VRAM, biasanya sedikit lebih cepat [perkiraan] |
| 3 | medium, float16 | `STT_MODEL=Systran/faster-whisper-medium`, `STT_COMPUTE_TYPE=float16` | |
| 4 | medium, int8_float16 | `STT_COMPUTE_TYPE=int8_float16` | |
| 5 | small, float16 | `STT_MODEL=Systran/faster-whisper-small` | default saat ini. Akurasi Bahasa Indonesia pada suara nyata sudah tercatat kurang baik (uji mikrofon 2026-10-29/30), jadi ini anak tangga terakhir |

- **Jangan** memakai `distil-large-v3`: model distil-whisper large-v3
  dilatih untuk **bahasa Inggris saja**. `large-v3-turbo` (multibahasa)
  kandidat di antara #1 dan #3, tapi ketersediaan konversi CTranslate2-nya
  untuk faster-whisper-server belum saya verifikasi.
- Setiap ganti `STT_MODEL`: nilainya harus sama di stt-server, agen, dan
  backend (jalur A cukup satu `.env.production`), lalu `up -d` ulang.
  `STT_NO_SPEECH_THRESHOLD` **wajib dikalibrasi ulang** per model [sumber:
  `.env.example`].
- Jalur A saja: setelah STT cepat, `VAD_MIN_SILENCE` (1.2) dan
  `ENDPOINTING_MIN_DELAY` (1.0) di `.env.production` bisa dicoba diturunkan
  untuk mengurangi jeda dirasakan. Nilai saat ini dipilih karena STT CPU
  lambat [sumber: `agent/main.py`]. Menurunkannya berisiko memotong jawaban
  kandidat yang berhenti sejenak, jadi wajib diuji E2E (§5). Ini bukan
  pengaturan GPU.

### 7.2 LLM & TTS (GPU TIDAK berpengaruh)

Keduanya API eksternal OpenAI lewat `AI_BASE_URL`. Server GPU tidak
mempercepatnya. Kalau gagal, pilihannya ada di luar runbook ini: model agen
lain (`AI_AGENT_MODEL`), model/suara TTS lain (`AI_TTS_MODEL`,
`AI_TTS_VOICE`), atau lokasi server yang lebih dekat ke endpoint API. TTS
self-hosted sudah pernah ditolak karena kualitas suara (`facebook/mms-tts-ind`,
PRD Fase 30).

### 7.3 Avatar

| # | Konfigurasi | Env | Boleh untuk kandidat sungguhan? |
|---|---|---|---|
| 1 | `pro`, 1 sesi | `FLASHHEAD_MODEL_TYPE=pro`, `FLASHHEAD_MAX_SESSIONS=1`, `AVATAR_MAX_SESSIONS=1` | ya (Apache-2.0). Klaim README: **tidak real-time di 1× 4090** (10,8 FPS), jadi kemungkinan besar gagal fps |
| 2 | `lite`, 3 → 2 → 1 sesi | `FLASHHEAD_MODEL_TYPE=lite`, `FLASHHEAD_ACK_NONCOMMERCIAL=1`, `FLASHHEAD_MAX_SESSIONS=AVATAR_MAX_SESSIONS=N` | **TIDAK.** VAE LTX-Video 0.9 = RAIL-M, riset/akademik saja, komersialisasi dilarang, juga melarang impersonasi tanpa persetujuan dan diskriminasi ketenagakerjaan [sumber: `flashhead-server/README.md`]. Hanya untuk uji internal dengan foto & suara penguji sendiri. Hasil lulus di sini **hanya** membuktikan kelayakan teknis |
| 3 | kurangi sesi | turunkan `FLASHHEAD_MAX_SESSIONS` **dan** `AVATAR_MAX_SESSIONS` bersamaan | sesi yang melebihi kapasitas otomatis voice-only |
| 4 | renderer CPU | `AVATAR_RENDERER=static` (flashhead-server tidak perlu dijalankan: hilangkan `--profile avatar-gpu`) | ya. Foto + indikator bicara, tanpa lip-sync. Wiring sudah terverifikasi E2E di CPU (2026-10-23) |
| 5 | voice-only | `AVATAR_PROVIDER=none` (default) | ya, perilaku produksi saat ini |

Ganti `.env` lalu `$B up -d` (flashhead-server membaca env saat start dan
memuat ulang N instance pipeline). Untuk `lite` + `torch.compile`, start
pertama bisa lama [sumber: `flashhead-server/README.md`, "belum teruji"].

Kalau `pro` gagal dan `lite` lulus, kesimpulan bisnisnya: target "1× 4090 +
boleh komersial" **tidak terpenuhi** oleh model ini (sudah diprediksi di PRD
Fase 67). Keputusan berikutnya (GPU lebih besar dengan dukungan multi-GPU,
model lain, atau tetap voice-only) ada di luar runbook ini.

---

## 8. Checklist

### Pra-sewa
- [ ] Penyedia memenuhi §1.5: VM/bare metal, root, Docker, IP publik, UDP inbound tanpa remap, security group sendiri.
- [ ] GPU dipilih (RTX 4090 24 GB untuk avatar), nilai `TORCH_CUDA_ARCH_LIST` diketahui (§1.1).
- [ ] Disk ≥ 150 GB, RAM ≥ 32 GB, ≥ 8 vCPU.
- [ ] Kunci OpenAI **khusus uji** dibuat, dengan batas belanja.
- [ ] Domain/subdomain uji + DNS (atau rencana sslip.io) untuk jalur A.
- [ ] Foto referensi milik penguji sendiri siap. Kalimat uji Bahasa Indonesia untuk akurasi STT disiapkan.
- [ ] `scripts/bench_voice_latency.py` dan `scripts/bench_avatar.py` sudah ada di commit yang akan di-clone.

### Host
- [ ] `nvidia-smi` di host: driver ≥ 570 (dicatat).
- [ ] NVIDIA Container Toolkit + `nvidia-ctk runtime configure` + restart docker.
- [ ] `docker run --rm --gpus all nvidia/cuda:12.8.1-base-ubuntu22.04 nvidia-smi` lulus.
- [ ] Port SSH dicek sebelum ufw (§1.5). Security group: hanya port di §1.4.
- [ ] `git rev-parse HEAD` dan `gpu.csv` dicatat.

### Jalur A — suara (prod)
- [ ] `setup-vps.sh` selesai; `.env.production` dilengkapi (§3.4).
- [ ] `config` menunjukkan stt-server `latest-cuda` + `float16` + device nvidia.
- [ ] Semua service healthy; `nodeIP` = IP publik; agen "registered worker".
- [ ] `nvidia-smi` dari dalam stt-server; digest image & CUDA_VERSION dicatat.
- [ ] Pemanasan STT (unduh large-v3) selesai; VRAM setelah model dimuat dicatat.
- [ ] Benchmark STT-saja × 3 run → CSV.
- [ ] Benchmark pipeline lengkap × 3 run → CSV.
- [ ] Anak tangga STT berikutnya (§7.1) bila STT p95 ≥ 500 ms.
- [ ] E2E dari HP data seluler (§5), ≥ 10 giliran, lembar dicatat.
- [ ] E2E dari jaringan kantor (TURN).
- [ ] `docker compose … logs > /root/gpu-results/logs-jalurA.txt`, lalu `down` (tanpa `-v`).

### Jalur B — avatar
- [ ] `.env` root dilengkapi (§3.5), `LIVEKIT_NODE_IP` = IP publik, `STT_COMPUTE_TYPE=float16` eksplisit.
- [ ] Foto di `deploy/avatar/reference.jpg`.
- [ ] `config` menunjukkan override GPU STT tergabung.
- [ ] Build flashhead-server sukses; waktu build & ukuran image dicatat.
- [ ] Start pertama: gerbang lisensi lulus, bobot terunduh, `/health` flashhead & avatar-worker benar.
- [ ] `bench_avatar.py` pro, 1 sesi, 10 menit + log `nvidia-smi` host.
- [ ] (Uji internal, lisensi riset) `lite` N = 1, 2, 3 sesi × 10 menit; uji overflow N+1 → `busy`.
- [ ] STT benchmark bersamaan dengan avatar (§4.4).
- [ ] E2E avatar via tunnel: video tampil, label terlihat, lip-sync dinilai, fallback dicatat.
- [ ] `$B logs > /root/gpu-results/logs-jalurB.txt`.

### Mencatat hasil (SEBELUM teardown)
- [ ] `scp -r root@<server>:/root/gpu-results ./gpu-results-<tanggal>-<gpu>` ke laptop.
- [ ] Periksa: tidak ada kunci/secret di folder hasil (`grep -ri "sk-\|API_KEY\|SECRET" gpu-results-*`).
- [ ] Hasil disalin ke repo (§9) dan dokumen diperbarui.

### Teardown
- [ ] Kunci OpenAI uji **dicabut** di dashboard OpenAI.
- [ ] `docker compose … down -v` untuk kedua jalur (hapus DB uji, rekaman, bobot, cache model).
- [ ] Hapus `.env`, `.env.production`, `deploy/avatar/reference.jpg` (`shred -u` bila tersedia).
- [ ] Instance **dihancurkan/terminate** (bukan hanya *stop*, karena disk yang di-stop biasanya tetap ditagih dan datanya tetap ada), termasuk volume/snapshot tambahan.
- [ ] Record DNS uji dihapus (jalur A).
- [ ] Tagihan penyedia dicek 24 jam kemudian (tidak ada resource tertinggal).

Bobot model (FlashHead, wav2vec2, whisper) adalah model publik dan tidak
sensitif. Yang sensitif adalah kunci API, `.env*`, foto referensi, rekaman
suara uji, dan log.

---

## 9. Mencatat hasil

**Lokasi.** `docs/04-engineering/gpu-validation-results/<YYYY-MM-DD>-<gpu>/`,
berisi:

- `README.md` dengan metadata run: penyedia & region, model GPU, driver,
  `nvidia-smi` CUDA version, digest image STT, commit git, `STT_MODEL` /
  compute type per run, varian FlashHead & N, waktu build, ukuran
  image/bobot, dan tabel kriteria §6 diisi **angka terukur + lulus/gagal**;
- CSV dari skrip (hanya angka waktu/fps/VRAM). **Jangan** commit audio,
  transkrip suara penguji, foto, atau log mentah yang memuat teks percakapan;
- lembar E2E (§5), tanpa data pribadi.

**Dokumen yang harus diperbarui setelah validasi** (status saat ini
"belum divalidasi/belum diuji"):

| File | Bagian |
|---|---|
| `docs/02-product/PRD.md` | judul & paragraf "Status performa" Fase 30; "Belum teruji" Fase 67; tabel kesiapan baris 5 "Validasi GPU" |
| `docs/02-product/FEATURE_ROADMAP.md` | baris Fase 19/30/59–66 (🟡 GPU) dan baris Fase 67 (avatar) |
| `docs/ROADMAP.md` | baris "Testing" (uji performa GPU) dan "Production Deployment" (`docker-compose.prod.gpu.yml` belum diuji) |
| `docs/DEPLOYMENT.md` §5b | klaim "jeda ~1–2 dtk", spesifikasi GPU, kalimat "Konfigurasi GPU belum diuji" |
| `docker-compose.prod.gpu.yml` | komentar "belum diuji di mesin GPU" & klaim 1–2 dtk |
| `flashhead-server/README.md` | bagian "Belum teruji" dan tabel klaim fps → angka terukur |
| `avatar-worker/README.md` | "Keterbatasan — catatan kejujuran" |
| `CHANGELOG.md` | entri validasi GPU |

Tulis angka apa adanya, termasuk yang gagal, dan pisahkan dengan jelas mana
yang diukur di GPU apa. Perubahan konfigurasi yang ternyata diperlukan
(mis. `MAX_JOBS`, celah compose avatar prod di §2) dikerjakan sebagai
perubahan terpisah, bukan di-hotfix di server sewaan.

---

## 10. Yang belum terbukti

**Yang sudah diuji di CPU (mesin dev Windows, 2026-10-31)**, hanya untuk
membuktikan skripnya bekerja, **bukan** performa:

- `bench_voice_latency.py` end-to-end terhadap `stt-server` CPU
  (`faster-whisper-small`, Docker Desktop) + OpenAI LLM/TTS sungguhan:
  8 sampel Indonesia dibuat lewat `--generate-samples`, 7 giliran terukur,
  0 error, WER rata-rata 0,07, STT p50 22,7 dtk / p95 43,1 dtk (RTF 3,4),
  exit 1 karena gagal ambang 500 ms seperti yang diharapkan di CPU. Angka STT
  CPU ini **lebih lambat** dari catatan "~10 dtk" 2026-09-26, kemungkinan
  karena beban Docker Desktop di mesin dev. Jangan dipakai sebagai pembanding.
- `bench_avatar.py` terhadap server FlashHead **palsu**
  (`scripts/tests/fake_flashhead.py`, "inferensi" = sleep): skenario sehat
  (3 sesi + 1 busy, exit 0), skenario GPU terlalu lambat (1.500 ms/chunk →
  18,5 fps, first frame 1.516 ms, exit 1), dan salah hitung busy (exit 1).
  Pengukuran VRAM **belum pernah** berjalan, karena tidak ada `nvidia-smi`.
- 16 unit test di `scripts/tests/` (persentil, CSV, evaluasi ambang, parser
  `nvidia-smi`, env-file).

Sampai runbook ini dijalankan, **tidak satu pun** dari hal berikut pernah
diukur atau dijalankan:

- **Runbook ini sendiri.** Belum pernah dieksekusi di server GPU. Perintah,
  urutan, perkiraan waktu, dan ukuran disk bisa salah.
- Polling VRAM `nvidia-smi` di `bench_avatar.py`/`bench_voice_latency.py`
  terhadap GPU sungguhan (parser hanya diuji dengan contoh keluaran teks).
- `docker-compose.prod.gpu.yml` di mesin GPU nyata, termasuk apakah image
  `fedirz/faster-whisper-server:latest-cuda` (tag tidak dikunci) cocok dengan
  driver yang tersedia.
- Penggabungan `docker-compose.yml` + `docker-compose.prod.gpu.yml` (§2
  butir 3). Secara struktur benar, tapi belum dijalankan.
- Latensi STT large-v3 di GPU, LLM TTFT dan TTS TTFB dari lokasi server,
  dan jeda yang dirasakan kandidat. Klaim "1–2 dtk" belum diukur dan
  kemungkinan terlalu optimis (§2 butir 6).
- Akurasi Bahasa Indonesia dan perilaku halusinasi large-v3. Ambang
  `STT_NO_SPEECH_THRESHOLD`=0.6 dan `STT_MIN_RMS`=0.02 dikalibrasi untuk
  `small` di CPU dengan mikrofon dev.
- Build image `flashhead-server` (CUDA 12.8 devel + kompilasi flash_attn),
  waktu build, ukuran image, dan start server.
- Semua angka FlashHead: fps `pro` 10,8 / `lite` 96 / 3 sesi paralel adalah
  **klaim README resmi** untuk RTX 4090, bukan hasil Aeos. VRAM per instance
  pipeline × N belum diketahui.
- Lip-sync Bahasa Indonesia (wav2vec2 berbahasa Inggris), latensi frame
  pertama nyata, dan perilaku fallback FlashHead → StaticRenderer di bawah
  beban nyata (selama ini hanya diuji dengan server palsu).
- Tampilan avatar di browser dengan manusia sungguhan, dan dampak
  `resume_false_interruption` yang mati di mode avatar.
- Perilaku kontensi GPU saat STT dan FlashHead berbagi satu GPU.
- Deploy avatar di jalur produksi: belum ada service-nya di
  `docker-compose.prod.yml` (§2 butir 2).
- Keamanan lisensi: catatan lisensi di `flashhead-server/README.md`
  **bukan nasihat hukum**. Konfirmasi ke legal sebelum avatar dipakai ke
  kandidat sungguhan.
