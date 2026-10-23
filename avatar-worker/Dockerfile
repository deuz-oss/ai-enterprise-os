FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

COPY pyproject.toml requirements.lock ./
COPY server.py renderers.py video_gen.py capacity.py ./
# Versi persis dari lock (universal, Python 3.12; versi LiveKit dikunci sama
# dengan agent/ lewat -c ../agent/requirements.lock). Regenerasi: README.md.
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.lock \
    && pip install --no-cache-dir --no-deps .

# HTTP internal untuk agen (POST/DELETE /sessions, GET /health). Tidak
# di-publish ke host di docker-compose.yml.
EXPOSE 8090
CMD ["python", "server.py"]
