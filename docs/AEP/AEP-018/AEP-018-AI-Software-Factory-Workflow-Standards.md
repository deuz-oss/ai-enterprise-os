# AEP-018 — AI Software Factory Workflow Standards

**Version:** 1.0 (Draft)  
**Status:** Core Engineering Standard

---

# 1. Purpose

Dokumen ini menetapkan standar workflow untuk AI Software Factory di bawah AI Engineering Playbook (AEP).

Tujuan utama:

* Menstandarkan proses pengembangan perangkat lunak berbantuan AI.
* Menghubungkan seluruh standar AEP dalam satu workflow terpadu.
* Memastikan setiap artefak memiliki asal, pemilik, dan jejak perubahan yang jelas.
* Mendukung kolaborasi manusia dan AI Agent secara konsisten.
* Memungkinkan otomatisasi end-to-end dari ide hingga operasi produksi.

Workflow adalah kontrak operasional organisasi engineering.

---

# 2. Workflow Principles

Seluruh workflow mengikuti prinsip:

* Workflow First.
* Artifact Driven.
* Human Governed.
* AI Assisted.
* Traceable.
* Repeatable.
* Observable.
* Continuously Improved.

---

# 3. End-to-End Workflow

Seluruh proyek mengikuti alur berikut:

```text id="factory-workflow"
Idea
↓
Discovery
↓
Validation
↓
PRD
↓
Architecture
↓
UX/UI Design
↓
Planning
↓
Implementation
↓
Testing
↓
Security Review
↓
Documentation
↓
Deployment
↓
Monitoring
↓
Feedback
↓
Continuous Improvement
```

Setiap tahap menghasilkan artefak yang menjadi masukan bagi tahap berikutnya.

---

# 4. Workflow Stages

Tahapan minimal:

* Discovery
* Product Definition
* Solution Design
* Planning
* Development
* Verification
* Release
* Operations
* Improvement

Tidak ada tahap yang boleh dilewati tanpa alasan yang terdokumentasi.

---

# 5. Artifacts

Setiap workflow menghasilkan artefak yang dapat ditelusuri, seperti:

* Vision
* Product Requirements Document (PRD)
* Architecture Decision Record (ADR)
* UX Design
* Source Code
* Test Results
* Security Review
* Deployment Manifest
* Runbook
* Release Notes

Artefak memiliki pemilik, versi, dan status.

---

# 6. Workflow Gates

Setiap transisi antar tahap memiliki quality gate.

Contoh:

* Discovery → PRD: masalah tervalidasi.
* PRD → Architecture: kebutuhan disetujui.
* Development → Testing: implementasi selesai.
* Testing → Deployment: seluruh quality gate lulus.

Gate menjaga kualitas, bukan memperlambat proses.

---

# 7. Roles & Responsibilities

Workflow melibatkan:

* Human Stakeholders.
* Product Manager Agent.
* Architect Agent.
* Engineering Agents.
* QA Agent.
* Security Agent.
* DevOps Agent.
* Documentation Agent.

Setiap artefak memiliki satu penanggung jawab utama.

---

# 8. Workflow Orchestration

Workflow dapat dijalankan:

* Manual.
* Semi-otomatis.
* Sepenuhnya otomatis.

Orkestrasi harus terdokumentasi dan dapat diaudit.

---

# 9. Task Flow

Setiap tugas memiliki:

* ID.
* Status.
* Prioritas.
* Pemilik.
* Dependensi.
* Estimasi.
* Artefak terkait.

Perubahan status harus tercatat.

---

# 10. Decision Management

Keputusan penting harus:

* Didokumentasikan.
* Dapat ditelusuri.
* Memiliki alasan.
* Memiliki penanggung jawab.
* Memiliki tanggal.

ADR digunakan untuk keputusan arsitektur dan teknis yang signifikan.

---

# 11. Human Approval

Persetujuan manusia diperlukan untuk aktivitas yang berdampak tinggi, seperti:

* Persetujuan PRD.
* Persetujuan arsitektur.
* Persetujuan rilis.
* Perubahan keamanan.
* Perubahan kebijakan.

---

# 12. Automation

Workflow yang dapat diotomatisasi meliputi:

* Pembuatan artefak awal.
* Validasi standar.
* Pengujian.
* Review otomatis.
* Deployment.
* Dokumentasi.
* Pelaporan.

Otomatisasi harus tetap dapat diaudit.

---

# 13. Traceability

Setiap artefak harus dapat ditelusuri ke:

* Tujuan bisnis.
* PRD.
* User Story.
* Implementasi.
* Pengujian.
* Deployment.
* Monitoring.

Tidak boleh ada implementasi tanpa asal kebutuhan yang jelas.

---

# 14. Metrics

Pantau minimal:

* Lead Time.
* Cycle Time.
* Deployment Frequency.
* Change Failure Rate.
* Mean Time to Recovery (MTTR).
* Workflow Success Rate.
* AI Assistance Rate.

Metrik digunakan untuk meningkatkan proses.

---

# 15. AI Agent Collaboration

AI Agent harus:

* Mengikuti urutan workflow.
* Melakukan handover yang jelas.
* Menggunakan artefak sebagai media komunikasi.
* Memvalidasi hasil sebelum meneruskan pekerjaan.

Kolaborasi lebih diutamakan daripada optimasi lokal tiap agent.

---

# 16. AI Coding Agent Rules

AI Coding Agent wajib:

* Tidak memulai implementasi tanpa kebutuhan yang memadai.
* Mematuhi seluruh quality gate yang relevan.
* Memperbarui artefak yang terdampak.
* Menjaga keterlacakan perubahan.
* Menolak melewati workflow tanpa otorisasi.

---

# 17. Workflow Review Checklist

Reviewer memastikan:

* Seluruh tahap yang diperlukan telah dijalankan.
* Artefak lengkap.
* Gate terpenuhi.
* Keputusan terdokumentasi.
* Handover jelas.
* Metrik tercatat.

---

# 18. Production Readiness Checklist

Sebelum rilis:

* PRD disetujui.
* Arsitektur disetujui.
* Pengujian selesai.
* Security Review selesai.
* Dokumentasi mutakhir.
* Deployment tervalidasi.
* Monitoring aktif.
* Runbook tersedia.

---

# 19. Compliance

Seluruh proyek wajib mengikuti workflow AEP-018.

Pengecualian harus didokumentasikan melalui mekanisme governance yang berlaku.

---

# 20. Future Extensions

Standar ini akan diperluas menjadi:

* **AEP-018-WORKFLOW** — Workflow Engine Standards.
* **AEP-018-ORCHESTRATION** — Workflow Orchestration Standards.
* **AEP-018-GATES** — Quality Gate Standards.
* **AEP-018-HANDOFF** — Artifact Handover Standards.
* **AEP-018-AUTOMATION** — Workflow Automation Standards.
* **AEP-018-METRICS** — Delivery Metrics Standards.
* **AEP-018-PLAYBOOKS** — Operational Playbook Standards.
