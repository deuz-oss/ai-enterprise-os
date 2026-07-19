# AEP-021 — Observability, Reliability & Site Reliability Engineering (SRE) Standards

**Version:** 1.0 (Draft)  
**Status:** Core Engineering Standard

---

# 1. Purpose

Dokumen ini menetapkan standar Observability, Reliability, dan Site Reliability Engineering (SRE) untuk seluruh sistem dalam AI Engineering Playbook (AEP).

Tujuan utama:

* Menjamin keandalan layanan.
* Mendeteksi masalah lebih cepat.
* Mengurangi waktu pemulihan.
* Mendukung operasi berbasis data.
* Meningkatkan pengalaman pengguna melalui sistem yang stabil.

Keandalan adalah fitur produk.

---

# 2. Reliability Principles

Seluruh sistem mengikuti prinsip:

* Reliability by Design.
* Observability by Default.
* Automation First.
* Measure Everything.
* Continuous Improvement.
* Blameless Learning.
* Error Budgets.
* Operational Excellence.

---

# 3. Observability Model

Observability terdiri dari empat pilar utama:

```text id="observability-pillars"
Logs
+
Metrics
+
Traces
+
Events
```

Seluruh layanan harus menghasilkan sinyal observabilitas yang konsisten.

---

# 4. Service Level Objectives (SLO)

Setiap layanan harus memiliki:

* Service Level Indicator (SLI).
* Service Level Objective (SLO).
* Error Budget.

Contoh SLI:

* Availability.
* Latency.
* Success Rate.
* Throughput.

Target SLO ditetapkan berdasarkan kebutuhan bisnis.

---

# 5. Logging Standards

Logging harus:

* Terstruktur.
* Konsisten.
* Dapat dicari.
* Memiliki correlation ID.
* Menghindari pencatatan data sensitif.

Log digunakan untuk analisis, bukan sekadar pencatatan.

---

# 6. Metrics Standards

Pantau minimal:

* Request Rate.
* Error Rate.
* Response Time.
* Resource Utilization.
* Queue Length.
* Cache Hit Rate.
* Database Performance.

Metrik harus memiliki definisi yang terdokumentasi.

---

# 7. Distributed Tracing

Untuk sistem terdistribusi:

* Gunakan trace ID yang konsisten.
* Telusuri alur permintaan lintas layanan.
* Identifikasi bottleneck.
* Dokumentasikan dependensi.

Tracing mempermudah analisis akar penyebab.

---

# 8. Alerting

Alert harus:

* Berbasis gejala, bukan hanya metrik mentah.
* Memiliki tingkat prioritas.
* Memiliki pemilik.
* Mengurangi false positive.

Alert yang tidak dapat ditindaklanjuti harus ditinjau.

---

# 9. Incident Management

Setiap insiden harus melalui:

* Detection.
* Triage.
* Mitigation.
* Recovery.
* Postmortem.
* Preventive Action.

Fokus utama adalah pemulihan layanan dan pembelajaran.

---

# 10. Blameless Postmortem

Setelah insiden:

* Dokumentasikan kronologi.
* Identifikasi akar penyebab.
* Catat faktor yang berkontribusi.
* Tentukan tindakan pencegahan.
* Hindari menyalahkan individu.

Tujuan postmortem adalah meningkatkan sistem.

---

# 11. Capacity Planning

Pantau dan rencanakan:

* CPU.
* Memory.
* Storage.
* Network.
* Database.
* AI Compute.
* Token Consumption.

Perencanaan kapasitas dilakukan secara proaktif.

---

# 12. Reliability Engineering

Layanan harus memiliki:

* Health Check.
* Readiness Check.
* Liveness Check.
* Retry Policy.
* Timeout.
* Circuit Breaker bila relevan.
* Graceful Degradation bila memungkinkan.

---

# 13. AI Observability

Untuk sistem AI, pantau:

* Model Latency.
* Prompt Success Rate.
* Hallucination Trend.
* Token Usage.
* Tool Invocation.
* Retrieval Quality.
* Cost per Request.
* Agent Success Rate.

Observabilitas AI menjadi bagian dari observabilitas sistem secara keseluruhan.

---

# 14. Reliability Metrics

Pantau metrik seperti:

* Availability.
* Mean Time to Detect (MTTD).
* Mean Time to Acknowledge (MTTA).
* Mean Time to Recover (MTTR).
* Change Failure Rate.
* Deployment Frequency.
* Error Budget Consumption.

Metrik digunakan untuk peningkatan berkelanjutan.

---

# 15. AI-Assisted Operations

AI dapat membantu:

* Deteksi anomali.
* Ringkasan insiden.
* Analisis akar penyebab.
* Prediksi kapasitas.
* Prioritisasi alert.
* Rekomendasi mitigasi.

Rekomendasi AI harus dapat diverifikasi oleh operator.

---

# 16. AI Agent Rules

AI Agent wajib:

* Menghasilkan telemetry yang memadai.
* Memperbarui dashboard bila diperlukan.
* Tidak menonaktifkan monitoring tanpa persetujuan.
* Mendokumentasikan perubahan observabilitas.
* Menandai penurunan reliabilitas yang terdeteksi.

---

# 17. Reliability Review Checklist

Reviewer memastikan:

* Logging memadai.
* Metrics tersedia.
* Tracing aktif bila diperlukan.
* Alert dapat ditindaklanjuti.
* SLO terdokumentasi.
* Dashboard diperbarui.
* Risiko operasional dipahami.

---

# 18. Production Readiness Checklist

Sebelum rilis:

* Health check aktif.
* Monitoring aktif.
* Dashboard tersedia.
* Alert tervalidasi.
* SLO ditetapkan.
* Runbook tersedia.
* Prosedur insiden terdokumentasi.

---

# 19. Compliance

Seluruh layanan produksi wajib mematuhi AEP-021.

Pengecualian harus didokumentasikan dan disetujui melalui governance organisasi.

---

# 20. Future Extensions

Standar ini akan diperluas menjadi:

* **AEP-021-SLO** — Service Level Objectives Standards.
* **AEP-021-OBS** — Observability Standards.
* **AEP-021-INCIDENT** — Incident Management Standards.
* **AEP-021-POSTMORTEM** — Blameless Postmortem Standards.
* **AEP-021-AIOPS** — AI Operations Standards.
* **AEP-021-DASHBOARD** — Dashboard Standards.
* **AEP-021-CAPACITY** — Capacity Planning Standards.
