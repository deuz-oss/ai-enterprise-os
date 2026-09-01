FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY pyproject.toml ./
COPY main.py ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir .

# Worker long-running (join room LiveKit, tunggu job dispatch) -- BUKAN
# server HTTP, tidak ada port yang di-EXPOSE. `start` = mode produksi
# (connect ke LiveKit, daftar sebagai agent dispatchable, tunggu job).
CMD ["python", "main.py", "start"]
