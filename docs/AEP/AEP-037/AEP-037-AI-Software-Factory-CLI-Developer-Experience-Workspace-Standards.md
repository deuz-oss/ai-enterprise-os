# AEP-037 — AI Software Factory CLI, Developer Experience & Workspace Standards

**Version:** 1.0 (Draft)  
**Status:** Reference Standard

---

# 1. Purpose

Dokumen ini menetapkan standar Command Line Interface (CLI), Developer Experience (DX), dan Workspace untuk AI Software Factory.

Tujuan utama:

* Menyediakan antarmuka terpadu untuk seluruh aktivitas pengembangan.
* Menyederhanakan pengelolaan proyek, agent, workflow, prompt, dan knowledge.
* Mengurangi konfigurasi manual.
* Mendukung otomatisasi dan integrasi dengan pipeline engineering.
* Meningkatkan produktivitas developer dan AI Agent.

CLI merupakan antarmuka utama platform, bukan sekadar utilitas tambahan.

---

# 2. Design Principles

Seluruh CLI mengikuti prinsip:

* Consistent Commands.
* Discoverable.
* Script Friendly.
* Extensible.
* Secure by Default.
* Context Aware.
* Automation Ready.
* Backward Compatible.

---

# 3. CLI Architecture

```text id="cli-architecture"
Developer / AI Agent
 │
 ▼
 AI Factory CLI
 │
 ▼
Command Router
 │
 ┌────────┼────────┐
 ▼        ▼        ▼
Workspace Platform Services Marketplace
```

CLI mengakses platform melalui API dan kontrak resmi.

---

# 4. Workspace Model

Workspace mewakili konteks kerja.

Workspace dapat berupa:

* Personal Workspace.
* Team Workspace.
* Project Workspace.
* Product Workspace.
* Organization Workspace.

Perintah CLI selalu dijalankan dalam konteks workspace yang jelas.

---

# 5. Core Commands

CLI minimal menyediakan kemampuan untuk:

* Membuat proyek baru.
* Mengelola workspace.
* Mengelola AI Agent.
* Mengelola workflow.
* Mengelola prompt.
* Mengelola knowledge.
* Mengelola artefak.
* Mengelola package.
* Menjalankan evaluasi.
* Menampilkan status platform.

Perintah harus konsisten dalam penamaan dan perilaku.

---

# 6. Command Structure

Format umum:

```text id="cli-pattern"
aifactory <resource> <action> [options]
```

Contoh:

```bash id="cli-examples"
aifactory project create
aifactory agent list
aifactory workflow run
aifactory prompt publish
aifactory knowledge search
aifactory package install
```

---

# 7. Configuration

CLI mendukung:

* Global configuration.
* Workspace configuration.
* Project configuration.
* Environment profile.
* Credential management.
* Plugin configuration.

Konfigurasi diprioritaskan dari yang paling spesifik ke yang paling umum.

---

# 8. Developer Experience

Platform harus menyediakan:

* Auto-completion.
* Context-aware help.
* Structured output (JSON/YAML bila sesuai).
* Rich error messages.
* Progress reporting.
* Dry-run mode.
* Interactive mode.

DX harus mempermudah penggunaan tanpa mengurangi kemampuan otomatisasi.

---

# 9. AI Agent Integration

AI Agent dapat menggunakan CLI atau API resmi.

CLI harus:

* Menghasilkan output yang stabil.
* Mendukung mode non-interaktif.
* Memiliki exit code yang terdokumentasi.
* Menghindari perubahan format yang memutus kompatibilitas.

---

# 10. Plugin System

CLI mendukung plugin yang dapat:

* Menambahkan command.
* Menambahkan resource.
* Menambahkan integrasi.
* Menambahkan formatter.
* Menambahkan workflow.

Plugin mengikuti kontrak SDK yang terdokumentasi.

---

# 11. Security

CLI harus:

* Menggunakan autentikasi resmi platform.
* Menghindari penyimpanan rahasia dalam teks biasa.
* Mendukung rotasi kredensial.
* Mematuhi kebijakan organisasi.
* Menghasilkan audit log bila relevan.

---

# 12. Observability

Pantau:

* Command Usage.
* Execution Time.
* Failure Rate.
* Plugin Usage.
* Workspace Activity.
* Automation Success Rate.

Pengukuran digunakan untuk meningkatkan DX.

---

# 13. AI Agent Rules

AI Agent wajib:

* Menggunakan command yang terdokumentasi.
* Tidak bergantung pada output yang tidak dijamin stabil.
* Mematuhi kontrak CLI dan API.
* Menangani kesalahan secara eksplisit.
* Memilih API bila kebutuhan integrasi lebih sesuai daripada CLI.

---

# 14. Review Checklist

Reviewer memastikan:

* Penamaan command konsisten.
* Dokumentasi tersedia.
* Output stabil.
* Mode otomatisasi didukung.
* Konfigurasi tervalidasi.
* Keamanan diterapkan.

---

# 15. Future Extensions

Framework ini akan diperluas menjadi:

* **AEP-037-CLI** — CLI Command Reference.
* **AEP-037-WORKSPACE** — Workspace Management.
* **AEP-037-CONFIG** — Configuration Framework.
* **AEP-037-PLUGINS** — CLI Plugin SDK.
* **AEP-037-AUTOMATION** — Automation Profiles.
* **AEP-037-SHELL** — Interactive AI Shell.
* **AEP-037-REMOTE** — Remote Workspace Management.

---

# 16. Long-Term Vision

Target jangka panjang adalah menyediakan CLI yang:

* Menjadi antarmuka standar AI Software Factory.
* Mendukung operasi lokal maupun jarak jauh.
* Terintegrasi dengan Marketplace, Workflow Engine, dan Agent Runtime.
* Digunakan oleh manusia maupun AI Agent.
* Menyediakan pengalaman yang konsisten di berbagai sistem operasi.

---

# 17. Compliance

Implementasi dianggap sesuai AEP-037 apabila menyediakan antarmuka CLI yang mengikuti struktur command, model workspace, dan kontrak interoperabilitas yang ditetapkan.
