#!/usr/bin/env bash
# Penyiapan VPS produksi AEOS (Ubuntu 22.04/24.04, dijalankan sebagai root).
#
#   curl -fsSL https://raw.githubusercontent.com/<org>/ai-enterprise-os/main/deploy/setup-vps.sh -o setup-vps.sh
#   sudo bash setup-vps.sh
#
# Yang dilakukan (idempoten -- aman diulang):
#   1. Instal Docker Engine + plugin compose (repo resmi Docker).
#   2. Firewall (ufw): SSH, 80/443, dan port interview suara bila dipilih.
#   3. Clone/update repo ke /opt/aeos.
#   4. Buat .env.production dengan secret acak (TIDAK menimpa yang sudah ada).
#   5. Build & jalankan stack (plus profile "voice" bila dipilih).
#
# Yang TIDAK dilakukan: membuat DNS record (lakukan di pengelola domain
# SEBELUM langkah 5 supaya Caddy bisa menerbitkan TLS) dan mengisi API key AI.
# Lihat docs/DEPLOYMENT.md.

set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/deuz-oss/ai-enterprise-os.git}"
APP_DIR="${APP_DIR:-/opt/aeos}"

log() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
die() { printf '\033[1;31mGAGAL: %s\033[0m\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "jalankan sebagai root (sudo bash $0)"
. /etc/os-release
[[ "${ID:-}" == "ubuntu" ]] || die "skrip ini untuk Ubuntu (terdeteksi: ${ID:-?})"

# Mode tanpa pertanyaan: isi lewat environment, mis.
#   sudo DOMAIN=aeos.contoh.co.id VOICE=y GPU_CHOICE=y bash setup-vps.sh
# Variabel: DOMAIN (wajib), ADMIN_EMAIL (default admin@DOMAIN), VOICE=y|n,
# GPU_CHOICE=y|n (default: otomatis bila nvidia-smi ada), ASSUME_YES=1 (lewati konfirmasi).
if [[ -z "${DOMAIN:-}" ]]; then
  read -rp "Domain aplikasi (mis. aeos.perusahaan.co.id): " DOMAIN
fi
[[ -n "${DOMAIN:-}" ]] || die "domain wajib diisi"
if [[ -z "${ADMIN_EMAIL:-}" ]]; then
  if [[ -t 0 ]]; then
    read -rp "Email admin pertama: " ADMIN_EMAIL
  else
    ADMIN_EMAIL="admin@${DOMAIN}"
  fi
fi
[[ -n "${ADMIN_EMAIL:-}" ]] || die "email admin wajib diisi"
if [[ -z "${VOICE:-}" ]]; then
  read -rp "Aktifkan interview suara AI (LiveKit + STT)? [y/N]: " VOICE
fi
VOICE=$([[ "${VOICE,,}" == "y" || "${VOICE:-}" == "1" ]] && echo 1 || echo 0)
GPU=0
if [[ $VOICE -eq 1 ]]; then
  G="${GPU_CHOICE:-}"
  if [[ -z "$G" ]]; then
    if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
      G=y; echo "GPU NVIDIA terdeteksi -- memakai konfigurasi GPU."
    elif [[ -t 0 ]]; then
      read -rp "Server punya GPU NVIDIA + driver? [y/N]: " G
    else
      G=n
    fi
  fi
  GPU=$([[ "${G,,}" == "y" || "$G" == "1" ]] && echo 1 || echo 0)
  if [[ $GPU -eq 1 ]] && ! nvidia-smi -L >/dev/null 2>&1; then
    echo "PERINGATAN: driver NVIDIA tidak terdeteksi (nvidia-smi gagal) -- lanjut tanpa GPU (STT di CPU)."
    GPU=0
  fi
  cpus=$(nproc); mem_gb=$(( $(awk '/MemTotal/ {print $2}' /proc/meminfo) / 1024 / 1024 ))
  if (( cpus < 4 || mem_gb < 7 )); then
    printf 'PERINGATAN: %s vCPU / %s GB RAM. Interview suara di CPU butuh >= 4 vCPU / 8 GB.\n' "$cpus" "$mem_gb"
    if [[ "${ASSUME_YES:-}" != "1" ]]; then
      read -rp "Tetap lanjut? [y/N]: " C; [[ "${C,,}" == "y" ]] || die "dibatalkan"
    fi
  fi
fi

log "1/5 Docker Engine"
if ! command -v docker >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y ca-certificates curl git
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  echo "Docker sudah terpasang: $(docker --version)"
fi
command -v git >/dev/null 2>&1 || apt-get install -y git

if [[ $GPU -eq 1 ]] && ! command -v nvidia-ctk >/dev/null 2>&1; then
  log "1b/5 NVIDIA Container Toolkit"
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
    | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
    | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
    > /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt-get update -y
  apt-get install -y nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker
fi

log "2/5 Firewall (ufw)"
apt-get install -y ufw >/dev/null
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
if [[ $VOICE -eq 1 ]]; then
  # Harus sama dengan deploy/livekit.yaml & docker-compose.prod.yml.
  ufw allow 7881/tcp
  ufw allow 50000:50100/udp
  ufw allow 3478/udp
  ufw allow 40000:40100/udp
fi
ufw --force enable
# Catatan: Docker memublikasikan port lewat iptables sendiri; firewall di
# panel provider cloud (security group) juga harus membuka port yang sama.

log "3/5 Kode aplikasi di $APP_DIR"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" pull --ff-only
else
  git clone "$REPO_URL" "$APP_DIR"
fi
cd "$APP_DIR"

log "4/5 .env.production"
secret() { openssl rand -hex 32; }
if [[ -f .env.production ]]; then
  echo ".env.production sudah ada -- tidak ditimpa."
else
  cp .env.production.example .env.production
  set_env() { sed -i "s|^$1=.*|$1=$2|" .env.production; }
  set_env DOMAIN "$DOMAIN"
  set_env CORS_ORIGINS "https://$DOMAIN"
  set_env SECRET_KEY "$(secret)"
  set_env ADMIN_EMAIL "$ADMIN_EMAIL"
  set_env ADMIN_PASSWORD "$(openssl rand -base64 18)"
  set_env POSTGRES_PASSWORD "$(secret)"
  set_env APP_DB_PASSWORD "$(secret)"
  set_env STORAGE_ACCESS_KEY "aeos$(openssl rand -hex 6)"
  set_env STORAGE_SECRET_KEY "$(secret)"
  if [[ $VOICE -eq 1 ]]; then
    set_env LIVEKIT_URL "ws://livekit:7880"
    set_env LIVEKIT_API_KEY "aeos$(openssl rand -hex 6)"
    set_env LIVEKIT_API_SECRET "$(secret)"
    set_env STT_BASE_URL "http://stt-server:8000/v1"
  fi
  chmod 600 .env.production
  echo "Dibuat dengan secret acak. Password admin awal:"
  grep '^ADMIN_PASSWORD=' .env.production
fi
if ! grep -qE '^AI_API_KEY=.+' .env.production; then
  echo "PERINGATAN: AI_BASE_URL/AI_API_KEY belum diisi -- fitur AI (termasuk"
  echo "penilaian & interview suara) nonaktif sampai diisi di $APP_DIR/.env.production."
fi

log "5/5 Build & jalankan"
COMPOSE=(docker compose -f docker-compose.prod.yml)
[[ $GPU -eq 1 ]] && COMPOSE+=(-f docker-compose.prod.gpu.yml)
COMPOSE+=(--env-file .env.production)
[[ $VOICE -eq 1 ]] && COMPOSE+=(--profile voice)
"${COMPOSE[@]}" up -d --build

log "Selesai"
cat <<EOF
Pastikan DNS mengarah ke server ini: $DOMAIN, files.$DOMAIN$( [[ $VOICE -eq 1 ]] && echo ", livekit.$DOMAIN" ).
Cek:   curl -s https://$DOMAIN/health/live
Log:   ${COMPOSE[*]} logs -f
Uji interview suara dari jaringan LUAR server (mis. HP dengan data seluler).
EOF
