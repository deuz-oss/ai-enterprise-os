FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY pyproject.toml ./
COPY main.py interview_flow.py ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

# Unduh bobot model plugin (Silero VAD) saat BUILD, bukan saat job pertama
# -- kalau tidak, sesi interview pertama menunggu unduhan. Turn detector
# lokal v1-mini TIDAK perlu diunduh: modelnya dibundel di paket
# livekit-agents (terverifikasi jalan dgn `--network none`). Env dummy
# karena main.py membaca env wajib saat import.
RUN STT_BASE_URL=http://unused AI_BASE_URL=http://unused python main.py download-files

# Worker long-running (join room LiveKit, tunggu job dispatch) -- BUKAN
# server HTTP, tidak ada port yang di-EXPOSE. `start` = mode produksi
# (connect ke LiveKit, daftar sebagai agent dispatchable, tunggu job).
CMD ["python", "main.py", "start"]
