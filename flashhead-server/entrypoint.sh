#!/usr/bin/env bash
# Gerbang lisensi -> unduh bobot (sekali, ke volume) -> server.
set -euo pipefail

python3 - <<'PY'
import os

from huggingface_hub import snapshot_download
from license_gate import check_license

model_type = check_license(
    os.environ.get("FLASHHEAD_MODEL_TYPE"), os.environ.get("FLASHHEAD_ACK_NONCOMMERCIAL")
)
# Bobot varian yang tidak dipakai tidak diunduh -- untuk `pro`, VAE LTX
# (lisensi riset saja) tidak pernah ada di server.
skip = ["Model_Lite/*", "VAE_LTX/*"] if model_type == "pro" else ["Model_Pro/*"]
snapshot_download(
    "Soul-AILab/SoulX-FlashHead-1_3B",
    revision=os.environ["FLASHHEAD_HF_REVISION"],
    local_dir=os.environ["FLASHHEAD_CKPT_DIR"],
    ignore_patterns=skip,
)
snapshot_download(
    "facebook/wav2vec2-base-960h",
    revision=os.environ["WAV2VEC_HF_REVISION"],
    local_dir=os.environ["FLASHHEAD_WAV2VEC_DIR"],
)
PY

exec python3 server.py
