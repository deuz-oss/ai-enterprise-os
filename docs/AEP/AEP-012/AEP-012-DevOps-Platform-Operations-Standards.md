# AEP-012 — DevOps, Platform & Operations Standards

**Version:** 1.0 (Draft)  
**Status:** Core Engineering Standard

---

# 1. Purpose

Dokumen ini menetapkan standar DevOps, Platform Engineering, dan Operations untuk seluruh proyek di bawah AI Engineering Playbook (AEP).

Tujuan utama:

* Otomatisasi proses pengiriman perangkat lunak.
* Deployment yang aman dan dapat diulang.
* Operasional yang andal.
* Observabilitas menyeluruh.
* Skalabilitas platform.
* Keandalan layanan.

Seluruh proses operasional harus dapat diotomatisasi sejauh memungkinkan.

---

# 2. Platform Principles

Seluruh platform mengikuti prinsip:

* Everything as Code.
* Automation First.
* Git as Source of Truth.
* Immutable Infrastructure.
* Self-Service Platform.
* Observability by Default.
* Secure by Default.
* Reliability First.

---

# 3. Environment Strategy

Minimal lingkungan:

```text id="envflow"
Development
↓
Testing
↓
Staging
↓
Production
```

Aturan:

* Setiap environment terisolasi.
* Konfigurasi terdokumentasi.
* Tidak menggunakan data produksi secara langsung kecuali telah dianonimkan dan diizinkan.

---

# 4. Infrastructure as Code

Seluruh infrastruktur harus dikelola sebagai kode.

Mencakup:

* Compute.
* Network.
* Storage.
* Database.
* DNS.
* IAM.
* Kubernetes.
* Monitoring.

Perubahan infrastruktur mengikuti proses review yang sama seperti source code.

---

# 5. CI/CD Standards

Pipeline minimal mencakup:

1. Build.
2. Lint.
3. Type Check (jika relevan).
4. Test.
5. Security Scan.
6. Package.
7. Deploy.
8. Verification.

Deployment manual hanya diperbolehkan untuk kondisi yang telah ditetapkan.

---

# 6. Deployment Strategy

Strategi yang didukung:

* Rolling Deployment.
* Blue/Green Deployment.
* Canary Deployment.

Pemilihan strategi didasarkan pada risiko dan karakteristik layanan.

---

# 7. Configuration Management

Konfigurasi harus:

* Dipisahkan dari aplikasi.
* Terversi.
* Terdokumentasi.
* Dapat diaudit.

Secret dikelola melalui mekanisme khusus sesuai AEP-011.

---

# 8. Container Standards

Jika menggunakan container:

* Satu proses utama per container.
* Image sekecil mungkin.
* Image dipindai untuk kerentanan.
* Gunakan base image yang dipelihara.

Container harus dapat dijalankan secara konsisten di seluruh environment.

---

# 9. Orchestration

Untuk sistem yang memerlukan orkestrasi:

* Gunakan deklarasi konfigurasi.
* Definisikan resource request dan limit.
* Terapkan health check.
* Gunakan rolling update yang aman.

---

# 10. Observability

Seluruh layanan wajib memiliki:

* Structured Logging.
* Metrics.
* Distributed Tracing bila relevan.
* Health Check.
* Readiness Check.
* Alerting.
* Dashboard.

Sistem yang tidak dapat diamati dianggap belum siap produksi.

---

# 11. Monitoring

Pantau minimal:

* Availability.
* Error Rate.
* Latency.
* Throughput.
* Resource Utilization.

Tambahkan metrik bisnis bila diperlukan.

---

# 12. Reliability

Setiap layanan harus memiliki:

* Backup.
* Recovery Plan.
* Disaster Recovery Strategy.
* Capacity Planning.
* Incident Response Procedure.

Target reliabilitas harus ditentukan berdasarkan kebutuhan bisnis.

---

# 13. Release Management

Setiap rilis harus memiliki:

* Nomor versi.
* Catatan perubahan.
* Persetujuan yang diperlukan.
* Rencana rollback.
* Verifikasi pasca-deployment.

---

# 14. Incident Management

Minimal mencakup:

* Deteksi.
* Eskalasi.
* Mitigasi.
* Komunikasi.
* Postmortem.
* Tindakan perbaikan.

Postmortem berfokus pada pembelajaran dan peningkatan sistem.

---

# 15. Platform Security

Platform harus:

* Menggunakan prinsip least privilege.
* Melakukan pemindaian image dan artefak.
* Menerapkan kontrol akses yang sesuai.
* Melindungi pipeline CI/CD.
* Memverifikasi artefak sebelum deployment.

---

# 16. Cost Management

Pantau:

* Compute.
* Storage.
* Network.
* Database.
* AI/LLM Usage.
* Observability Cost.

Optimasi biaya dilakukan tanpa mengorbankan keandalan dan keamanan.

---

# 17. AI Operations (AIOps)

Untuk sistem AI:

* Pantau kualitas model.
* Pantau latensi inferensi.
* Pantau biaya penggunaan model.
* Pantau tingkat kegagalan.
* Pantau drift jika relevan.
* Lakukan evaluasi berkala terhadap prompt dan workflow AI.

---

# 18. AI Coding Agent Rules

AI Coding Agent wajib:

* Memperbarui pipeline bila diperlukan.
* Menambahkan pemeriksaan otomatis yang relevan.
* Tidak melewati quality gate.
* Menjaga kompatibilitas deployment.
* Memperbarui dokumentasi operasional jika perubahan memengaruhi operasi.

---

# 19. Operations Review Checklist

Reviewer memastikan:

* Pipeline otomatis tersedia.
* Deployment dapat diulang.
* Monitoring memadai.
* Alerting tersedia.
* Backup diverifikasi.
* Dokumentasi operasional mutakhir.
* Kepatuhan terhadap AEP-012.

---

# 20. Production Readiness Checklist

Sebelum rilis:

* CI/CD berhasil.
* Deployment tervalidasi.
* Health check aktif.
* Monitoring aktif.
* Alerting aktif.
* Backup tersedia.
* Recovery procedure diuji.
* Dashboard operasional tersedia.
* Risiko residual didokumentasikan.

---

# 21. Compliance

Seluruh sistem wajib mematuhi AEP-012.

Pengecualian harus didokumentasikan melalui Architecture Decision Record (ADR).

---

# 22. Future Extensions

Standar ini akan diperluas menjadi:

* **AEP-012-CI** — Continuous Integration Standards.
* **AEP-012-CD** — Continuous Delivery Standards.
* **AEP-012-GITOPS** — GitOps Standards.
* **AEP-012-OBS** — Observability Standards.
* **AEP-012-SRE** — Site Reliability Engineering Standards.
* **AEP-012-PLATFORM** — Internal Developer Platform Standards.
* **AEP-012-AIOPS** — AI Operations Standards.
