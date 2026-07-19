# AEP-027 — AI Software Factory Repository & Monorepo Standards

**Version:** 1.0 (Draft)  
**Status:** Reference Standard

---

# 1. Purpose

Dokumen ini menetapkan standar struktur repository dan monorepo untuk AI Software Factory.

Tujuan utama:

* Menyediakan struktur proyek yang konsisten.
* Mempermudah kolaborasi manusia dan AI Agent.
* Mendukung modularitas dan skalabilitas.
* Menyederhanakan otomatisasi build, test, deployment, dan dokumentasi.
* Mengurangi variasi struktur antar proyek.

Repository adalah fondasi pengembangan, bukan sekadar tempat penyimpanan kode.

---

# 2. Repository Principles

Seluruh repository mengikuti prinsip:

* Consistent Structure.
* Convention over Configuration.
* Modular Organization.
* Clear Ownership.
* Version Controlled.
* AI Readable.
* Automation Friendly.
* Documentation First.

---

# 3. Repository Model

Platform mendukung:

* Monorepo.
* Multi-repository dengan kontrak yang terdokumentasi.
* Hybrid Repository.

Monorepo direkomendasikan untuk platform inti AI Software Factory.

---

# 4. Standard Directory Layout

Struktur referensi:

```text
/
├── apps/ # Aplikasi utama
├── services/ # Layanan backend
├── packages/ # Library bersama
├── agents/ # AI Agent
├── workflows/ # Workflow definitions
├── prompts/ # Prompt registry
├── knowledge/ # Knowledge base
├── schemas/ # Data contracts
├── apis/ # API specifications
├── infrastructure/ # IaC & deployment
├── scripts/ # Automation scripts
├── docs/ # Dokumentasi
├── tests/ # Test suites
├── examples/ # Contoh implementasi
├── tools/ # Internal tooling
└── .github/ # GitHub workflows & templates
```

Struktur dapat diperluas tanpa mengubah konvensi inti.

---

# 5. Module Standards

Setiap modul memiliki:

* Tujuan yang jelas.
* README.
* Owner.
* Version.
* Dependency declaration.
* Test.
* Documentation.

Modul harus dapat dipahami secara mandiri.

---

# 6. Dependency Management

Ketergantungan antar modul harus:

* Eksplisit.
* Minimum.
* Terdokumentasi.
* Dapat dilacak.

Hindari dependensi melingkar (cyclic dependencies).

---

# 7. Shared Packages

Komponen bersama ditempatkan pada area khusus dan mencakup:

* UI Components.
* Utility Libraries.
* SDK.
* Domain Models.
* Shared Configurations.
* Validation Rules.

Perubahan pada paket bersama mengikuti proses versioning yang ditetapkan.

---

# 8. Repository Metadata

Setiap repository memiliki metadata minimal:

* Nama.
* Deskripsi.
* Pemilik.
* Lisensi.
* Status.
* Versi.
* Kontak.
* Tautan dokumentasi.

Metadata membantu discovery dan governance.

---

# 9. Documentation Structure

Dokumentasi minimal meliputi:

* README.
* Architecture.
* Development Guide.
* API Reference (jika relevan).
* Contribution Guide.
* Changelog.

Dokumentasi berada sedekat mungkin dengan artefak yang dijelaskan.

---

# 10. Automation Layout

Repository menyediakan area untuk:

* Build Automation.
* Test Automation.
* Linting.
* Security Scanning.
* Documentation Generation.
* Release Automation.

Otomatisasi menjadi bagian dari struktur proyek.

---

# 11. AI Agent Integration

Repository menyediakan lokasi khusus untuk:

* Agent Definitions.
* Agent Configurations.
* Prompt Templates.
* Tool Definitions.
* Agent Tests.
* Evaluation Results.

Seluruh artefak AI memiliki struktur yang konsisten.

---

# 12. Repository Governance

Repository harus memiliki:

* CODEOWNERS.
* Branch Protection.
* Pull Request Template.
* Issue Template.
* Security Policy.
* Contribution Guidelines.

Governance diterapkan sejak awal proyek.

---

# 13. AI Agent Rules

AI Agent wajib:

* Mengikuti struktur repository yang ditetapkan.
* Tidak membuat direktori baru tanpa justifikasi.
* Menempatkan artefak pada lokasi yang sesuai.
* Memperbarui dokumentasi bila struktur berubah.
* Menghormati aturan kepemilikan modul.

---

# 14. Review Checklist

Reviewer memastikan:

* Struktur sesuai standar.
* Modul memiliki dokumentasi.
* Dependensi jelas.
* Otomatisasi tersedia.
* Kepemilikan terdokumentasi.
* Tidak ada duplikasi struktur.

---

# 15. Future Extensions

Standar ini akan diperluas menjadi:

* **AEP-027-MONOREPO** — Monorepo Architecture.
* **AEP-027-MODULES** — Module Organization.
* **AEP-027-LIBRARIES** — Shared Library Standards.
* **AEP-027-DEPENDENCIES** — Dependency Governance.
* **AEP-027-GITHUB** — Repository Governance.
* **AEP-027-TEMPLATES** — Project Templates.
* **AEP-027-BOOTSTRAP** — Repository Bootstrap Kit.

---

# 16. Long-Term Vision

Seluruh proyek AI Software Factory dapat dibuat dari template repository yang seragam sehingga:

* Struktur selalu konsisten.
* AI Agent memahami lokasi artefak tanpa konfigurasi tambahan.
* Tooling dapat bekerja lintas proyek.
* Onboarding menjadi lebih cepat.
* Governance lebih mudah diterapkan.

---

# 17. Compliance

Repository dianggap sesuai AEP-027 apabila mengikuti struktur inti, menyediakan metadata yang diperlukan, dan menerapkan mekanisme governance dasar.
