# AI Enterprise OS Roadmap

**File:** `docs/ROADMAP.md`

**Version:** 1.1

**Status:** Master Delivery Roadmap

**Terakhir diperbarui:** 2026-10-30 — status disinkronkan dengan `CHANGELOG.md` (s/d Fase 73) dan git (s/d commit `96b5374`)

---

# 1. Purpose

Dokumen ini mendefinisikan urutan implementasi AI Enterprise OS dari fase perencanaan hingga operasi produksi.

Roadmap menjadi acuan utama bagi Product, Engineering, AI, QA, dan DevOps untuk memahami prioritas, milestone, serta target setiap fase pengembangan.

---

# 2. Product Lifecycle

```text
Vision

↓

Architecture

↓

Foundation

↓

Platform

↓

Core Intelligence

↓

Business Intelligence

↓

Applications

↓

Enterprise Features

↓

Production

↓

Continuous Improvement
```

---

# 3. Current Progress

| Phase | Status |
| ------------------------------------------ | -------------- |
| AEP (Vision) | ✅ Completed |
| ASF-BUILD (Business Capability) | ✅ Completed |
| ASF-IMPLEMENTATION (Engineering Blueprint) | 🚧 In Progress |
| Repository Governance | 🚧 In Progress |
| Source Code | 🚧 In Progress — backend FastAPI (`backend/app/modules/`), frontend React, mobile Flutter v1 (`mobile/`), agen suara `agent/`, PoC `avatar-worker/`; Fase 1–73 tercatat di `CHANGELOG.md` |
| Testing | 🚧 In Progress — pytest backend (70 file `backend/tests/test_*.py`, termasuk isolasi tenant & drift migrasi), tes `agent/` & `avatar-worker/`, Vitest frontend; semua dijalankan CI (`.github/workflows/ci.yml`). Belum: uji performa di server GPU |
| Production Deployment | 🚧 Disiapkan — `docker-compose.prod.yml` (+ profile `voice`), `deploy/setup-vps.sh`, `docs/DEPLOYMENT.md`; repo tidak mencatat server produksi yang sedang berjalan |

Implementasi aktual dicatat per fase produk (Fase 1–73) di `docs/02-product/FEATURE_ROADMAP.md`, `docs/02-product/PRD.md` §5, dan `CHANGELOG.md`. Catatan implementasi pada Phase 3–8 di bawah adalah pemetaan kasar ke fase-fase itu (per 2026-10-30).

---

# 4. Major Milestones

## Phase 0 — Vision

Objective

Mendefinisikan visi, filosofi, dan arah AI Enterprise OS.

Deliverables

* AEP-000 sampai AEP-050

Status

✅ Completed

---

## Phase 1 — Business Capability Blueprint

Objective

Mendefinisikan seluruh kemampuan bisnis yang harus dimiliki sistem.

Deliverables

* ASF-BUILD-001 sampai ASF-BUILD-050

Status

✅ Completed

---

## Phase 2 — Engineering Blueprint

Objective

Mendefinisikan arsitektur teknis dan standar implementasi.

Deliverables

* System Architecture
* Technology Stack
* Agent Framework
* Data Platform
* Repository Governance
* Security Architecture

Status

🚧 In Progress

---

## Phase 3 — Foundation Platform

Objective

Membangun fondasi teknis yang akan digunakan oleh seluruh modul.

Scope

* Identity
* Multi Tenant
* Workflow Engine
* Knowledge Platform
* AI Runtime
* LLM Gateway
* Observability

Status

🚧 In Progress — sebagian besar sudah ada di kode

Catatan implementasi (2026-10-30)

* Identity: JWT + RBAC per modul, token dicabut saat password berubah (`users.token_version`) — ada.
* Multi Tenant: shared schema `TenantMixin` + RLS PostgreSQL, provisioning `/platform/tenants` — ada.
* AI Runtime / LLM Gateway: `backend/app/core/llm.py` (provider-agnostic, API kompatibel OpenAI) + metering `ai_usage_events` (Fase 17) — ada.
* Knowledge Platform: RAG Q&A kontrak + Pages (wiki internal) — sebagian.
* Workflow Engine: belum ada engine generik; yang ada alur approval spesifik (rantai approval Payment Request multi-level, approval klien ber-token).
* Observability: audit log aplikasi ada; metrics/tracing belum.

---

## Phase 4 — AI Engine

Objective

Membangun mesin AI inti.

Scope

* Agent Runtime
* Memory
* Tool System
* Reasoning Engine
* Evaluation
* Prompt Management

Status

🚧 In Progress — terbatas pada kebutuhan produk

Catatan implementasi (2026-10-30)

* Agent Runtime: worker agen suara AI Interview (`agent/`, LiveKit Agents 1.7.1) — ada, khusus interview.
* Tool System / Reasoning: alur interview terstruktur (`agent/interview_flow.py`), @AEOS & slash command di Chat — spesifik per fitur, belum generik.
* Evaluation: penilaian AI Interview dijalankan 2× + penanda skor tidak stabil + ringkasan kalibrasi reviewer (Fase 64) — spesifik.
* Memory, Prompt Management: belum ada sebagai komponen tersendiri.

---

## Phase 5 — Intelligence Modules

Objective

Mengimplementasikan seluruh domain intelligence.

Target

* Executive Intelligence
* Finance Intelligence
* Sales Intelligence
* Marketing Intelligence
* HR Intelligence
* Operations Intelligence
* Customer Intelligence
* Innovation Intelligence
* Ecosystem Intelligence
* Governance Intelligence

Status

🚧 In Progress — sebagian domain

Catatan implementasi (2026-10-30): implementasi mengikuti domain outsourcing (lihat FEATURE_ROADMAP), bukan sepuluh modul di atas satu per satu.

* Finance: AI akuntansi (asisten tutup buku, anomali, OCR faktur, rekonsiliasi bank, prediksi pembayaran), draf pengingat penagihan, rekonsiliasi invoice ↔ absensi.
* Sales: ringkasan AI lead, cek margin quotation, alasan skor match.
* HR: screening & matching CV, Talent Pool, AI Interview, digest kepatuhan kontrak & BPJS.
* Operations: tinjauan sebelum finalisasi payroll.
* Executive: narasi eksekutif akuntansi, perubahan besar KPI di Dashboard.
* Marketing, Customer, Innovation, Ecosystem, Governance Intelligence: belum ada.

---

## Phase 6 — Enterprise Applications

Objective

Membangun antarmuka pengguna untuk setiap domain.

Examples

* Executive Command Center
* Finance Console
* HR Console
* Operations Console
* Sales Console

Status

🚧 In Progress — sebagian besar ada

Catatan implementasi (2026-10-30)

* Aplikasi web React (41 halaman di `frontend/src/pages/`): Dashboard, Finance, Accounting, Employees, Payroll, Pipeline/CRM, Job Orders, Talent Pool, AI Interview, Chat, plus portal publik (karier, onboarding, portal klien).
* Mobile app internal v1 (Flutter, `mobile/`).
* Belum ada "Executive Command Center" terpisah; Dashboard (`/overview`) yang menjalankan peran itu.

---

## Phase 7 — Enterprise Readiness

Objective

Menyiapkan sistem untuk penggunaan perusahaan.

Scope

* Security Hardening
* High Availability
* Disaster Recovery
* Compliance
* Performance Optimization

Status

🚧 In Progress — sebagian

Catatan implementasi (2026-10-30)

* Security Hardening: audit backend Fase 57, test isolasi tenant (`backend/tests/test_cycle_cross_tenant.py`), pencabutan token — ada.
* Compliance: kepatuhan UU PDP AI Interview (persetujuan, retensi, penarikan; Fase 59), hak hapus data kandidat — ada.
* Performance Optimization: code splitting per route (Fase 68) — sebagian.
* High Availability, Disaster Recovery: belum.

---

## Phase 8 — Production

Objective

Merilis AI Enterprise OS ke lingkungan produksi.

Scope

* Production Deployment
* Monitoring
* Incident Response
* Maintenance

Status

🚧 Disiapkan — belum tercatat berjalan

Catatan implementasi (2026-10-30)

* Production Deployment: `docker-compose.prod.yml` (+ profile `voice`), `docker-compose.prod.gpu.yml` (belum diuji di mesin GPU), `deploy/setup-vps.sh`, `docs/DEPLOYMENT.md` — siap pakai.
* Repo tidak mencatat server produksi yang sedang berjalan; status go-live perlu dikonfirmasi.
* Monitoring, Incident Response: belum.

---

# 5. Engineering Workstream

Setiap fitur harus mengikuti alur berikut.

```text
Business Requirement

↓

Architecture

↓

Implementation

↓

Unit Test

↓

Integration Test

↓

Security Review

↓

Code Review

↓

Release
```

---

# 6. Documentation Workstream

Setiap perubahan harus memperbarui dokumentasi terkait.

| Document | Required |
| ------------------- | ---------------------------------- |
| AEP | Jika ada perubahan visi |
| ASF-BUILD | Jika ada capability baru |
| ASF-IMPLEMENTATION | Jika ada perubahan desain |
| ADR | Jika ada keputusan arsitektur baru |
| TRACEABILITY-MATRIX | Wajib |
| CHANGELOG | Wajib |

---

# 7. Release Strategy

```text
Prototype

↓

MVP

↓

Internal Alpha

↓

Closed Beta

↓

Open Beta

↓

General Availability (GA)

↓

Enterprise Edition
```

---

# 8. Definition of Done

Sebuah milestone dianggap selesai jika:

* Requirement telah diimplementasikan.
* Dokumentasi diperbarui.
* Unit test lulus.
* Integration test lulus.
* Security review selesai.
* Code review disetujui.
* Traceability Matrix diperbarui.

---

# 9. Success Metrics

Keberhasilan roadmap diukur melalui:

* Persentase capability yang selesai.
* Cakupan pengujian.
* Stabilitas sistem.
* Performa AI.
* Waktu deployment.
* Keberhasilan release.

---

# 10. Living Document Policy

ROADMAP.md adalah dokumen hidup.

Setiap milestone, perubahan prioritas, atau penambahan fase harus diperbarui pada dokumen ini sebelum implementasi dimulai.

---

# End of Roadmap
