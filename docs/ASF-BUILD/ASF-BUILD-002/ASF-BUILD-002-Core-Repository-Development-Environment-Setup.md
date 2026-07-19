# ASF-BUILD-002 — Core Repository & Development Environment Setup

**Version:** 1.0
**Phase:** Implementation
**Status:** Engineering Specification

---

# 1. Purpose

Dokumen ini mendefinisikan standar pembuatan repository utama dan development environment untuk AI Software Factory.

Tujuan:

* Membuat foundation engineering.
* Menstandarkan workflow developer.
* Menyiapkan environment reproducible.
* Memastikan seluruh engineer dapat bekerja dengan konfigurasi yang sama.

---

# 2. Development Philosophy

Environment harus memenuhi:

## One Command Startup

Developer dapat menjalankan:

```bash
docker compose up
```

untuk menjalankan seluruh sistem.

---

## Reproducible Environment

Tidak bergantung pada:

* konfigurasi laptop,
* versi lokal,
* manual setup.

---

## Developer Friendly

Developer baru dapat onboarding dengan cepat.

---

# 3. Repository Name

Standard:

```
ai-software-factory
```

Repository type:

```
Monorepo
```

---

# 4. Final Repository Structure

```
ai-software-factory/

├── apps/
│
│ ├── web/
│ │ ├── src/
│ │ ├── components/
│ │ ├── pages/
│ │ └── package.json
│ │
│ └── api/
│ ├── app/
│ ├── tests/
│ ├── requirements.txt
│ └── Dockerfile
│

├── packages/
│
│ ├── shared/
│ ├── ai-sdk/
│ └── config/


├── services/
│
│ ├── agent-runtime/
│ ├── workflow-engine/
│ ├── knowledge-service/
│ └── tool-service/


├── database/

│ ├── migrations/
│ └── seeds/


├── infrastructure/

│ ├── docker/
│ ├── kubernetes/
│ └── terraform/


├── docs/

│ ├── architecture/
│ ├── api/
│ └── decisions/


├── scripts/

├── tests/

├── .github/

│ └── workflows/


├── docker-compose.yml

├── README.md

└── .env.example

```

---

# 5. Backend Foundation

Technology:

```
Python 3.12

FastAPI

SQLAlchemy 2

Pydantic v2

Alembic

PostgreSQL

Redis
```

---

Backend structure:

```
apps/api/

app/

├── main.py

├── core/

│ ├── config.py
│ ├── security.py
│ └── database.py


├── modules/

│ ├── users/
│ ├── organizations/
│ ├── projects/
│ └── health/


├── api/

│ └── routes/


└── models/
```

---

# 6. Frontend Foundation

Technology:

```
TypeScript

React

Next.js

Tailwind CSS

Component Library
```

Structure:

```
apps/web/

src/

├── app/

├── components/

├── features/

├── hooks/

├── lib/

├── types/

└── styles/
```

---

# 7. Docker Environment

Services:

```yaml
services:

 api:
 FastAPI


 web:
 Next.js


 postgres:
 PostgreSQL


 redis:
 Redis


 vector:
 pgvector


 storage:
 S3 compatible storage
```

---

# 8. Environment Configuration

File:

```
.env.example
```

Berisi:

```env
APP_ENV=development

DATABASE_URL=

REDIS_URL=

AI_PROVIDER=

AI_API_KEY=

SECRET_KEY=

STORAGE_ENDPOINT=
```

Tidak ada credential hardcoded.

---

# 9. Database Foundation

Initial database:

```
PostgreSQL
```

Schema awal:

```
users

organizations

workspaces

projects

audit_logs
```

---

# 10. Authentication Foundation

Implement:

* JWT authentication.
* Password hashing.
* User session.
* Role permission.

Role awal:

```
OWNER

ADMIN

MEMBER

VIEWER
```

---

# 11. Code Quality Setup

Backend:

Tools:

```
ruff

black

pytest

mypy
```

Frontend:

Tools:

```
eslint

prettier

typescript checker
```

---

# 12. Git Workflow

Branch:

```
main

develop

feature/*

fix/*
```

---

Pull Request wajib:

* description,
* testing result,
* reviewer approval.

---

# 13. CI Pipeline

GitHub Actions:

Workflow:

```
Pull Request

 ↓

Install Dependency

 ↓

Lint

 ↓

Test

 ↓

Build

 ↓

Approval
```

---

# 14. Documentation Foundation

Dokumen wajib:

```
README.md

Architecture Overview

Development Guide

API Documentation

Contribution Guide
```

---

# 15. Local Developer Experience

Developer baru:

Step 1:

Clone:

```bash
git clone ai-software-factory
```

Step 2:

Setup:

```bash
cp .env.example .env
```

Step 3:

Run:

```bash
docker compose up --build
```

Step 4:

Access:

```
Frontend:
http://localhost:3000


Backend:
http://localhost:8000


API Docs:
http://localhost:8000/docs
```

---

# 16. Security Baseline

Wajib:

* Secret management.
* Environment separation.
* Dependency scanning.
* Container scanning.

---

# 17. Initial Deliverables

ASF-BUILD-002 menghasilkan:

## Repository

✅ Monorepo created

---

## Backend

✅ FastAPI running

---

## Frontend

✅ Next.js running

---

## Database

✅ PostgreSQL connected

---

## Infrastructure

✅ Docker Compose running

---

## Quality

✅ CI pipeline active

---

# 18. Definition of Done

ASF-BUILD-002 selesai jika:

Developer dapat menjalankan:

```bash
docker compose up
```

dan mendapatkan:

* frontend aktif,
* backend aktif,
* database aktif,
* API documentation aktif.

---

# 19. Next Phase

Setelah foundation selesai:

## ASF-BUILD-003

**AI Software Factory Core Backend Implementation**

Fokus:

* Domain model.
* Database schema.
* Authentication.
* Organization.
* Workspace.
* Project system.
* API foundation.

---

# End of ASF-BUILD-002
