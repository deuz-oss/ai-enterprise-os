# AI Enterprise OS Repository Map

**File:** `docs/REPOSITORY-MAP.md`  
**Version:** 0.1  
**Status:** Foundation Documentation  
**Purpose:** Repository navigation and traceability standard

---

# 1. Purpose

Dokumen ini mendefinisikan struktur hubungan antara:

```
AEP
↓
ASF-BUILD
↓
ASF-IMPLEMENTATION
↓
Repository Module
↓
Source Code
```

Tujuan:

* menjaga traceability seluruh requirement.
* membantu developer dan coding agent memahami lokasi implementasi.
* mencegah architecture drift.
* menjadi peta utama pengembangan AI Enterprise OS.

---

# 2. Repository Philosophy

AI Enterprise OS dibangun dengan 5 lapisan:

```
AEP
Vision Layer

↓

ASF-BUILD
Capability Layer

↓

ASF-IMPLEMENTATION
Engineering Layer

↓

Platform & Intelligence Layer
System Layer

↓

Source Code
Implementation Layer
```

---

# 3. Root Repository Structure

```
ai-enterprise-os/

├── docs/
│
├── apps/
│
├── platform/
│
├── intelligence/
│
├── ai-engine/
│
├── packages/
│
├── database/
│
├── infrastructure/
│
├── security/
│
├── scripts/
│
└── tests/
```

---

# 4. Documentation Mapping

## AEP Layer

Location:

```
docs/AEP/
```

Purpose:

Menyimpan:

* product vision.
* business philosophy.
* strategic direction.
* future evolution.

Format:

```
AEP-XXX-Name.md
```

Example:

```
docs/AEP/
├── AEP-000-Vision.md
├── AEP-001-Enterprise-AI-Concept.md
└── AEP-050-Future-Autonomous-Enterprise.md
```

---

# ASF-BUILD Layer

Location:

```
docs/ASF-BUILD/
```

Purpose:

Mendefinisikan capability yang harus dimiliki sistem.

Format:

```
ASF-BUILD-XXX-Name.md
```

Example:

```
ASF-BUILD-050-Executive-Command-Center.md
```

---

# ASF-IMPLEMENTATION Layer

Location:

```
docs/ASF-IMPLEMENTATION/
```

Purpose:

Dokumen engineering:

* architecture.
* technology.
* implementation approach.
* development standard.

Example:

```
ASF-IMPLEMENTATION-001-System-Architecture.md

ASF-IMPLEMENTATION-002-Technology-Stack.md

ASF-IMPLEMENTATION-003-Agent-Framework.md
```

---

# 5. Capability to Module Mapping

| ASF-BUILD Capability | Repository Location |
| ------------------------ | --------------------------------------- |
| Executive Command Center | `intelligence/executive-intelligence/` |
| Finance Intelligence | `intelligence/finance-intelligence/` |
| Sales Intelligence | `intelligence/sales-intelligence/` |
| Marketing Intelligence | `intelligence/marketing-intelligence/` |
| HR Intelligence | `intelligence/hr-intelligence/` |
| Operations Intelligence | `intelligence/operations-intelligence/` |
| Customer Intelligence | `intelligence/customer-intelligence/` |
| Innovation Intelligence | `intelligence/innovation-intelligence/` |
| Ecosystem Intelligence | `intelligence/ecosystem-intelligence/` |
| Governance Intelligence | `intelligence/governance-intelligence/` |

---

# 6. Platform Mapping

Platform layer menyediakan kemampuan dasar yang dipakai semua intelligence module.

```
platform/

├── identity
│
├── workflow
│
├── knowledge
│
├── agent-runtime
│
└── governance
```

---

## Identity Platform

Location:

```
platform/identity/
```

Responsible for:

* authentication.
* authorization.
* RBAC.
* tenant management.

Related:

* ASF-IMPLEMENTATION security architecture.

---

## Workflow Platform

Location:

```
platform/workflow/
```

Responsible for:

* automation.
* approval.
* business process execution.

---

## Knowledge Platform

Location:

```
platform/knowledge/
```

Responsible for:

* document intelligence.
* enterprise memory.
* semantic search.
* knowledge graph.

---

## Agent Runtime Platform

Location:

```
platform/agent-runtime/
```

Responsible for:

* agent lifecycle.
* tool execution.
* permission.
* evaluation.

---

## Governance Platform

Location:

```
platform/governance/
```

Responsible for:

* audit.
* compliance.
* policy enforcement.

---

# 7. AI Engine Mapping

Location:

```
ai-engine/
```

AI Engine adalah core intelligence runtime.

Structure:

```
ai-engine/

├── agents/
├── reasoning/
├── memory/
├── tools/
├── prompts/
├── evaluations/
└── model-gateway/
```

---

# 8. Executive Intelligence Mapping Example

Complete flow:

```
AEP-050

↓

ASF-BUILD-050
Executive Command Center

↓

ASF-IMPLEMENTATION-003
Agent Framework

↓

intelligence/executive-intelligence/

↓

ai-engine/agents/executive-agent/

↓

Source Code
```

---

# 9. Development Rules

## Rule 1

Tidak boleh membuat module baru tanpa:

```
AEP Reference

+

ASF-BUILD Reference
```

---

## Rule 2

Setiap intelligence module wajib memiliki:

```
README.md

DOMAIN.md

ARCHITECTURE.md

API.md

TESTS.md
```

---

## Rule 3

Setiap AI Agent wajib memiliki:

```
Agent Definition

Prompt Specification

Tool Permission

Memory Strategy

Evaluation Criteria
```

---

# 10. Coding Agent Navigation Instruction

Coding agent wajib membaca:

Urutan:

```
1. README.md

2. docs/REPOSITORY-MAP.md

3. Relevant AEP

4. Relevant ASF-BUILD

5. Relevant ASF-IMPLEMENTATION

6. Source Code
```

Sebelum melakukan perubahan.

---

# 11. Future Expansion

Repository harus siap menerima:

```
New Intelligence Domain

↓

New ASF-BUILD Capability

↓

New Repository Module

↓

New AI Agents
```

Tanpa mengubah core architecture.

---

# 12. Current Status

```
Documentation Mapping
██████████ 100%

Repository Structure
██████████ 100%

Capability Traceability
█████████░ 90%

Implementation
░░░░░░░░░░ 0%
```

---

# End of Repository Map
