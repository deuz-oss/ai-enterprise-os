# Product Design Audit — 2026-09-15 (High-Level Survey)

> Companion to `design.md` (design-system source of truth) and the
> 2026-09-12 accessibility audit cycle (see project memory
> `project_ui_audit_cycle`). This document covers dimensions that cycle
> did NOT cover — product clarity, IA, workflow correctness, AI UX,
> enterprise trust, design-system rollout completeness — not a redo of
> the a11y work already shipped.

**Mode:** AUDIT + DESIGN QA (survey level). **Scope:** whole product,
high-level pass — 9 of 23 authenticated routes inspected live
(light + dark), plus code review of the design system and one backend
service. Not exhaustive; a deep-dive on any single module is a
natural follow-up, not done here.

**No code was changed in this pass** — findings only, per the agreed
mode ("redesign dengan approvalku").

---

## Executive Summary

Aeos's design system is unusually mature for its stage: a living
`design.md` with dated decisions and rationale, a real token system
(`--accent`, `--th-color`, `--cat-*`), a documented component library
(`KpiCard`, `StatusPill`, `DonutChart`, `HeaderCanvas`), and a
five-round accessibility audit already shipped (labels, contrast,
keyboard nav across ~20+ pages, verified live not just read). This is
not a product that needs a redesign — it needs its own already-written
rollout plan finished, plus one real correctness bug fixed.

The one finding worth escalating above "polish": the contract-expiry
reminder banner (visible on both Dashboard's "Tindakan Mendesak" and
the Employees page) can surface contracts that expired **years** ago
as "0 hari lagi" urgent — a trust-eroding bug in a surface specifically
designed to build trust (framework §49). Confirmed in both the live UI
(via seeded renewal-chain data from an earlier session) and the
backend query that causes it.

## Design Score

**76/100**

| Category | Score /5 | Notes |
|---|---:|---|
| Product clarity | 4 | Login page states the value prop in one screen; dashboard headline is contextual (greeting + live counts) |
| Information architecture | 4 | 5-category sidebar grouping is deliberate and documented (`design.md` §7); role-filtered nav matches backend RBAC |
| Navigation | 4 | Command palette (⌘K), consistent back-links in detail views, role-aware quick actions |
| UX / workflow correctness | 3 | Real bug found (see Top Findings #1) — an "urgent" surface showing wrong urgency |
| UI visual craft | 4 | Consistent card/table/badge system, clean in both themes |
| Visual hierarchy | 4 | KPI row → urgent banner → per-module cards is a clear, consistent F-pattern across pages |
| Interaction design | **2.5** ▼ *(was 3.5)* | **Revised down** — deep-dive confirmed a real, codebase-wide gap: destructive deletes skip the app's own `confirmToast` pattern in 5+ places (see Deep-Dive Finding #6). This was the item flagged "not re-verified" in the survey; now verified, and the result is worse than assumed |
| Data-dense UX | 3.5 | Table restyle pattern (avatar + StatusPill + tabular-nums) only live on 2 of ~20 tables — tracked, not finished |
| Accessibility | 4 | Inherited from the 2026-09-12 five-round axe-core cycle; not re-audited fresh, informally spot-checked only |
| Responsive | 3 | Mobile drawer/hamburger implemented in `Layout.tsx`. **Genuinely re-attempted this pass and still unverifiable** — see Deep-Dive Addendum; score held, not lowered, since no defect was found, only an inability to test |
| Design system | 4 | Rare for this stage: dated decisions, contrast math shown, explicit non-goals recorded. Minor new note: AI Interview page skips the KPI-row+tabs pattern every other module uses (Deep-Dive Finding #8) |
| AI UX | 3.5 | AI is contextual, not a bolted-on chatbot (good) — but 4 distinct AI surfaces with no unifying explanation (see #2) |
| Enterprise UX | 4 | RBAC enforced UI+backend, audit log gated, credit-balance trust indicator, platform-admin isolation |
| Commercial quality | 4 | No gradient/glassmorphism trend-chasing; reads credible in a sales-demo sense |

**Revised overall score: 74/100** *(was 76/100)* — the Interaction Design
revision above is the only scorecard change from the deep-dive pass; it
moves the average down about 1.4 points. Redesign Level is unchanged
(still LEVEL 1 — POLISH): a missing confirmation dialog is a bug fix,
not an architectural problem.

## Redesign Level

**LEVEL 1 — POLISH.** The architecture (IA, routing, component
library, token system) is sound and intentionally built — nothing here
warrants LEVEL 2+ restructuring. The work that remains is (a) fixing
one real bug, (b) finishing rollouts the team already scoped and
started, and (c) tightening a few UX-clarity gaps. Do not use this
audit as license to introduce new navigation structures, new component
primitives, or a new visual language — that would contradict §8 (don't
redesign blindly) given how deliberate the existing system already is.

---

## Top Findings

### 1. [P1] Contract-expiry reminder surfaces already-expired contracts as "0 hari lagi"

**Evidence:** Employees page banner read *"KON/DUMMY-003/03 berakhir
2024-12-31 (0 hari lagi)"* — today is 2026-09-15, so that contract
expired ~21 months ago. `backend/app/modules/hrd/service.py:1160-1186`
(`expiring_contracts`):
```python
.where(EmploymentContract.end_date <= limit)   # no lower bound
...
"days_left": max(days_left, 0),                # clamps negative → 0
```
No filter excludes **superseded** contracts (ones with a later
contract pointing back via `previous_contract_id`, added this same
session's Tier 2 work) — so every contract in a renewal chain, not
just the current one, is eligible to match.

**Impact:** This banner is the product's "urgent, needs action" trust
surface (Dashboard's "Tindakan Mendesak" pulls from the same kind of
signal). Showing stale, already-resolved contracts as equally urgent
as real ones either causes wasted HR action or — worse — teaches users
to ignore the banner, burying genuinely urgent items (framework §49:
predictability is a trust requirement).

**Recommendation:**
- Add `.where(EmploymentContract.end_date >= today)` to exclude
  already-past contracts.
- Exclude contracts referenced as `previous_contract_id` by another
  contract (i.e., only the latest link in each renewal chain is
  eligible) — mirrors the "root-of-chain" walk already used elsewhere
  in this module for PKWT validation.
- Never clamp negative days to 0 silently; if an already-past contract
  should surface at all (e.g. "kontrak berakhir, belum diperpanjang"),
  give it a distinct label, not a fake "0 hari lagi".

**Expected outcome:** the banner becomes trustworthy again — every
entry is a real, current, actionable item.

### 2. [P2] Four AI entry points with no unifying mental model

**Evidence:** In one short survey pass: floating "Tanya AEOS AI" FAB
(global), in-chat `@AEOS` mention (Chat Workspace), "Tanya Kontrak
(AI)" inline widget (Employees), "AI Executive Digest" card
(Dashboard). Each looks and behaves differently; nothing on first use
explains how they relate.

**Impact:** Framework §12 (AI-native UX) asks that AI reduce
navigation and decision complexity — right now a new user has to
independently discover four different AI affordances and guess their
scope. This is a discoverability tax, not a technical gap; each
surface individually is reasonable and contextual (the opposite of a
bolted-on chatbot, which is the right instinct).

**Recommendation:** Not a rebuild — a legibility pass. Either (a) give
all four a shared visual marker (the same sparkle glyph + consistent
micro-label convention already used on the FAB and digest card) so
they read as "the same AI, different scopes," or (b) a one-line
first-run tooltip near the FAB explaining "Gunakan @AEOS di halaman
manapun untuk tanya soal data yang sedang kamu lihat." Small effort,
meaningfully improves AI UX score.

### 3. [P2] Design-system rollout is real but incomplete, and undertracked as a single unit

**Evidence (all already individually noted in `design.md` §5a/§5b, but
worth surfacing together as one backlog item):**
- Table restyle pattern (avatar+name, `StatusPill`, `tabular-nums`,
  32-36px rows) shipped on 2 of ~20 data tables (Employees main table,
  Dashboard invoice table).
- `HeaderCanvas` pattern shipped on Dashboard only; Job Orders,
  Employees, Payroll were explicitly scoped but not reached.
- Badge dark-mode migration gap still open in `Finance.tsx`
  (aging/risk/forecast boxes), `AccountingAi.tsx` status badges,
  `TalentPoolPanels.tsx:255`.

**Impact:** Individually low-severity (each is cosmetic, not
functional), but collectively they mean the product currently reads as
two visual eras — the restyled pages and the not-yet-restyled ones —
which undercuts the "commercial SaaS" consistency goal that motivated
the whole effort (`design.md` §1).

**Recommendation:** Treat as one epic, sequence by traffic/visibility
rather than file order — Payroll and Job Orders are higher-traffic
than the remaining long tail, and probably belong before finishing
every table in the app.

### 4. [P3] Zero-state KPI cards don't distinguish "genuinely zero" from "no data yet"

**Evidence:** Leads' "Win Rate" shows a bare `-`; Dashboard's "Revenue
MTD" and "Outstanding & Faktur" show `Rp 0` with a caption like "0
invoice tercatat" — accurate, but doesn't explain *why* (new tenant,
no invoices created yet) or suggest a next action.

**Impact:** Minor for an experienced internal user; more consequential
for a first-run paying customer evaluating the product, where an
unexplained wall of zeroes reads as "broken" rather than "you haven't
started" (framework §46 — empty states are part of the product).

**Recommendation:** For KPI cards specifically (not full-page empty
states, which already exist elsewhere in the app), add a short
sub-caption when the underlying dataset is empty tenant-wide, e.g.
"Belum ada invoice — buat dari Quotation yang sudah Deal."

### 5. [P3 / unverified] Responsive behavior implemented but not re-confirmed live this session

**Evidence:** `Layout.tsx` has a real mobile drawer implementation
(hamburger trigger, backdrop, `translate-x` transition, `lg:` 
breakpoint split) — structurally correct. This session's browser
automation could not force a narrow viewport reliably, so it was not
visually re-confirmed.

**Recommendation:** Not a finding of a defect — a flagged gap in this
audit's coverage. A follow-up pass with real viewport testing (browser
devtools device toolbar, or an actual mobile browser) should confirm
before this dimension is scored higher than 3/5.

---

## Design Backlog

| ID | Problem | Priority | Area | Status |
|---|---|---|---|---|
| DES-001 | Contract-expiry reminder shows expired/superseded contracts as urgent | P1 | UX correctness / Workforce | **Fixed** (Sprint 1) |
| DES-002 | AI entry points (FAB, @mention, contract-AI widget, digest card) lack a unifying visual/explanatory pattern | P2 | AI UX | **Fixed** (Sprint 4) — added the shared `Sparkles` marker (already used by FAB + digest card) to the Employees contract-AI widget; Chat's `@AEOS` already had adequate in-place discoverability via its input placeholder, left as-is |
| DES-003 | Finish table-restyle rollout (avatar+StatusPill+tabular-nums) beyond Employees/Dashboard | P2 | Design system | **Fixed** (Sprint 3) — Payroll runs table + Job Orders table; StatusPill got a new `payroll_run` domain, replacing a local color map |
| DES-004 | Finish `HeaderCanvas` rollout to Job Orders/Employees/Payroll | P2 | Design system | **Fixed** (Sprint 3) — all 3 pages; component extended with an `actions` slot (backward-compatible) so each page's primary button/filters sit in the same row |
| DES-005 | Badge dark-mode migration gap (`Finance.tsx`, `AccountingAi.tsx`, `TalentPoolPanels.tsx`) | P3 | Design system | **Fixed** (Sprint 4) — plus one bonus catch (`Pages.tsx` delete-button hover state) found via an app-wide grep sweep confirming no other instances remained |
| DES-006 | KPI cards don't explain tenant-wide zero-state | P3 | UX / onboarding clarity | **Fixed** (Sprint 4) — Dashboard's "Revenue MTD" card |
| DES-007 | Re-verify mobile/responsive rendering with real viewport testing | P3 | Responsive | Unverified (not a confirmed defect) |

DES-003 through DES-005 are not new discoveries — they're already
recorded in `design.md`; listed here so they compete for priority
alongside new findings instead of living only as prose in a different
document.

---

## Deep-Dive Addendum (2026-09-15, same day)

Follow-up to the survey above, run at the user's explicit request
("lanjut deep dive per modul... aku mau seluruhnya"). This pass:
logged in and inspected 15 additional pages/flows not touched in the
survey (Job Orders + detail/Kanban, Quotations, Agreements,
Suppression List, Referral, Talent Pool, AI Interview, Blacklist,
Pages, Payroll, Finance, Accounting, Rates, Billing, Audit); went
deeper on 3 pages only shallow-checked before (all 7 EmployeeDetail
tabs instead of 2, Leads' Kanban board, Users); performed and verified
one real destructive action end-to-end (deleting a dummy emergency
contact, with code-level root-cause confirmation); and made two
genuine, documented attempts at real mobile-viewport testing.

Not accessibility (already covered 2026-09-12) — this pass looked at
layout quality, card arrangement, information usefulness, workflow
completeness, and destructive-action safety.

### 6. [P1] Destructive deletes skip the app's own confirmation pattern in 5+ places

**Evidence:** Live-verified on `EmployeeDetail.tsx` → Ringkasan tab →
Kontak Darurat: clicked "Hapus" next to a dummy emergency contact
("Budi Santoso") — it was deleted **immediately**, no confirmation
dialog, no undo toast, gone in one click.

Code confirms this isn't isolated. The codebase already has a
purpose-built confirmation helper, `confirmToast()` (from
`components/ui`), used in 8 files. But these destructive deletes call
their mutation directly on click, bypassing it entirely:
```
frontend/src/pages/Chat.tsx:589            onClick={() => deleteMessage.mutate(m.id)}
frontend/src/pages/EmployeeDetail.tsx:1293 onClick={() => deleteEmergencyContact.mutate(c.id)}
frontend/src/pages/ClientDetail.tsx:535    onClick={() => deleteSite.mutate(s.id)}
frontend/src/pages/TalentPoolPanels.tsx:361 onClick={() => deleteExperience.mutate(exp.id)}
frontend/src/pages/Payroll.tsx:392         onClick={() => deleteComponent.mutate(c.id)}
```
The Payroll.tsx case is the sharpest evidence this is an inconsistency
rather than a missing feature: **the same file** uses `confirmToast(...)`
correctly at line 765 for a different action, but line 392's delete
button skips it. `EmployeeDetail.tsx` shows the identical split —
`deleteInsurance` (line 2235) is wrapped in `confirmToast("Hapus polis
ini?", ...)`; `deleteEmergencyContact` (line 1293), 940 lines earlier
in the same file, is not.

**Impact:** One misclick = permanent data loss, no recovery path.
Worst-case instances: an emergency contact (safety-relevant — the
entire point of the field is availability during a real emergency) and
a payroll component (financial — silently changes what someone gets
paid). Framework §47: destructive actions need explicit consequences
and, where possible, reversibility. Right now these five have neither.

**Recommendation:** Not a new pattern to design — wrap all five call
sites in the existing `confirmToast()` helper, the same way
`deleteInsurance` and the Payroll.tsx line-765 action already do. Then
grep the rest of the codebase for the same
`onClick={() => delete\w+\.mutate\(` shape to confirm no sixth
instance was missed (this search only covered exact-match direct
mutate calls; delete actions routed through a separate handler
function first would not have matched and were not checked here).

**Expected outcome:** every destructive action in the app goes through
one consistent, already-built confirmation step — a bug fix, not new
scope.

### 7. [P2] Kanban board can hide its only occupied column off-screen by default

**Evidence:** Job Orders → "Operator Produksi" → Candidates tab. Tab
label read "Candidates (1)". Every visible stage column (Sourcing,
Screening, Interview Internal, Disubmit) showed "Kosong" (empty).
Scrolling right ~2 full screen-widths revealed the 1 candidate sitting
in "Onboarded" — the 9th of 9 stage columns. The only affordance
hinting more content exists is a thin, easy-to-miss horizontal
scrollbar; nothing scrolls the board to the occupied stage
automatically, and there's no "items exist further right" indicator.

**Impact:** A recruiter opening this tab sees an apparently-empty
pipeline for a job order that actually has an active candidate — reads
as "nothing is happening here" when the opposite is true.

**Recommendation:** Auto-scroll the board to the stage containing the
most/most-recent candidates on load, or add a visible "→ N kandidat di
tahap lain" affordance when non-empty columns are scrolled out of
view.

### 8. [P2] Rates page exposes raw JSON textareas for a compliance-critical config

**Evidence:** `/rates` → PPh 21 tab → "Versi Baru PPh 21" form. The
progressive tax bracket input is a raw textarea pre-filled with
`[[60000000, 0.05], [250000000, 0.15], [500000000, 0.25],
[5000000000, 0.30], [null, 0.35]]`, plus two more unlabeled "TER A
(JSON)" / "TER B (JSON)" textareas below it.

**Impact:** This configures Indonesian income-tax withholding brackets
— a regulation-driven number that has to be exactly right, maintained
by HR/Finance staff who are very unlikely to be comfortable hand-editing
nested JSON arrays. A malformed or mistyped bracket here doesn't fail
loudly — it silently produces wrong payroll withholding for every
employee under that rate version.

**Recommendation:** Replace with a real bracket editor: repeatable
rows of (min-Rp, rate-%) with add/remove-row controls, client-side
validation that brackets are ascending and rates are 0-100%, no raw
JSON exposed to the end user.

### 9. [P3] Referral reward-amount field has no label, placeholder, or unit

**Evidence:** `/referral` → "Pengaturan Program" — checkbox "Aktifkan
program referral" sits next to a bare number input showing `0`. No
label, no placeholder text, no "Rp" prefix/suffix, no helper text.

**Impact:** A first-time user cannot tell what this number represents
(nominal reward in Rupiah? a percentage? a day count?) without reading
source code or guessing by trial.

**Recommendation:** Add a visible label ("Nominal reward per referral
(Rp)" or whatever it actually is) and a currency-formatted input to
match the rest of the app's Rupiah fields.

### 10. [P3] "Create new" forms placed above "browse existing" content on browse-first pages

**Evidence:** Two independent instances of the same pattern:
- Talent Pool (`/talent-pool`): the "Tambah Kandidat" CV-upload form
  sits above the search/filter bar and the 24-row candidate table,
  even though "Total Talent: 24" in the KPI row signals this is
  primarily a browse/search page.
- Accounting → Jurnal tab (`/accounting`): a blank "Jurnal Umum Baru"
  entry form sits above "Daftar Jurnal 2026", the actual journal list.

**Impact:** Minor, but on both pages the higher-frequency task (find
an existing record) is pushed below the lower-frequency task (create a
new one), adding a scroll for the common case.

**Recommendation:** Not urgent enough to fix in isolation, but worth
bundling with DES-003/004 (table/HeaderCanvas rollout) as one
"page-order/layout consistency" pass, since it's the same kind of
per-page layout polish.

### 11. [Unverified, tooling gap] Mobile viewport genuinely could not be tested this pass either

**Evidence:** Two independent attempts, each verified rather than
assumed: created a fresh tab, called `resize_window` to 390×844,
navigated, and confirmed via `window.innerWidth`/`outerWidth` executed
in the page itself that the browser window **stayed at 1280×672**
regardless — the resize call reports success but has no real effect.
Repeated with a 1-second wait and a second size (400×850): same
result, confirmed via JS both before and after. No device-emulation
tool (CDP viewport override, devtools device toolbar equivalent) is
exposed in the available toolset.

**This is now a confirmed tooling limitation, not a suspected one.**
`Layout.tsx`'s mobile drawer implementation (hamburger, backdrop,
`translate-x` transition, `lg:` breakpoint split) still reads as
structurally correct in code — nothing here found a defect, because
nothing here could actually render the layout narrow enough to check.

**Recommendation:** This genuinely needs a human, or an environment
with real devtools device-toolbar access, to close out. Don't treat
Responsive as verified based on this audit at any point — it has now
been attempted twice and failed twice for the same reason.

---

## Design Backlog (continued)

| ID | Problem | Priority | Area | Status |
|---|---|---|---|---|
| DES-008 | 5+ destructive deletes bypass the app's own `confirmToast` pattern (Chat, EmployeeDetail, ClientDetail, TalentPoolPanels, Payroll) | **P1** | Interaction design / data safety | **Fixed** (Sprint 1) — also caught and fixed a 6th instance during the fix sweep: `Accounting.tsx` used a native, unstyled `window.confirm()` instead of `confirmToast`. Sweep additionally found 4 more unguarded destructive actions outside DES-008's original 5 (`revokePortalAccess` in ClientDetail, `revokeOnboardingInvite` in JobOrderDetail, `removeLeadContact` in Leads, `removeLogo` in TalentPool) — **not fixed yet**, left for approval as a new item, see DES-015 |
| DES-009 | Kanban board doesn't scroll to occupied stage column, can look empty when it isn't | P2 | UX / Recruitment | **Fixed** (Sprint 2) |
| DES-010 | Rates/PPh21 tax bracket config is raw JSON textareas, not a real form | P2 | UX / compliance risk | **Fixed** (Sprint 2) |
| DES-011 | Referral reward-amount input has no label/unit | P3 | UX clarity | **Fixed** (Sprint 2) |
| DES-012 | "Create new" forms placed above "browse existing" content (Talent Pool, Accounting Jurnal) | P3 | Layout / IA | **Fixed** (Sprint 4) — both pages, form content unchanged, only reordered below the list/table |
| DES-013 | AI Interview page skips the KPI-row+tabs pattern used everywhere else | P3 | Design system consistency | **Fixed** (Sprint 3) — KPI row added (Total/Aktif/Draft/Arsip); tabs filter skipped deliberately, template list is small enough that filtering wouldn't add value (see commit notes) |
| DES-014 | Mobile viewport still unverifiable with available tooling — needs a human/real devtools pass | P3 | Responsive (coverage gap, not a defect) | Blocked (tooling) |
| DES-015 | 4 more destructive actions found during the DES-008 fix sweep but not in its original scope, still unguarded: `revokePortalAccess` (`ClientDetail.tsx:474`, revokes a client's portal login), `revokeOnboardingInvite` (`JobOrderDetail.tsx:849`, styled `variant="danger"` but that's cosmetic only — no actual confirm step), `removeLeadContact` (`Leads.tsx:1325`), `removeLogo` (`TalentPool.tsx:243`, lowest severity — just a logo image) | P2 (P3 for removeLogo) | Interaction design / data safety | **Fixed** — all 4 wrapped in `confirmToast()`, same pattern as DES-008. Verified live on `revokePortalAccess` (the highest-severity one). |

### What held up well in this pass (worth preserving, not fixing)

- All 7 `EmployeeDetail` tabs (Dokumen HR, Payroll, Absensi, Riwayat,
  BPJS & Asuransi, Cuti & Akun, plus the previously-seen Ringkasan/
  Kontrak Kerja) have consistent, well-written empty-state copy —
  several explain exactly where to go to unblock the empty state
  (e.g. "buat lewat menu Pengguna dengan role 'karyawan'").
- The bank-account-validation feature shipped earlier this session is
  live and working end-to-end: `EmployeeDetail` correctly showed "⚠
  Rekening tidak ditemukan/tidak aktif" for a dummy BRI account.
- Payroll's pre-flight banner ("3 karyawan rekening bank kosong" +
  "Lihat 3 Kasus") is a genuinely good instance of the Deel-inspired
  preflight-check pattern `design.md` §2 calls for.
- Contract deletion correctly has NO delete button once a contract is
  referenced by a renewal — matches the backend guard shipped earlier
  this session (see prior "cek gap" regression fix); this is the
  right way to prevent a destructive action, by not offering it, and
  stands in useful contrast to Finding #6 above.
- Suppression List, Quotations, Agreements, Blacklist, Referral all
  have clean, consistent empty-state tables with explanatory copy —
  no half-built-looking screens found anywhere in this pass.

---

## Explicitly Out of Scope This Pass

- Full a11y re-audit (already exhaustively covered 2026-09-12, see
  memory `project_ui_audit_cycle`) — not repeated here.
- Deep-dive on any single module (Payroll, Finance, Accounting,
  Recruitment pipeline detail) — this was a breadth-first survey per
  the agreed scope ("seluruh produk, survei tingkat tinggi dulu").
- The 4 token-based external portals (careers, onboarding, client
  portal, AI interview session) — already audited in the prior cycle.
- Any implementation — this document is findings + backlog only,
  pending approval on what to act on.
