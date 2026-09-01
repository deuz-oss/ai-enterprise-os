FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/srv/.cache/huggingface

WORKDIR /srv

COPY pyproject.toml ./
COPY main.py ./
# Cache mount (bukan --no-cache-dir) -- torch dkk. besar, build ini butuh
# beberapa percobaan di koneksi lambat; cache mount bikin percobaan ulang
# lanjut dari unduhan sebelumnya alih-alih mulai dari nol tiap kali.
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && pip install .

EXPOSE 8000

# Model diunduh sekali saat startup pertama (cache di volume `tts_model_cache`,
# lihat docker-compose.yml) -- start pertama lambat, selanjutnya cepat.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
