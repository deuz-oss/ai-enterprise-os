FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY pyproject.toml requirements.lock ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
# Versi persis dari lock (universal, Python 3.12) supaya build produksi sama dengan
# yang diuji CI -- pyproject hanya batas bawah. Perbarui: lihat AGENTS.md.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.lock \
    && pip install --no-cache-dir --no-deps .

EXPOSE 8000

# Migrasi dijalankan tiap start (idempoten: upgrade/stamp head), lalu server.
CMD ["sh", "-c", "python scripts/migrate.py && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-2}"]
