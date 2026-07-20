FROM python:3.13-slim

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic

COPY src ./src

EXPOSE 8000
CMD ["uvicorn", "organization_service.main:app", "--host", "0.0.0.0", "--port", "8000"]
