# AEP-036 — AI Marketplace, Package Registry & Distribution Standards

**Version:** 1.0 (Draft)  
**Status:** Reference Standard

---

# 1. Purpose

Dokumen ini menetapkan standar Marketplace, Package Registry, dan Distribution Framework untuk AI Software Factory.

Tujuan utama:

* Menyediakan mekanisme distribusi komponen AI yang konsisten.
* Mendukung penggunaan ulang lintas proyek dan organisasi.
* Memungkinkan instalasi, pembaruan, dan penghapusan paket secara terkelola.
* Menjamin kualitas, keamanan, dan kompatibilitas paket.

Marketplace menjadi kanal resmi distribusi komponen AI.

---

# 2. Marketplace Principles

Seluruh marketplace mengikuti prinsip:

* Package First.
* Secure by Default.
* Discoverable.
* Versioned.
* Signed.
* Reusable.
* Governed.
* Extensible.

---

# 3. High-Level Architecture

```text id="marketplace-architecture"
Package Publisher
 │
 ▼
Package Registry
 │
 ▼
Marketplace Catalog
 │
 ▼
Package Manager
 │
 ▼
AI Software Factory
```

Registry menyimpan metadata dan paket, sedangkan Marketplace menyediakan pengalaman pencarian dan distribusi.

---

# 4. Supported Package Types

Marketplace mendukung distribusi:

* AI Agent.
* Prompt Pack.
* Workflow Pack.
* Knowledge Pack.
* Tool Connector.
* Plugin.
* UI Component.
* Template.
* Evaluation Suite.
* Policy Pack.
* Documentation Pack.

Jenis paket dapat berkembang sesuai kebutuhan.

---

# 5. Package Manifest

Setiap paket memiliki manifest yang memuat:

* Package ID.
* Nama.
* Deskripsi.
* Versi.
* Penulis.
* Lisensi.
* Dependencies.
* Compatibility.
* Digital Signature.
* Status.

Manifest menjadi sumber informasi resmi paket.

---

# 6. Package Lifecycle

Setiap paket melalui tahapan:

```text id="package-lifecycle"
Create
↓
Validate
↓
Sign
↓
Publish
↓
Install
↓
Update
↓
Deprecate
↓
Archive
```

Seluruh perubahan harus dapat diaudit.

---

# 7. Registry Standards

Package Registry harus mendukung:

* Version history.
* Dependency resolution.
* Integrity verification.
* Metadata indexing.
* Semantic search.
* Access control.

Registry menjadi sumber kebenaran distribusi paket.

---

# 8. Package Installation

Package Manager harus mendukung:

* Install.
* Upgrade.
* Rollback.
* Remove.
* Verify.
* Dependency resolution.

Operasi harus bersifat dapat diprediksi dan terdokumentasi.

---

# 9. Compatibility

Setiap paket menyatakan:

* Versi AEP minimum.
* Versi platform yang didukung.
* Dependensi wajib.
* Dependensi opsional.
* Breaking changes.

Kompatibilitas diperiksa sebelum instalasi.

---

# 10. Security

Seluruh paket harus:

* Ditandatangani secara digital.
* Dipindai terhadap kerentanan yang diketahui.
* Memiliki provenance yang dapat diverifikasi.
* Mematuhi kebijakan keamanan organisasi.
* Menyediakan informasi izin yang dibutuhkan.

---

# 11. Quality Assurance

Sebelum dipublikasikan, paket harus:

* Lulus validasi manifest.
* Lulus pengujian yang relevan.
* Memiliki dokumentasi.
* Menyertakan changelog.
* Menyediakan informasi dukungan.

---

# 12. Observability

Pantau:

* Install Count.
* Active Installations.
* Update Rate.
* Failure Rate.
* Compatibility Issues.
* Download Latency.
* Package Health.

Metrik digunakan untuk meningkatkan kualitas ekosistem.

---

# 13. AI Agent Rules

AI Agent wajib:

* Menginstal paket melalui Package Manager resmi.
* Memeriksa kompatibilitas sebelum penggunaan.
* Menghormati lisensi dan kebijakan paket.
* Memperbarui metadata setelah instalasi atau pembaruan.
* Tidak memodifikasi paket terpasang secara langsung tanpa mekanisme yang sesuai.

---

# 14. Review Checklist

Reviewer memastikan:

* Manifest lengkap.
* Dependensi jelas.
* Kompatibilitas terdokumentasi.
* Paket telah ditandatangani.
* Dokumentasi memadai.
* Pengujian tersedia.

---

# 15. Future Extensions

Framework ini akan diperluas menjadi:

* **AEP-036-REGISTRY** — Package Registry Service.
* **AEP-036-MANAGER** — Package Manager CLI.
* **AEP-036-SIGNING** — Package Signing & Provenance.
* **AEP-036-CATALOG** — Marketplace Catalog Service.
* **AEP-036-CERTIFICATION** — Package Certification Program.
* **AEP-036-POLICIES** — Package Governance Policies.
* **AEP-036-FEDERATION** — Federated Marketplace Standards.

---

# 16. Long-Term Vision

Target jangka panjang adalah membangun marketplace yang:

* Menyediakan ribuan paket AI.
* Mendukung distribusi internal maupun publik.
* Memungkinkan organisasi berbagi komponen secara aman.
* Menjadi pusat discovery untuk AI Agent, workflow, prompt, dan tool.
* Terintegrasi penuh dengan Bootstrap Kit, Workflow Engine, dan Agent Runtime.

---

# 17. Compliance

Seluruh paket yang didistribusikan melalui AI Software Factory wajib mengikuti AEP-036 atau menyediakan mekanisme yang setara untuk metadata, keamanan, kompatibilitas, dan tata kelola.
