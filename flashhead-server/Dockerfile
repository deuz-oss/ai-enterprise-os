# flashhead-server -- SoulX-FlashHead di server GPU NVIDIA (profile compose
# `avatar-gpu`). CATATAN KEJUJURAN: image ini ditulis di mesin dev TANPA GPU
# NVIDIA dan BELUM PERNAH dibangun/dijalankan -- lihat README.md.
#
# Ubuntu 22.04 = Python 3.10 (versi di README resmi). devel (bukan runtime)
# karena flash_attn dikompilasi dari source.
FROM nvidia/cuda:12.8.1-cudnn-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        python3 python3-pip python3-dev git ffmpeg libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Repo resmi dikunci ke satu commit (2026-05-28, "Update README.md").
ARG FLASHHEAD_COMMIT=9bc03de06bb0de82cd6bc477804512ae06144bf2
RUN git clone https://github.com/Soul-AILab/SoulX-FlashHead.git /opt/flashhead \
    && git -C /opt/flashhead checkout ${FLASHHEAD_COMMIT}
WORKDIR /opt/flashhead

COPY requirements.lock /tmp/requirements.lock
RUN python3 -m pip install --no-cache-dir --upgrade pip \
    && python3 -m pip install --no-cache-dir -r /tmp/requirements.lock \
        --extra-index-url https://download.pytorch.org/whl/cu128

# flash_attn versi resmi; butuh torch saat build (--no-build-isolation).
# Arsitektur default 8.9 = RTX 4090 (kompilasi lebih cepat). GPU lain: ubah.
ARG TORCH_CUDA_ARCH_LIST=8.9
ENV TORCH_CUDA_ARCH_LIST=${TORCH_CUDA_ARCH_LIST}
RUN python3 -m pip install --no-cache-dir ninja \
    && MAX_JOBS=4 python3 -m pip install --no-cache-dir flash_attn==2.8.0.post2 --no-build-isolation

# Server Aeos dijalankan dari dalam checkout resmi (config dibuka relatif).
COPY server.py license_gate.py entrypoint.sh ./

# Bobot TIDAK dibakar ke image: diunduh saat start ke volume /models dengan
# revisi Hugging Face terkunci (entrypoint.sh).
ENV FLASHHEAD_CKPT_DIR=/models/SoulX-FlashHead-1_3B \
    FLASHHEAD_WAV2VEC_DIR=/models/wav2vec2-base-960h \
    FLASHHEAD_HF_REVISION=5fbd2e44ba08ab2deb28bd55cff2c15523e51ba5 \
    WAV2VEC_HF_REVISION=22aad52d435eb6dbaf354bdad9b0da84ce7d6156

EXPOSE 8010
ENTRYPOINT ["bash", "entrypoint.sh"]
