# AEOS — FULL PRODUCT, CODE & UI/UX AUDIT

**Date:** 2026-10-08 · **Mode:** audit only, no production code changed ·
**Companions:** `design.md` (design-system source of truth),
`PRODUCT_DESIGN_AUDIT-2026-09-15.md` (product/IA survey),
`ui-audit-2026-09-12/` (5-round accessibility cycle), backend audit Fase 57
(CHANGELOG).

**Method.** Code read across `frontend/src` (41 pages, 29.3k lines) and
`backend/app` (26 modules), pattern counts by grep, a production build to
measure the bundle, and live browser QA against the local dev stack
(Vite + FastAPI + seeded SQLite) at 1280px desktop, plus 390px (mobile) and
820px (tablet) through a same-origin iframe harness. The browser window
itself could not be resized, the same blocker the 2026-09-15 audit hit.

**Evidence labels:** **[LIVE]** seen in the running app ·
**[CODE]** read in source with file:line · **[COUNT]** grep count ·
**[INFERRED]** follows from code but not reproduced live.

**Product reality check.** The brief describes a generic ERP (sales,
purchasing, inventory). The repo is something more specific: a
**multi-tenant operating system for Indonesian outsourcing / staffing
companies**. It covers CRM → quotation → agreement → job order →
recruitment / AI interview → onboarding → employee (BPJS, contracts,
leave) → attendance → payroll (Saltab, PPh21) → invoicing / e-Faktur →
accounting. There is no inventory or purchasing module. This audit judges
the product it actually is, and does not invent the missing modules as
requirements.

> **Status 2026-10-08 (later):** Phase 0 implemented. P0 #1–#3 and P1 #4,
> #5, #7 (persistent `confirmToast`), and the login-error announcement are
> fixed. See CHANGELOG "Fase 67".
> **Phase 1** implemented as CHANGELOG "Fase 68": route-level code splitting
> (initial JS 610 → 96 KB gzip), state primitives (`components/ui/states.tsx`)
> adopted on the pages with no error UI, single date formatters, semantic
> status tokens + `.num`. Rolling `.num`/`TableStateRow` out to every table is
> Phase 3 (`DataTable`).
> **Phase 2** implemented as CHANGELOG "Fase 69": Pipeline side panel with
> `?lead=` URL, Payroll run stepper + `slip_count`, `PeriodPicker`, tablet
> header fix, dead period control removed, FAB padding, English nav labels.
> **Phase 3 (wave 1)** as CHANGELOG "Fase 70": `DataTable` primitive on Finance
> invoices, Payroll BPJS recap, Employees, Clients; invoice mark-paid now
> confirmed. 47 hand-built tables remain (largest: Accounting 8).
> **Phase 4** as CHANGELOG "Fase 71": DataTable mobile card mode, MyPortal's 6
> tables migrated, skip link, inert mobile drawer with focus management,
> global :focus-visible, labelled ESS/finance forms, contrast fixes; axe-core
> WCAG 2.2 AA sweep (12 admin pages + 7 ESS sections at 390px).
> **Phase 5** as CHANGELOG "Fase 72": Decimal journal posting (fixed payroll
> journals silently rejected when slips had non-tax deductions; new account
> 2-1400), `useMe` + shared types, cache cleared on login/logout, Vitest in CI.
> Correction: `/overview` is 17 ms / 27 constant queries in-process; the 4.1 s
> in §13 and Top-20 #20 was the Docker stack on :8000, not the endpoint.
> **Phase 6** as CHANGELOG "Fase 73": AI opportunities #1 (payroll
> pre-finalize review) and #2 (receivables reminder drafts) shipped with
> deterministic findings + optional, labelled AI text that never sends or
> writes data. Opportunities #3-#10 remain open.
> **Still-open round (2026-10-09)**: opportunity #3 (invoice ↔ attendance
> reconciliation) shipped -- `GET /finance/invoices/{id}/reconciliation`,
> deterministic findings + optional labelled AI summary, "Cek absensi" in the
> Finance invoice table. Runtime deps pinned (`backend/requirements*.lock`,
> used by Docker & CI). Remaining hand-built tables migrated to `DataTable`
> (intentional exceptions: Saltab grid, attendance import errors, dashboard
> & forecast summaries, tenant license/usage panels, review dialog). Browser
> re-check: skip link, mobile drawer (main now inert while open; menu button
> toggles), payroll review & reminder dialogs (reminder now returns focus).
> **Decision 2-1400**: stays a *liability clearing* account (Potongan Gaji
> Lain-lain) -- accountants reclassify; no code change. #4-#10 remain open.

---

## 1. Executive Summary

AEOS is far more mature than an "internal CRUD app." It has real
multi-tenancy that the ORM enforces automatically, a central RBAC registry
backed by a matrix test, an audit log, Alembic with a drift test, 60
backend test files, CI, zero `any` in the TypeScript, a token-based
design system with a written rationale, and an accessibility pass already
shipped. The architecture does **not** need rework.

**What would real business users complain about in week one:**

1. **"The numbers don't agree."** **[LIVE]** The Dashboard shows
   *Outstanding Rp 4.357.602.000 · 2 overdue*. The Finance page, under the
   same concept, shows *Total Outstanding Rp 10.146.592.000 · 4 overdue*.
   The aging report counts **draft (never-sent) invoices** as overdue
   receivables (`backend/app/modules/finance/service.py:267`). The
   dashboard KPI does not. In a finance product, two different totals for
   one label destroy trust faster than any visual issue.
2. **"One click and payroll is locked forever."** **[CODE+LIVE]**
   *Finalisasi* on a payroll run is a 20px-tall red text link sitting next
   to *Generate*. It fires immediately with no confirmation
   (`frontend/src/pages/Payroll.tsx:957,969`). Finalizing cannot be undone
   (no reopen path in `payroll/service.py`) and it auto-posts a journal.
   Cancelling a tax invoice (*Batalkan* faktur, `Finance.tsx:447-453`) and
   marking a referral reward paid (`Referral.tsx:217`) are also one-click.
3. **"Payroll says 38 employees — we have 300."** **[CODE]** Payroll and
   Attendance load `/employees` with no limit, so the backend default of
   200 applies (`hrd/router.py:76`). Above 200 employees, these break
   silently: the payroll run confirmation ("Jalankan payroll … untuk N
   karyawan aktif"), the pre-run anomaly checks (missing bank account,
   expired BPJS), and the attendance employee picker
   (`Payroll.tsx:590-593,628-637,771`; `Attendance.tsx:79-82,354`).
4. **"I can't find anything in long lists."** **[COUNT]** There are 0
   sortable columns, 0 sticky table headers, 0 bulk actions, and 0
   column-visibility controls app-wide. Pagination exists on only 4 lists.
   Clients, Quotations, Agreements, and Employees have no text search on
   the list page.
5. **"It shows zeros when something is wrong."** **[LIVE]** When the
   session token is rejected (401), the client clears it but does not
   redirect. The user stays on `/payroll` looking at *0 karyawan aktif ·
   Rp 0* with a live *+ Run Payroll* button. Query errors are rendered on
   very few pages, and there is no 403 handling anywhere, so failures look
   like "no data."
6. **"Clicking a lead does nothing."** **[LIVE]** On Pipeline, the lead
   detail renders *below the whole table* (`Leads.tsx:1088`), off-screen,
   with no scroll and no URL. The floating *Tanya AEOS AI* button also
   covers the last row's stage selector.
7. **"It's slow to open."** **[LIVE+BUILD]** The whole app ships as one JS
   chunk of **2.25 MB (610 KB gzip)**, with 0 `lazy()` routes. Public pages
   like the careers portal download LiveKit, Tiptap, Recharts and
   wavesurfer too. `/overview` took **4.1 s** on a tiny dev dataset (23
   clients, 43 employees).

None of these needs a redesign. They are **targeted correctness, safety,
and data-UX fixes** on a sound base.

---

## 2. Repository & Architecture Map

| Layer | Fact |
|---|---|
| Backend | FastAPI modular monolith, Python 3.12, SQLAlchemy 2, Alembic (96 revisions + drift test `tests/test_migrations.py`), 26 modules under `backend/app/modules`, 173 GET endpoints |
| Tenancy | Shared schema, `TenantMixin` + SQLAlchemy listener auto-filter/inject `tenant_id` (`core/tenancy.py`), `TenantContextMiddleware` from JWT `tid` |
| AuthZ | `core/permissions.py` central role registry, `require_roles` (admin bypass), `require_platform_admin`, `tests/test_rbac_matrix.py` |
| Audit | `modules/audit` (`audit.log_event`), referenced from 17 services; `/audit` UI with filters, limit ≤500 |
| Money | `core/money.py` Decimal for payroll (Fase 57); **finance/accounting still use `float(` in 31 places** |
| Jobs | No queue/scheduler. Only FastAPI `BackgroundTasks` in `ai_interview`. Reminders are manual (`core/config.py:123`) |
| Frontend | React 18 + TS 5 + Vite 5 + Tailwind 3 + TanStack Query 5 + react-router 6, sonner toasts, lucide icons, Recharts, Tiptap, LiveKit, wavesurfer, react-virtuoso (Chat only) |
| Routing | `App.tsx`, flat: 9 public token/auth routes + 31 routes under `<Layout>`. All eager imports |
| Data access | `api/client.ts` thin fetch wrapper (`get/getPaged/getCursor/post/patch/put/delete/upload`); 198 `useQuery` + 213 `useMutation` written inline in pages; no per-domain hooks layer |
| Design system | CSS variables in `index.css` (`--bg`, `--text`, `--accent`, `--accent-contrast`, `--th-color`, `--cat-*`), classes `.btn/.btn-secondary/.btn-ghost/.btn-danger/.input/.card/.pill/.th/.td`, and `components/ui/*` (Button, Badge, Card, KpiCard, StatusPill, PillTabs, DonutChart, HeaderCanvas, PreflightAlert, ProgressStep, dialogToast) |
| Quality gates | CI: ruff, mypy, pytest, `tsc && vite build`, Docker builds. **No frontend tests, no ESLint**, no bundle budget |
| Mobile | Flutter staff app in `mobile/` (out of scope here) |

---

## 3. Product Surface Map

| Module | Route | Purpose | Main user | Complexity | UX risk |
|---|---|---|---|---|---|
| Overview | `/` | Cross-module KPIs, urgent actions | Owner/management | High | **High** (conflicting totals) |
| Pipeline | `/leads` | Lead table/kanban, activities, contacts, saved views, AI brief | BD | High (1594 LOC) | **High** (detail off-screen) |
| Klien | `/clients`, `/clients/:id` | Client master, sites, docs, portal access | BD/management | Medium | Medium |
| Quotation / Agreement | `/quotations`, `/agreements` | Approval → send | BD/management | Medium | Medium (one-click send/approve) |
| Suppression List | `/suppressed-contacts` | Email suppression | BD | Low | Low |
| Job Orders | `/job-orders`, `/job-orders/:id` | Requisitions, placement kanban | Recruiter | High (1249 LOC) | Medium |
| Referral | `/referral` | Referral rewards | Recruiter/finance | Low | Medium (one-click "paid") |
| Talent Pool | `/talent-pool`, `/:id` | Candidate DB, custom fields | Recruiter | High | Medium |
| AI Interview | `/ai-interview` (+ public session/recording) | Templates, invites, evidence | Recruiter | High (1463 LOC) | Medium |
| Black Lists | `/blacklist` | Banned candidates | Recruiter | Low | Low |
| Karyawan | `/employees`, `/employees/:id` | Employee master, 6 tabs (BPJS, cuti, contracts…) | HR/ops | **Very high** (2510 LOC) | High |
| Absensi | `/attendance` | Daily records, fingerprint import | HR/ops | Medium | **High** (200 cap) |
| Payment Requests | `/payment-requests` | Approval chain | Ops/finance | Medium | Medium |
| Payroll | `/payroll` | Runs, Saltab grid, BPJS, client approval | HR/ops/finance | High | **Critical** (irreversible one-click, 200 cap) |
| Finance | `/finance` | Invoices, e-Faktur, aging, forecast | Finance | High | **Critical** (draft-as-overdue, one-click faktur cancel) |
| Accounting | `/accounting` | COA, journals, 8 tabs, AI | Accountant | High | High |
| Rates | `/rates` | PPh21/BPJS/billing/bank-fee tables | Finance | Medium | Medium |
| Chat | `/chat` | Channels, @AEOS assistant | All | High (1738 LOC) | Low |
| Pages | `/pages/:id` | Notion-like docs (Tiptap) | All | Medium | Low |
| Billing / Audit / Users | `/billing`, `/audit`, `/users` | Subscription credits, audit log, user admin | Admin | Low–Medium | Medium |
| Portal Saya | `/portal-saya` | ESS: payslips, leave, overtime, selfie attendance | Employee | High (1459 LOC) | Medium (mobile-critical) |
| Platform | `/platform` | Tenant provisioning | Platform admin | Medium | Low |
| Public portals | `/careers/*`, `/onboarding/:t`, `/payroll/client/:t`, `/clients/portal/:t`, `/ai-interview/session/:t` | External candidates/clients | External | Medium | **High** (bundle weight on mobile) |
| Auth | `/login`, `/forgot-password`, `/reset-password` | — | All | Low | Low |

**Shared surfaces:** top bar (tenant switcher, ⌘K palette, period
button, credit balance, inbox, account menu), grouped sidebar with role
filtering, mobile drawer, floating *Tanya AEOS AI* button, sonner toaster.

---

## 4. Code Quality Audit

### Keep (genuinely good)
- **Type safety:** 0 `any`, 1 `as unknown as`, 0 `@ts-ignore` **[COUNT]**.
- **Comments explain *why*** (dated decisions, contrast math, RBAC
  caveats). This is rare and valuable.
- **Server state via TanStack Query** with consistent `invalidateQueries`
  (165 calls) and no hand-rolled global store.
- **Few effects:** 32 `useEffect` across 29k lines, so little
  effect-driven derived state.

### Problems

| # | Issue | Evidence | Impact |
|---|---|---|---|
| C1 | **God components** | `EmployeeDetail.tsx` 2510 LOC with 2 top-level functions, 21 queries, 25 mutations, 108 inline styles. Also `Chat.tsx` 1738, `Leads.tsx` 1594, `AIInterview.tsx` 1463, `MyPortal.tsx` 1459, `Accounting.tsx` 1377, `Payroll.tsx` 1253 | Every change risks regressions, nothing can be unit-tested, and code review is hard |
| C2 | **No data-access layer**: query keys and URLs are repeated as strings | `["me"]`/`/auth/me` declared 12×. `["employees"]` is shared by `Attendance.tsx:80` and `Payroll.tsx:591`, while `Employees.tsx:157` uses `?limit=1000`. Cache semantics depend on URL details | Silent truncation (see D1), cache collisions, duplicated fetch logic |
| C3 | **Duplicated domain types** | 240 local `interface/type` declarations. `EmployeeRow` ×4, `ClientRow` ×4, `Candidate` ×3, `AttendanceRow` ×3, `InvoiceRow` ×2 … | Drift: one page's `EmployeeRow` lacks fields another has. No single contract with the backend schema |
| C4 | **Inline styles as the theming mechanism** | 1136 `style={{…}}` across 55 files, mostly `color: "var(--text-muted)"` | Design-system changes need sweeps across 55 files (proven by the 140-instance contrast fix in Sept). Tailwind tokens `surface.*` exist in `tailwind.config.ts` but are barely used |
| C5 | **Two button systems** | `<Button>` 49 uses in 8 files vs `className="btn…"` 212 in 35 files. Text-link buttons (`Payroll.tsx:957`) are a third pattern | Inconsistent sizes and focus/disabled states |
| C6 | **Query errors mostly ignored** | Pages with `useQuery` but 0 error rendering: `ClientDetail` (8 queries), `Dashboard` (6), `Referral`, `Blacklist`, `TalentPoolDetail`, `Billing`, `Clients`, `Users`, `Audit`. Mutation `onError` only 22× vs 213 mutations | Failures look like empty data (live: zeros on 401) |
| C7 | **Mutation errors swallowed in forms** | `Clients.tsx:55-63` `createClient` has no error display. The user clicks *Simpan Klien* and nothing happens on 4xx | Lost input, duplicate retries |
| C8 | **Money as float in finance/accounting** | `float(` 31× in `finance/service.py` + `accounting/service.py`. `aging_report` returns `float(invoice.total_due)` (`finance/service.py:283`). Payroll journal sums `float(s.gross)` (`payroll/service.py:1357-1366`) | Rounding drift in journals on large runs (Fase 57 fixed payroll calc, not posting) |
| C9 | ~~N+1 in report loops~~ **(retracted)** | `Invoice.client` is already `relationship(..., lazy="selectin")` (`finance/models.py:99`), so `aging_report` does not N+1. The 4.1 s `/overview` still needs profiling (§13) | — |
| C10 | **Locale formatting scattered** | `formatRupiah` (`api/client.ts:127`) is used in 21 files, but `toLocaleString("id-ID")` appears ad hoc 16×, `Rates.tsx:199` has its own `fmt`, and backend text uses en-US `f"{x:,.0f}"` (`ai/collab.py:430` → "Rp4,357,602,000" on the Dashboard) | Mixed `4.357.602.000` / `4,357,602,000` on one screen **[LIVE]** |
| C11 | **No frontend safety net** | No ESLint (so no `react-hooks/exhaustive-deps`), no tests, no bundle budget | Regressions in 29k LOC only show up manually |

TODO/FIXME hotspots: none (0). Dead code: the header period button is a
non-functional control (see U3). The `/candidates` route only redirects.

---

## 5. Architecture Audit (Enterprise SaaS readiness)

| Capability | Status | Evidence / note |
|---|---|---|
| Multi-tenancy | **Already supported** | ORM-level auto-filtering, explicit bypass option, tenant suspension blocks login |
| Multiple organizations per user | **Requires refactor** (deliberate v1 limit) | Email globally unique (AGENTS.md); tenant switcher exists in UI |
| Role-based access | **Already supported** | `permissions.py` + matrix test; frontend nav mirrors it |
| Fine-grained permissions (per-record, per-field) | **Architecturally possible** | Roles are coarse (8 roles); ESS scoping in services. Defer until customers ask |
| Audit trail | **Partially supported** | `audit.log_event` in 17 services. Not every financial mutation is covered (e.g. faktur cancel, referral paid: verify). No before/after diff |
| Large datasets | **Partially supported** | Only 22 of 173 GET endpoints declare a bounded `limit`. `X-Total-Count` exists in 4 modules. Clients/sites/documents lists are unbounded (`clients/router.py:32,54`) |
| Financial records | **Partially supported** | Double-entry journals, auto-posting with balance guard. Float in finance/accounting. No period-close UI ("Periode akuntansi tercatat 0") |
| Reporting | **Partially supported** | Dashboard, aging, forecast. **Definitions disagree across modules** (draft-as-overdue) |
| Configurable business rules | **Partially supported** | Rates tables, custom fields, approval chain for payment requests |
| Integrations | **Partially supported** | e-Sign, payment, bank validation, Google, LiveKit adapters under `core/` |
| Background jobs | **Major gap (future)** | No queue/scheduler. Contract-expiry reminders, payslip email batches, and AI indexing all run in-request or manually. MVP-acceptable; becomes P1 at ~10 tenants |
| Notifications | **Partially supported** | In-app inbox + unread count; email sends are inline |
| AI features | **Already supported (broadly)** | RAG, forecast, lead brief, screening, interview evidence, accounting AI, chat @AEOS |
| Session security | **Partially supported** | JWT in `localStorage`, 480-min expiry (`config.py:22`), no revocation on password change (no token versioning; still open from Fase 57). **Fixed 2026-10-10**: `users.token_version` + JWT claim `tv`, bumped on change/reset/admin-set password (open WebSockets are not force-closed) |

**MVP vs future:** report-definition consistency, the 200-row truncation,
and unsafe irreversible actions are **MVP problems now**. The queue,
multi-org users, and fine-grained permissions are **future scalability**
problems and should not be built yet.

---

## 6. UI Audit (visual)

- **Layout / density:** **[LIVE]** a calm, consistent card + KPI-row + table
  rhythm. It reads like credible SaaS. KPI cards are large (≈110px tall),
  and every list page opens with 4 of them, which pushes the actual work
  surface (the table) below the fold on laptop heights (Employees table
  top ≈ 520px at 1280×717).
- **Typography:** Inter is used throughout. **Numbers are not tabular or
  right-aligned in most tables.** Employees, Leads (*Nilai Potensi*), and
  Clients left-align numbers and dates (`text-align:start`,
  `font-variant-numeric:normal` **[LIVE]**). Payroll's BPJS table *does*
  right-align (good, but inconsistent). Large KPI values overflow narrow
  cards on Finance (*Rp 10.146.592.000* touches the card edge **[LIVE]**).
- **Color:** semantic token system is solid and dark mode is carefully
  verified. Issues: the header *Saldo: Rp 0* pill with a red *Top Up* is
  a permanent alarm-colored element for admins. Red is used for both
  "deduction" (BPJS *Potongan Karyawan*) and the "Finalisasi" action, so
  danger and normal-negative share one hue.
- **Components:** inconsistent action affordances within one table row,
  e.g. Payroll *Slip Gaji* (green link) · *Generate* (grey link) ·
  *Finalisasi* (red link) · *+ Payment Request* (green link). These are
  four unequal text links with no button chrome.

---

## 7. UX Audit (IA, navigation, orientation)

| # | Route / component | Problem | Impact | Recommendation |
|---|---|---|---|---|
| U1 | Sidebar (`Layout.tsx` `NAV_ITEMS`) | Mixed-language labels: *Pipeline, Job Orders, Talent Pool, Black Lists, Suppression List, Overview* vs *Klien, Karyawan, Absensi* | Looks unfinished; harder to scan | Pick Indonesian for nav, keep industry terms (Job Order, Payroll) consistently. One terminology table in `design.md` |
| U2 | Pipeline → row click (`Leads.tsx:846,1088`) | Detail appears below the table, out of view, with no deep link | The user thinks the click failed **[LIVE]** | Right-side drawer, or route `/leads/:id` like Clients/Employees |
| U3 | Top bar period button (`Layout.tsx:522-530`) | Looks like a dropdown (chevron) but does nothing ("segera dapat difilter") while Payroll has its own numeric month/year inputs and Dashboard its own "30 hari terakhir" | Three competing time contexts, one of them fake | Remove the header control until it works. Standardize a `PeriodPicker` (month select, not `type=number`) per page |
| U4 | Top bar during load **[LIVE]** | Tenant switcher, balance pill and user name are absent until `/auth/me` resolves, so the header reflows and shows "?" / "…" | Jank on every hard load | Reserve space with skeletons |
| U5 | Detail not found (`/employees/does-not-exist`) **[LIVE]** | A single red line "Karyawan tidak ditemukan." with no back link | Dead end | Shared `NotFoundState` with a back action |
| U6 | Employees list | *Tanya Kontrak (AI)* panel sits above the KPIs, disabled-looking ("Belum ada kontrak terindeks") | AI competes with the primary task | Move into EmployeeDetail → Kontrak tab, or into ⌘K |
| U7 | Floating *Tanya AEOS AI* | Overlaps the bottom-right of every table (covers the last stage selector on Pipeline) **[LIVE]** | Blocks controls | Dock into the top bar, or add bottom padding to `<main>` |
| U8 | Login (`Login.tsx`) | "⌘ + Enter" hint on Windows. A warning-styled subscription notice is permanently visible to everyone before login | Alarm before the user has done anything | OS-aware hint. Show the notice only after a lock error |

---

## 8. Data UX Audit

**Can an accountant work here for hours? Not yet comfortably.**

| Capability | State | Evidence |
|---|---|---|
| Sorting | **Absent** | 0 `sortBy/onSort/aria-sort` **[COUNT]** |
| Sticky headers | **Absent** | `thead` position `static` **[LIVE]**; only `Layout` header is sticky |
| Search on list | Partial | Leads, Talent Pool have it. Employees, Clients (backend supports `q`!), Quotations, Agreements do not |
| Pagination | 4 lists | Employees, JobOrders, Leads, PaymentRequests (`<Pagination>`). Others load all or hit server defaults silently |
| Bulk actions / row selection | **Absent** | 0 matches |
| Column visibility / saved views | Leads only (saved views) | — |
| Export | Partial | BPJS CSV, e-Faktur QR/PDF; no generic list export |
| Numeric alignment / tabular nums | Inconsistent | See §6 |
| Currency format | Inconsistent | id-ID vs en-US on one screen **[LIVE]** |
| Dates | Inconsistent | Raw ISO `2025-03-03` (Employees *Masuk*, Clients *Akhir Kontrak*, Finance *Jatuh Tempo*) vs `toLocaleDateString("id-ID")` 13× |
| Totals/subtotals | Missing in tables | KPIs above, no footer totals on Finance invoices or BPJS recap |
| Responsive tables | Horizontal scroll only | Finance invoice table overflows **at 1280px desktop**: the *Faktur Pajak* actions are cut off **[LIVE]** |
| Large-list correctness | **Broken above 200** | D1 below |

**D1: Silent truncation (P1).** `Payroll.tsx:592` and
`Attendance.tsx:81` call `/employees` and get the backend default
`limit=200` (`hrd/router.py:76`). `Employees.tsx:157`/`Referral.tsx:84`
request 1000 (the maximum). Nothing tells the user that a list was
capped. Payroll derives *Karyawan Aktif*, the anomaly preflight, and the
run confirmation text from that capped list.

**D2: Inconsistent "overdue/outstanding" (P0 for trust).**
`finance/service.py:263-289` `aging_report` includes
`InvoiceStatus.draft`. The dashboard (`dashboard/router.py:204-213`)
excludes drafts. Live: Dashboard *Rp 4.357.602.000 / 2 overdue* vs Finance
*Rp 10.146.592.000 / 4 overdue*. The Dashboard's own *Aging Tagihan
Terlambat* widget then shows *1-30 hari Rp 5.788.990.000*, all of it from
drafts INV/2026/0002 and 0004, on the same page as the KPI that excludes
them.

---

## 9. Form UX Audit

| Form | Issue | Evidence |
|---|---|---|
| Create client | Placeholder-only labels; a required `*` in the placeholder disappears on typing; no error display; no success toast; the date input relies on its placeholder (invisible for `type=date`) | `Clients.tsx:85-95` |
| Attendance manual input | `<select>` of up to 200 employees with no search; capped | `Attendance.tsx:354` |
| Payroll period | Month as a free `type=number` (accepts 13, 0) | **[LIVE]** "8" / "2026" inputs |
| Inline-edit pattern | Leads stage `<select>` in the table row mutates on change with no undo | `Leads.tsx` table |
| Unsaved changes | No guard anywhere (0 `beforeunload/useBlocker`). Long forms in EmployeeDetail/AI Interview template | **[COUNT]** |
| Submit states | `disabled={isPending}` is common (good). Labels don't change ("Menyimpan…") | — |
| Validation | Server-side only; errors shown as raw `detail` strings where shown at all | `api/client.ts:36-40` |
| Number inputs | 91 `type="number"` and no currency input. Rupiah amounts are typed without grouping separators, so 10× errors are easy | **[COUNT]** |

**Destructive / irreversible confirmation.** `confirmToast`
(`components/ui/dialogToast.tsx:10-19`) is used in 15 files for deletes,
which is good coverage. But it is a **sonner toast with the default 4 s
auto-dismiss**, it is not modal, it does not take focus, and it sits in
the top-right corner. The irreversible actions that matter most do not
use it at all:

| Action | File:line | Reversible? |
|---|---|---|
| Finalize payroll run | `Payroll.tsx:957,969` | **No** (no reopen path; posts journal) |
| Cancel e-Faktur | `Finance.tsx:447-453` | **No** (tax-authority record) |
| Mark referral reward paid | `Referral.tsx:217` | Likely no |
| Send quotation to client | `Quotations.tsx:318` | No (external email) |
| Approve quotation / agreement | `Quotations.tsx:301`, `Agreements.tsx:319` | Workflow |
| Post journal entry | `Accounting.tsx:222` | No (posted) |
| Send payslip email | `Payroll.tsx:333`, `EmployeeDetail.tsx:1760` | No (external) |

---

## 10. Responsive Audit

| Viewport | Finding | Type |
|---|---|---|
| **Desktop 1280** | Finance invoice table wider than its card, so actions are clipped at the right **[LIVE]**. The FAB covers the last column **[LIVE]** | Workflow |
| **Tablet 820** | **Top bar is 1011px wide in an 809px header, so the whole page scrolls horizontally** **[LIVE iframe]**. The account menu is pushed off-screen. Payroll row actions are 20px tall **[LIVE]**, and *Finalisasi* sits right next to *Generate* | Workflow + safety |
| **Mobile 390** | Drawer + hamburger work **[LIVE]**. KPIs stack one per row, so the Employees table starts below the first screen. Tables are 464px in a 379px viewport (horizontal scroll, no card mode). Payroll is a single very long stacked page | UX (layout fits, workflow does not) |
| ESS (`/portal-saya`) | The most mobile-critical surface (selfie attendance, leave). Inherits the 2.25 MB bundle on mobile data **[INFERRED]** | Performance |

Responsive *layout* mostly holds. Responsive *UX* (what an HR or ops
user can actually finish on a tablet) breaks on the header and on dense
admin tables.

---

## 11. Accessibility Audit

The 2026-09-12 cycle fixed labels, contrast, and keyboard reachability of
rows across ~25 routes. This pass focuses on what that cycle did not
cover.

**P0:** none found that fully blocks usage.

**P1**
- **Modals have no dialog semantics.** The hand-rolled overlays at
  `Payroll.tsx:541`, `EmployeeDetail.tsx:1819`, `JobOrderDetail.tsx:1133,1186`
  and `MyPortal.tsx:261` have 0 `role="dialog"`, 0 `aria-modal`, no focus
  trap, and no focus return **[COUNT]**. Keyboard and screen-reader users
  tab behind the modal.
- **Destructive confirmations are an auto-dismissing toast** (4 s, no
  focus move). Screen-reader and slower users can miss the window
  (`dialogToast.tsx:15`). WCAG 2.2.1 (timing).
- **Login error is not announced.** No `role="alert"`/`aria-live` on the
  error box **[LIVE]**.

**P2**
- No skip link; one `<main>` (good) **[LIVE]**.
- Mobile drawer: hamburger has `title` only, no `aria-expanded`/`aria-controls`.
  Focus is not moved into the drawer **[LIVE]**.
- No `:focus-visible` styling defined for `.btn*` (0 `focus-visible` in
  src); it relies on browser defaults. The Chat composer uses `outline-none`
  with no replacement (`Chat.tsx:1703`).
- Touch targets under 24px: Payroll row actions 20px, *Top Up* 24px **[LIVE]**
  (WCAG 2.5.8).
- Error states rendered as red text only, without an icon.

**P3**
- No `aria-sort` (there is no sorting yet). Add it when sorting arrives.
- Toasts sit top-right, far from the triggering action.

---

## 12. Design System Audit

**Existing tokens:** `--bg, --bg-elevated, --sidebar, --hover, --border,
--text, --text-muted, --accent, --accent-tint, --accent-contrast,
--th-color, --cat-*` (light + dark). Radius default 5px (Tailwind), cards
`rounded-xl`, pills `9999px`.

**Missing tokens:** semantic status (`--success/--warning/--danger/--info`
fg/bg/border; today hardcoded in `.p-*` and Tailwind `red-600 dark:red-400`
×140), spacing/density scale, type scale (sizes hardcoded `text-xs/sm`,
`12px`), elevation (inline `boxShadow` in modals), z-index layers (z-10/20/30/40/50
ad hoc), and a numeric-figure utility (`tabular-nums` + right-align).

**Consistency matrix**

| Pattern | Implementations found | Recommendation |
|---|---|---|
| Button | `<Button>` (49), `.btn*` class (212), bare text-link `<button>` (Payroll/Finance row actions) | Canonical `<Button>` with `variant` + `size="sm"`; row actions → `<RowActions>` (icon buttons + overflow menu) |
| Status | `<StatusPill>` (4), `<Badge>` (16), raw `pill p-*` (135), Tailwind `bg-*-50` badges with no dark variant (Finance, AccountingAi) | One `<StatusPill tone>` with a status→tone map per domain |
| Dialog | 4 hand-rolled overlays, `confirmToast`, `promptToast`, CommandPalette overlay | One accessible `<Dialog>` + `<ConfirmDialog>` (no new dependency needed; a focus trap is ~40 LOC, or use native `<dialog>`) |
| Table | 57 `<table>` in 26 files with `.th/.td` classes; per-page empty rows; no sort/sticky | `<DataTable>` primitive: columns config, numeric alignment, sticky header, sort, loading/empty/error rows, optional selection |
| Loading | "Memuat…" text in 17 files; mostly nothing | `<Skeleton>` rows for tables/KPIs |
| Empty | Ad-hoc strings, sometimes wrong while loading (`Clients.tsx:163`) | `<EmptyState title action>` |
| Error | `text-red-600` paragraphs; mostly absent for queries | `<ErrorState onRetry>` + `<QueryBoundary>` wrapper |
| Period selection | Header fake button, numeric inputs (Payroll), select (Dashboard) | `<PeriodPicker>` |
| Money | `formatRupiah`, `toLocaleString`, local `fmt`, backend f-strings | `formatRupiah`/`formatDate` only; backend returns numbers, frontend formats |
| Page header | `PageHeader` (workspace.tsx) vs `HeaderCanvas` vs ad-hoc | Keep both, documented roles |
| KPI | `<KpiCard>` (60) | **Keep**. Already canonical |

---

## 13. Performance Audit

| Issue | Current impact | Future impact | Effort |
|---|---|---|---|
| One 2.25 MB / 610 KB-gzip chunk, 0 `lazy()` (`App.tsx` eager imports) | Medium (desktop), **High** (public careers/onboarding on mobile) | High | **Low**: `React.lazy` per route + `Suspense` |
| `/overview` 4.1 s on tiny data **[LIVE]** | Medium | High | Medium: profile; likely N+1 + many counts |
| Full-list fetches (clients ×7 call sites, `/employees` ×4) | Low | High | Medium (server pagination + search selects) |
| `refetchOnWindowFocus: false`, `retry: 1` globally (`App.tsx`) | Fine; stale data risk is low | — | — |
| Large tables not virtualized (only Chat uses Virtuoso) | Low | Medium (Saltab grid at 500+ employees) | Medium |

---

## 14. Security & Trust UX Audit

- **Backend is the real gate:** `require_roles` per router + matrix test.
  The frontend role checks (`Layout.tsx:310-330`, `canEdit` in 5 pages)
  only hide controls. That is correct, and the code says so in comments.
- **URL-level access:** non-authorized roles can open any route by URL.
  The page renders and its queries 403, and **no page renders 403**
  (0 handling) **[CODE]**, so the user sees empty/zero data instead of
  "you don't have access" **[INFERRED]**. Correction (Phase 0 session): the
  minted non-admin tokens failed because the server on :8000 (Docker, bound
  `0.0.0.0`) uses a different `SECRET_KEY`/database than the repo `.env`, not
  because the accounts are inactive.
- **Session expiry:** 401 clears the token but leaves the user on the page
  with zeroed KPIs and live action buttons **[LIVE]** (`api/client.ts:35`).
  It should redirect to `/login?next=`.
- **Token storage:** `localStorage` JWT with an 8 h lifetime and no
  revocation. Acceptable for MVP; P2 hardening (httpOnly cookie or token
  versioning on password change).
- **Error leakage:** backend `detail` strings are shown verbatim. Fine
  today (Indonesian business messages); make sure 500s never surface
  stack text.
- **Auditability in UI:** the `/audit` page exists, but no record page
  shows "who changed this, when." Finance users expect this on invoices
  and payroll runs.

---

## 15. AI-Native UX Audit

**Current AI surfaces:** floating *Tanya AEOS AI* (global chat), *Tanya
Kontrak (AI)* on Employees, lead AI brief, candidate AI screening
(`components/Ai.tsx`), AI Interview evidence + consistency, Accounting AI
(`AccountingAi.tsx`), revenue forecast (`ai/forecast.py`), dashboard
`ai_insight`, chat digest.

**Assessment:** AI is mostly **in-context** (good, as the 09-15 audit
said). The two weakest placements are the generic FAB, which also
overlaps data, and the *Tanya Kontrak* panel above the employee list. The
architecture (RAG module, usage metering `core/ai_usage.py`, credit
balance) can support embedded AI without feeling gimmicky.
Hard rule kept from the AI Interview roadmap: **no emotion scoring**.

---

## 16. Enterprise SaaS Gap Analysis

| NOW (before real customers) | NEXT (first 10 tenants) | LATER |
|---|---|---|
| One definition per financial metric (overdue/outstanding) | Background job queue + scheduler (reminders, email batches, indexing) | Multi-org users |
| Confirm dialog for irreversible actions | Server pagination + search on all master lists | Field-level permissions |
| No silent truncation | Record-level activity/audit timeline on invoice, payroll run, employee | Custom report builder |
| 401 → login, 403 → access state | Period close / lock in accounting UI | Public API / webhooks catalog |
| Route-level code splitting | Generic CSV export on lists | SSO/SAML |
| Consistent money/date formatting | `DataTable` with sort/sticky/totals | Inventory/purchasing (only if the market demands it) |

---

## 17. Top 20 Problems

| Rank | Area | Problem | Severity | Impact | Effort |
|---|---|---|---|---|---|
| 1 | Finance data | Aging counts drafts as overdue; Dashboard vs Finance totals disagree (`finance/service.py:267`) | **P0** | Trust in every finance number | S |
| 2 | Payroll safety | *Finalisasi* irreversible, one-click, 20px link (`Payroll.tsx:957,969`) | **P0** | Locked wrong payroll + posted journal | S |
| 3 | Finance safety | e-Faktur *Batalkan* one-click (`Finance.tsx:451`) | **P0** | Tax record cancelled by misclick | S |
| 4 | Data correctness | `/employees` capped at 200 in Payroll/Attendance; confirm text + preflight wrong | **P1** | Payroll for mid-size tenants | S–M |
| 5 | Session UX | 401 leaves user on a zeroed page with live actions (`api/client.ts:35`) | **P1** | Misleading data, failed actions | S |
| 6 | Error states | Query errors/403 render as empty data (≥9 pages with 0 error UI) | **P1** | "No data" lies | M |
| 7 | Confirm pattern | `confirmToast` auto-dismisses in 4 s, non-modal | **P1** | Missed/accidental destructive ops; a11y | S |
| 8 | A11y | Modals lack dialog semantics/focus trap (4 files) | **P1** | Keyboard/SR users | S–M |
| 9 | Performance | 2.25 MB single bundle, 0 lazy routes | **P1** | Slow public/mobile portals | S |
| 10 | Pipeline UX | Lead detail renders off-screen below table; no URL (`Leads.tsx:1088`) | **P1** | Core BD workflow | M |
| 11 | Tablet | Header overflows to 1011px at 820px viewport | **P1** | Whole app scrolls sideways on iPad | S |
| 12 | Data UX | No sort, sticky header, bulk actions anywhere | **P1** | Hours-long work sessions | L (via DataTable) |
| 13 | Formatting | Mixed id-ID/en-US Rupiah; raw ISO dates | **P2** | Polish + trust | S–M |
| 14 | Finance table | Overflows at 1280px; actions clipped | **P2** | Finance daily use | S |
| 15 | Header | Fake period dropdown; three competing period contexts | **P2** | Confusion | S |
| 16 | Forms | Placeholder-only labels, swallowed create errors (`Clients.tsx`) | **P2** | Lost input | S per form |
| 17 | Code | God components (EmployeeDetail 2510 LOC, 46 hooks) | **P2** | Velocity / regressions | L (incremental) |
| 18 | Code | No data layer: duplicated types/keys (`EmployeeRow`×4, `["me"]`×12) | **P2** | Drift, cache bugs | M |
| 19 | Backend money | Float in finance/accounting posting (31×) | **P2** | Rounding drift in journals | M |
| 20 | `/overview` | 4.1 s on tiny data; N+1 risk | **P2** | Dashboard sluggishness at scale | M |

---

## 18. Keep / Fix / Refactor / Redesign / Defer

- **KEEP:** tenancy model, RBAC registry + matrix test, audit module,
  Alembic drift test, token-based theming + dark mode, `KpiCard`,
  command palette, grouped sidebar IA, TanStack Query, strict TS,
  in-context AI placement, explanatory comments.
- **FIX:** #1–#5, #7, #11, #13–#16 (small, high-value).
- **REFACTOR:** a domain data layer (`src/api/<domain>.ts` hooks + shared
  types), `DataTable`, `Dialog/ConfirmDialog`, `QueryBoundary`, splitting
  `EmployeeDetail` by tab (one file per tab, no behavior change), and
  moving inline styles to Tailwind `surface.*` tokens opportunistically
  (only when a file is touched anyway).
- **REDESIGN:** Pipeline master-detail (drawer/route) and Payroll page
  structure (a stepper per run: Absensi → Generate → Review Saltab →
  Finalize → Payment Request, instead of five stacked sections).
- **DEFER:** queue/scheduler (until reminders become customer-visible),
  multi-org users, field-level permissions, report builder, inventory/
  purchasing, virtualization outside Chat.

---

## 19. Recommended Design Direction

- **Philosophy:** "Quiet ledger." The interface recedes; numbers, status,
  and next action lead. Every screen answers: *what needs me, how much,
  by when*.
- **Density:** two modes. *Comfortable* (current) for dashboards and
  detail pages; *compact* tables (36px rows, 13px text) for Finance,
  Payroll, Accounting, and Talent Pool. Reduce list-page KPI rows to one
  compact strip (≈64px) so the table starts above the fold.
- **Typography:** Inter with `font-feature-settings: "tnum"` for all money,
  counts and dates. Right-align numeric columns, left-align text. A
  four-step type scale (12/13/14/20, plus 28 for KPI values) as tokens.
- **Color strategy:** neutral slate surfaces; teal accent only for
  primary action and selection. Semantic status tokens are separate from
  the "negative amount" style, so red means *danger/action-required*.
  Negative money uses a minus sign plus muted red text, never the same
  red as destructive buttons.
- **Navigation:** keep the grouped sidebar. Make terminology consistent.
  Every record gets a URL (`/leads/:id`). Breadcrumb on detail pages
  (`Klien › PT X`). Remove non-functional global controls.
- **Tables:** one `DataTable`: sticky header, sort, server pagination,
  search, status filter tabs (already common), footer totals for money
  columns, a row overflow menu for secondary actions, and primary
  irreversible actions moved off the row into the record page.
- **Forms:** visible labels above fields, required marker on the label,
  inline server errors mapped to fields, a currency input with grouping,
  a month picker instead of a number input, an unsaved-changes guard on
  long forms.
- **Dashboards:** one canonical metric definition per KPI (shared backend
  function), each KPI links to the filtered list it summarizes, and
  "as-of" timestamp.
- **Responsive:** desktop-first for back office. Tablet must have no
  horizontal page scroll; tables may scroll inside their card with a
  sticky first column. Mobile is first-class only for ESS, public portals,
  approvals, and attendance. Admin tables collapse to card lists there.
- **Interaction principles:** reversible actions are immediate with an
  undo toast; irreversible actions need a modal confirm stating the
  consequence ("Payroll 8/2026 akan dikunci dan jurnal diposting. Tidak
  bisa dibatalkan."), and for payroll a typed period; every mutation
  shows success or failure.
- **AI interaction principles:** AI appears where the decision is made;
  it always shows its source records; it proposes and the human commits;
  it is metered visibly (credit balance already exists); and AI output is
  never written to financial records without an explicit user action.

---

## 20. Prioritized Roadmap

| Phase | Scope | Files | Outcome | Depends on | Risk | Effort |
|---|---|---|---|---|---|---|
| **0: Critical fixes** | Aging excludes drafts (or labels them separately) + one shared "outstanding/overdue" query used by dashboard, finance, and AI collab; `ConfirmDialog` for finalize payroll, cancel faktur, mark paid, post journal, send quotation/payslip; `/employees` callers pass explicit limits + a "list truncated" warning; 401 → redirect `/login?next=` | `finance/service.py`, `dashboard/router.py`, `ai/collab.py`, `Payroll.tsx`, `Finance.tsx`, `Referral.tsx`, `Accounting.tsx`, `Quotations.tsx`, `Attendance.tsx`, `api/client.ts`, new `components/ui/ConfirmDialog.tsx` + tests | Numbers agree; no one-click irreversible ops; no silent truncation | — | Low (behavior is narrowed, not changed) | 2–3 days |
| **1: Design system foundation** | `Dialog/ConfirmDialog` (a11y), `QueryBoundary` (loading/empty/error/403), `EmptyState`, `Skeleton`, semantic status tokens, `tabular-nums` utility, `formatRupiah/formatDate` as the only formatters; route-level `React.lazy` | `components/ui/*`, `index.css`, `App.tsx`, `api/client.ts` | Primitives exist; bundle split (target < 400 KB gzip initial) | Phase 0 dialog | Low | 3–5 days |
| **2: Core UX** | Pipeline drawer/route; Payroll run stepper; fix tablet header; remove fake period control; FAB placement; consistent nav terminology; not-found states | `Leads.tsx`, `Payroll.tsx`, `Layout.tsx` | Core workflows obvious and safe | Phase 1 | Medium (Payroll UX) | 1–2 weeks |
| **3: Data UX** | `DataTable` (sort, sticky, totals, search, server pagination) rolled out Finance → Payroll BPJS/Saltab → Employees → Clients → others; backend `limit/offset/q` + `X-Total-Count` on master lists; form labels/currency input/month picker | `components/DataTable.tsx`, 26 table files, list routers | Hours-long work sessions viable | Phase 1 | Medium (many files; do one module per PR) | 2–3 weeks |
| **4: Responsive + a11y** | Card-mode tables on mobile for ESS/approvals; drawer ARIA; focus-visible; skip link; touch targets ≥ 24px; re-run axe on new primitives | `Layout.tsx`, `MyPortal.tsx`, `index.css`, primitives | WCAG 2.2 AA on core flows; tablet usable | Phases 1–3 | Low | 1 week |
| **5: Enterprise polish** | Domain data layer (hooks + shared types), split `EmployeeDetail` by tab, `/overview` profiling + `selectinload`, Decimal in finance/accounting, record activity timeline, ESLint + a minimal Vitest setup for primitives | `src/api/*`, `EmployeeDetail.tsx`, backend services | Maintainability, speed at scale | — | Medium | 2–3 weeks, incremental |
| **6: AI-native UX** | See §15 opportunities, starting with payroll anomaly explanation and receivables collection assistant | `ai/*`, Payroll, Finance | AI where decisions happen | Phases 0–3 (correct data first) | Medium | Ongoing |

**Top 10 AI-native opportunities (by business value):**
1. **Payroll pre-finalize review**: explain deltas vs last month per
   employee (new components, tax jumps, negative net pay) in the
   Finalize confirm.
2. **Receivables collection assistant** on aging: rank overdue clients,
   draft a reminder (human sends).
3. **Invoice ↔ attendance reconciliation**: flag invoices whose billed
   headcount/hours diverge from approved attendance.
4. **Contract-expiry & BPJS compliance digest**: weekly list with proposed
   actions (needs the scheduler, Phase NEXT).
5. **Natural-language list filtering** in ⌘K ("karyawan PT X kontrak habis
   bulan depan" → filtered Employees URL).
6. **Journal suggestion from bank/payment events** (already partly in
   Accounting AI); always as a draft, never auto-posted.
7. **Quotation pricing guardrails**: margin warning from Rates + client
   history while editing.
8. **Candidate–job match explanation** in Job Order kanban (exists in
   `ai/service.py` matching; surface the reasons inline).
9. **Document understanding at upload**: extract KTP/NPWP/contract dates
   into the form for confirmation (onboarding self-service).
10. **Anomaly explanations on dashboard KPIs**: one sentence plus source
    records when a KPI moves more than X%.

---

## 21. Browser QA Findings

| # | Flow | Result |
|---|---|---|
| 1 | Authentication | Wrong password → inline error box (layout shifts down, not announced to SR). "⌘ + Enter" hint on Windows. Permanent subscription warning |
| 2 | Dashboard | Loads progressively; `/overview` 4.1 s. Urgent banner "2 invoice … (Rp4,357,602,000)" in en-US format next to id-ID figures; aging widget includes drafts (Rp 5,79 M in "1-30 hari") contradicting the KPI |
| 3 | Navigation | Sidebar grouping clear; mixed EN/ID labels; header reflows when `/auth/me` resolves |
| 4 | List/table (Employees, Leads) | No sort/sticky/search on Employees; numbers/dates left-aligned, raw ISO dates; FAB covers last column |
| 5 | Create form (Clients, code + UI) | Placeholder labels; no error feedback path |
| 6 | Edit/inline (Leads stage select) | Immediate mutation, no undo |
| 7 | Detail (Leads detail, Employee not-found) | Lead detail off-screen below table; not-found is a bare red line |
| 8 | Destructive (Payroll *Finalisasi*) | One-click irreversible (code-verified; not clicked live to preserve data) |
| 9 | Modal (Payroll slip preview, code) | No dialog semantics/focus trap |
| 10 | Responsive | Mobile 390 drawer works; KPIs push lists below fold. Tablet 820 header overflow → page h-scroll. Finance table clipped at 1280 |
| + | Session | Rejected token → zeroed Payroll page with live *+ Run Payroll*, no redirect |

Not verified live: 403 behavior per role (minted tokens were signed with
the repo `.env` secret, which the :8000 server doesn't use), dark mode (covered by the 09-12 cycle), and the public
portals (covered on 09-12; only the bundle-weight finding is new).

---

## 22. Final Assessment

AEOS has a sound architecture, a deliberate design system, and unusually
careful engineering habits. What stands between it and real business
users is a short list: **metric definitions that disagree, irreversible
financial actions without safeguards, silent list truncation, failure
states that look like "no data,"** and the missing table toolkit that
finance and HR users need for long sessions. All of these can be fixed
with the existing stack and no new framework or dependencies (a focus
trap and code splitting are built in or a few lines of code).

### AUDIT VERDICT: **NEEDS TARGETED REFACTOR**

**Why not "Ready for UI polish":** the top problems are about
correctness and safety (P0 #1–#3), not appearance, and the
missing `DataTable`/`Dialog`/`QueryBoundary` primitives mean polish
would be applied 26 times instead of once.
**Why not "Major UX redesign":** the IA, visual language, and page
patterns work. Only two flows (Pipeline master-detail, Payroll run
sequence) need structural redesign.
**Why not "Architectural rework":** tenancy, RBAC, audit, migrations,
and typing are the strongest part of the product. The gaps (queue,
pagination contract, data layer) are incremental additions.

*Stopping here. No implementation until a scope is approved.*
