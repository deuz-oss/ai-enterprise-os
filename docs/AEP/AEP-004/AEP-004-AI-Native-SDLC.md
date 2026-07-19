# AEP-004 — AI-Native Software Development Lifecycle (AI-SDLC)

**Version:** 1.0 (Draft)  
**Status:** Core Operational Standard

---

# Purpose

Dokumen ini mendefinisikan siklus hidup pengembangan perangkat lunak yang menjadi standar seluruh proyek dalam AI Engineering Playbook (AEP).

Setiap produk, layanan, library, maupun platform wajib mengikuti AI-SDLC untuk memastikan kualitas, keamanan, konsistensi, dan kemampuan berkembang.

---

# Guiding Principles

AI-SDLC dibangun berdasarkan prinsip:

* Human Accountability.
* AI-Augmented Execution.
* Continuous Validation.
* Shift Left Security.
* Shift Left Testing.
* Documentation as Code.
* Automation by Default.
* Observability by Design.

---

# Lifecycle Overview

```
Idea
 ↓
Discovery
 ↓
Validation
 ↓
Planning
 ↓
Architecture
 ↓
Design
 ↓
Implementation
 ↓
Verification
 ↓
Security Review
 ↓
Release Readiness
 ↓
Deployment
 ↓
Operations
 ↓
Monitoring
 ↓
Learning
 ↓
Continuous Improvement
```

---

# Stage 1 — Idea

## Objective

Mengidentifikasi peluang yang layak dikembangkan.

### Inputs

* Ide produk.
* Masalah pelanggan.
* Insight pasar.
* Inovasi teknologi.

### Activities

* Brainstorming.
* AI-assisted market exploration.
* Problem framing.

### Outputs

* Problem Statement.
* Opportunity Brief.

### Exit Criteria

* Masalah terdefinisi dengan jelas.
* Ada hipotesis nilai yang ingin diuji.

---

# Stage 2 — Discovery

## Objective

Memahami kebutuhan pengguna dan konteks bisnis.

### Activities

* User research.
* Competitive analysis.
* Risk identification.
* Stakeholder interviews.

### AI Support

* Ringkasan wawancara.
* Analisis kompetitor.
* Sintesis kebutuhan.

### Outputs

* Discovery Report.
* Personas.
* User Journey.

---

# Stage 3 — Validation

## Objective

Membuktikan bahwa solusi layak dibangun.

### Activities

* Value proposition validation.
* Feasibility study.
* Technical assessment.
* Cost estimation.

### Outputs

* Validation Report.
* Go / No-Go Decision.

---

# Stage 4 — Planning

## Objective

Mengubah hasil validasi menjadi rencana kerja.

### Outputs

* Product Requirements Document (PRD).
* Roadmap.
* Backlog.
* Sprint Plan.
* Success Metrics.

### AI Support

* Draft PRD.
* User stories.
* Acceptance criteria.

---

# Stage 5 — Architecture

## Objective

Merancang fondasi teknis sebelum implementasi.

### Activities

* System architecture.
* Data model.
* API contract.
* Security architecture.
* AI workflow design.

### Outputs

* Architecture Decision Records (ADR).
* High-Level Design.
* Sequence Diagram.
* Infrastructure Blueprint.

### Exit Criteria

* Architecture review selesai.
* Risiko utama terdokumentasi.

---

# Stage 6 — Design

## Objective

Mendesain pengalaman pengguna dan antarmuka.

### Activities

* UX Flow.
* Wireframe.
* High-Fidelity Design.
* Design System.
* Accessibility Review.

### Outputs

* UI Specification.
* Design Tokens.
* Prototype.

---

# Stage 7 — Implementation

## Objective

Membangun solusi berdasarkan desain dan arsitektur yang disetujui.

### Activities

* Coding.
* Pair Programming (Human + AI).
* Code Review.
* Refactoring.

### Mandatory Rules

* Ikuti AEP Coding Standards.
* Tidak ada hardcoded secret.
* Dokumentasi diperbarui.
* Test ditambahkan untuk fitur baru.

### Outputs

* Source Code.
* Unit Tests.
* Updated Documentation.

---

# Stage 8 — Verification

## Objective

Memastikan solusi memenuhi standar kualitas.

### Activities

* Unit Testing.
* Integration Testing.
* End-to-End Testing.
* Performance Testing.
* AI Evaluation.

### Exit Criteria

* Semua pengujian relevan lulus.
* Tidak ada defect kritis yang diketahui.

---

# Stage 9 — Security Review

## Objective

Memastikan solusi aman sebelum dirilis.

### Activities

* Static Analysis.
* Dependency Scan.
* Secret Detection.
* Threat Review.
* Access Control Review.

### Outputs

* Security Assessment.
* Risk Register.

---

# Stage 10 — Release Readiness

## Objective

Memastikan produk siap dipublikasikan.

### Checklist

* Dokumentasi lengkap.
* Monitoring aktif.
* Rollback plan tersedia.
* Deployment plan disetujui.
* Support plan tersedia.

### Output

* Release Approval.

---

# Stage 11 — Deployment

## Objective

Merilis perubahan secara aman.

### Activities

* Automated Deployment.
* Smoke Test.
* Health Check.
* Canary / Blue-Green Deployment (jika relevan).

### Outputs

* Production Release.
* Deployment Report.

---

# Stage 12 — Operations

## Objective

Menjaga sistem tetap stabil dan dapat diandalkan.

### Activities

* Incident Management.
* Capacity Planning.
* Cost Monitoring.
* Backup Verification.

### Outputs

* Operational Dashboard.
* Incident Log.

---

# Stage 13 — Monitoring

## Objective

Mengamati kesehatan sistem dan pengalaman pengguna.

### Metrics

* Availability.
* Latency.
* Error Rate.
* Resource Utilization.
* Customer Satisfaction.
* AI Model Performance.

### Outputs

* Monitoring Dashboard.
* Alerts.
* Trend Reports.

---

# Stage 14 — Learning

## Objective

Mengubah pengalaman menjadi pengetahuan organisasi.

### Activities

* Sprint Retrospective.
* Post-Incident Review.
* Customer Feedback Analysis.
* AI Performance Review.

### Outputs

* Lessons Learned.
* Improvement Backlog.
* Updated Playbook.

---

# Stage 15 — Continuous Improvement

## Objective

Meningkatkan produk, proses, dan organisasi secara berkelanjutan.

### Activities

* Process optimization.
* Refactoring.
* Technical debt reduction.
* Standard updates.
* Automation improvements.

### Outputs

* Improvement Plan.
* Updated Standards.

---

# AI Responsibilities Across the Lifecycle

AI dapat membantu dalam:

* Analisis kebutuhan.
* Penyusunan PRD.
* Desain arsitektur.
* Pembuatan kode.
* Refactoring.
* Pengujian.
* Dokumentasi.
* Analisis keamanan.
* Ringkasan retrospektif.

AI tidak menggantikan persetujuan manusia pada keputusan strategis, keamanan, kepatuhan, maupun rilis ke produksi.

---

# Definition of Done

Sebuah pekerjaan dianggap selesai apabila:

* Tujuan bisnis tercapai.
* Kode memenuhi standar AEP.
* Seluruh pengujian relevan lulus.
* Dokumentasi diperbarui.
* Keamanan telah ditinjau.
* Monitoring tersedia.
* Artefak tersimpan di repositori yang sesuai.
* Pembelajaran penting telah didokumentasikan.

---

# Governance

Tidak ada tahap yang boleh dilewati tanpa persetujuan yang terdokumentasi. Pengecualian hanya diperbolehkan dalam kondisi darurat dan wajib dievaluasi setelah insiden selesai.

AI-SDLC adalah proses baku yang menjadi acuan seluruh proyek di bawah AI Engineering Playbook dan menjadi fondasi operasional AI Software Factory.
