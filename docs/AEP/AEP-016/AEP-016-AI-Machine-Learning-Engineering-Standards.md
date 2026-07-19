# AEP-016 — AI & Machine Learning Engineering Standards

**Version:** 1.0 (Draft)  
**Status:** Core Engineering Standard

---

# 1. Purpose

Dokumen ini menetapkan standar AI Engineering dan Machine Learning Engineering untuk seluruh proyek di bawah AI Engineering Playbook (AEP).

Standar ini berlaku untuk:

* Large Language Model (LLM) Applications
* Retrieval-Augmented Generation (RAG)
* Machine Learning
* Deep Learning
* Computer Vision
* Speech AI
* Recommendation Systems
* Predictive Analytics
* AI Agents

Tujuan utama:

* Konsistensi.
* Reproducibility.
* Reliability.
* Safety.
* Scalability.
* Observability.

---

# 2. AI Engineering Principles

Seluruh sistem AI mengikuti prinsip:

* AI by Design.
* Human Oversight.
* Evaluation Before Deployment.
* Data Quality First.
* Prompt as Code.
* Model Agnostic.
* Reproducibility.
* Responsible AI.

AI adalah komponen sistem yang harus direkayasa, diuji, dan dipantau seperti perangkat lunak lainnya.

---

# 3. AI Lifecycle

Seluruh solusi AI mengikuti siklus berikut:

```text id="ai-lifecycle"
Problem Definition
↓
Data Collection
↓
Data Preparation
↓
Model Selection
↓
Training / Configuration
↓
Evaluation
↓
Deployment
↓
Monitoring
↓
Improvement
```

Setiap tahap menghasilkan artefak yang dapat ditinjau dan dilacak.

---

# 4. Problem Definition

Sebelum membangun solusi AI, dokumentasikan:

* Tujuan bisnis.
* Permasalahan yang ingin diselesaikan.
* Pengguna sasaran.
* Kriteria keberhasilan.
* Risiko.
* Batasan.

AI hanya digunakan jika memberikan nilai yang nyata dibanding pendekatan non-AI.

---

# 5. Model Selection

Pemilihan model mempertimbangkan:

* Kemampuan.
* Akurasi.
* Latensi.
* Biaya.
* Ukuran konteks.
* Dukungan multimodal.
* Persyaratan privasi.
* Kemudahan integrasi.

Model dipilih berdasarkan kebutuhan, bukan popularitas.

---

# 6. Prompt Engineering

Prompt diperlakukan sebagai artefak engineering.

Setiap prompt produksi harus:

* Memiliki ID.
* Memiliki versi.
* Memiliki tujuan.
* Memiliki evaluasi.
* Memiliki riwayat perubahan.

Standar detail mengacu pada AEP-007-PROMPT.

---

# 7. Retrieval-Augmented Generation (RAG)

Jika menggunakan RAG:

* Sumber data harus terdokumentasi.
* Metadata harus dipelihara.
* Chunking harus konsisten.
* Retrieval dapat diaudit.
* Konteks harus relevan dan mutakhir.

Kualitas retrieval dievaluasi secara berkala.

---

# 8. AI Evaluation

Evaluasi minimal mencakup:

* Accuracy.
* Relevance.
* Consistency.
* Hallucination Rate.
* Latency.
* Cost.
* Safety.
* User Satisfaction.

Evaluasi dilakukan sebelum dan sesudah deployment.

---

# 9. AI Testing

Jenis pengujian meliputi:

* Prompt Regression Test.
* Golden Dataset Evaluation.
* Output Consistency Test.
* Edge Case Evaluation.
* Safety Evaluation.
* Tool Calling Validation.

Perubahan model atau prompt harus melalui evaluasi ulang.

---

# 10. AI Safety

Sistem AI harus:

* Memiliki guardrails.
* Menangani input yang tidak sesuai.
* Membatasi akses ke tool sensitif.
* Meminimalkan risiko penyalahgunaan.
* Menghindari kebocoran data.

---

# 11. AI Observability

Pantau minimal:

* Request Volume.
* Latency.
* Token Usage.
* Cost.
* Success Rate.
* Error Rate.
* Tool Usage.
* Retrieval Quality.

Observabilitas harus mendukung analisis insiden dan optimasi.

---

# 12. Model Management

Setiap model memiliki:

* Identitas.
* Versi.
* Konfigurasi.
* Riwayat perubahan.
* Status.
* Pemilik.

Perubahan model harus dapat ditelusuri.

---

# 13. Dataset Management

Dataset harus:

* Memiliki versi.
* Memiliki metadata.
* Memiliki sumber yang terdokumentasi.
* Memiliki kebijakan retensi.
* Dapat direproduksi.

Dataset merupakan artefak engineering.

---

# 14. AI Deployment

Deployment AI harus:

* Dapat diulang.
* Memiliki rollback.
* Memiliki monitoring.
* Memiliki evaluasi pascadeployment.
* Mendukung pembaruan yang aman.

---

# 15. Cost Management

Pantau biaya berdasarkan:

* Model.
* Pengguna.
* Fitur.
* Token.
* Agent.
* Workflow.

Optimasi biaya dilakukan tanpa mengorbankan kualitas yang dibutuhkan.

---

# 16. Human Oversight

Keputusan yang berdampak tinggi harus memiliki mekanisme peninjauan manusia sesuai tingkat risiko.

Peran manusia mencakup:

* Persetujuan.
* Audit.
* Eskalasi.
* Evaluasi.

---

# 17. AI Coding Agent Rules

AI Coding Agent wajib:

* Mendokumentasikan asumsi.
* Mematuhi standar AEP terkait.
* Menambahkan evaluasi untuk perubahan AI.
* Memperbarui prompt atau konfigurasi yang relevan.
* Tidak mengganti model produksi tanpa justifikasi dan proses yang ditetapkan.

---

# 18. AI Review Checklist

Reviewer memastikan:

* Tujuan AI jelas.
* Model dipilih berdasarkan kebutuhan.
* Prompt terdokumentasi.
* Evaluasi memadai.
* Risiko dipertimbangkan.
* Monitoring tersedia.
* Biaya dipantau.

---

# 19. Production Readiness Checklist

Sebelum rilis:

* Evaluasi AI lulus.
* Guardrails aktif.
* Monitoring aktif.
* Prompt terversi.
* Model terversi.
* Dataset terversi.
* Dokumentasi lengkap.
* Risiko residual didokumentasikan.

---

# 20. Compliance

Seluruh sistem AI wajib mematuhi AEP-016.

Pengecualian harus didokumentasikan melalui Architecture Decision Record (ADR).

---

# 21. Future Extensions

Standar ini akan diperluas menjadi:

* **AEP-016-RAG** — Retrieval-Augmented Generation Standards.
* **AEP-016-PROMPTS** — Prompt Lifecycle Standards.
* **AEP-016-EVAL** — AI Evaluation Standards.
* **AEP-016-MLOPS** — MLOps Standards.
* **AEP-016-MODELS** — Model Governance Standards.
* **AEP-016-AGENTS** — Agent Runtime Standards.
* **AEP-016-SAFETY** — AI Safety Standards.
* **AEP-016-MULTIMODAL** — Multimodal AI Standards.
