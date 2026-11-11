# AEOS — FULL PRODUCT, CODE & UI/UX AUDIT

**Date:** 2026-11-11 · **Mode:** audit only, no production code changed ·
**Predecessor:** `FULL_AUDIT-2026-10-08.md` (its Phases 0–6 and all 10 AI
opportunities were shipped). This is a fresh audit of the code as it stands at
commit `f61943a`, not a restatement of the old one. Where an old finding was
re-checked, its status is stated.

**Method.** Source read across `frontend/src` (42 pages, ~31k lines in
pages + top-level components) and `backend/app` (28 modules, ~47k lines),
pattern counts by grep and two small scripts, a production build, the
frontend test suite, and live browser QA against an **isolated** stack
(FastAPI on a scratch SQLite database + Vite, never the Docker stack on
:8000). Viewport 1280 px desktop; 390 px and 820 px through a same-origin
iframe. Seven test accounts (admin, finance, hr, operations, business_dev,
recruiter, karyawan) were created to check role behaviour.

**Evidence labels:** **[LIVE]** seen in the running app · **[API]** observed
HTTP response · **[CODE]** read in source with file:line · **[COUNT]** grep or
script count · **[INFERRED]** follows from code, not reproduced.

**Not covered in this pass (stated so nobody assumes otherwise):** dark mode,
the five public token portals, AI features that call an LLM, Chat, Leads,
Accounting and AI Interview pages in the browser (code only), real mobile
devices, PostgreSQL behaviour (QA ran on SQLite), cross-tenant isolation with
a second tenant, and load/performance at scale. Login rate limiting could not
be judged: the QA instance inherited the repo `.env`, so 7 failed logins
returning 401 proves nothing.

**Test baseline at audit time:** backend `pytest` 800 passed, 4 skipped, in
19 min 37 s locally (slow enough to discourage running it before every push);
frontend `vitest` 117 passed; `tsc && vite build` clean.

> **Status 2026-11-11 (later):** Phase 0 implemented (CHANGELOG "Audit
> 2026-11-11 Phase 0"). Top-20 #1, #2, #3, #6 and the form-reset part of #9
> are fixed: read-only lookup endpoints (`/clients/options`,
> `/clients/site-options`, `/auth/users/options`) with per-role tests, a
> global mutation error handler, readable 422 messages, Users form reset only
> on success, and production guards for `SECRET_KEY` / `ADMIN_PASSWORD`.
> Re-verified live: `finance` can pick a client and sees the rejection
> message; `recruiter` can open the Job Order form; duplicate payroll run and
> duplicate user email now show the server's message. Still open from the
> same items: the Users password field is still plain text (#9).
> **#4 fixed (same day):** `/auth/me` returns `allowed_areas` from
> `NAV_AREAS` in `core/permissions.py`; the sidebar is filtered from it and a
> forbidden route renders one "Tidak ada akses" page. A test calls each
> area's primary endpoint as every role and checks it against
> `allowed_areas`. Known gap: Overview cards still link to modules the role
> cannot open. Side finding from that test: `GET /rates/*` is readable by
> every tenant role, including `karyawan` (only writes are restricted) — not
> changed.
> **#5 fixed (same day):** base salary edit uses a formatted `CurrencyInput`
> and a confirmation showing old → new with the percentage (large changes
> warned); the backend audits `employee.salary_changed` and rejects negative
> salaries; admins/management see the change history in the Riwayat tab.
> Observed while verifying, local mode only: on SQLite, timestamps come back
> without a UTC offset and `formatDateTime` renders them as local time (7
> hours early in WIB). Columns are `DateTime(timezone=True)`, so PostgreSQL
> should be unaffected — not verified, not changed.
> **Phase 1 (2026-11-12):** `Dialog` primitive on native `<dialog>` with the
> five hand-built overlays migrated (#10), `FormField` (first use: Users
> form, password now masked — rest of #9), `PillTabs` state semantics,
> `--shadow-overlay` token, ESLint with the hooks rules in CI (0 errors, 8
> pre-existing warnings left as is). `CurrencyInput` exists from the salary
> fix. Not done from Phase 1: adopting `CurrencyInput` / `FormField` across
> the remaining forms, and z-index tokens (no longer needed for dialogs,
> which use the top layer). Phases 2–6 untouched apart from the items above.

---

## 1. Executive Summary

The October audit's problems are largely gone. Verified fixed: drafts no longer
count as overdue, irreversible actions go through a real modal
(`components/ui/ConfirmDialog.tsx`, native `<dialog>`), 401 redirects to
`/login?expired=1&next=…`, routes are code-split (initial JS 610 → 101 KB
gzip), 55 tables run on one `DataTable` with sort, sticky header and totals,
mobile and tablet no longer scroll sideways, and dates/currency have one
formatter. The architecture is sound and does not need rework.

What is left is a different class of problem. The app was built and tested
**as admin**, and it mostly reports **success paths only**.

**If AEOS launched today, users would complain about these, in this order:**

1. **"I'm the finance officer and I can't create an invoice."** **[LIVE]**
   Logged in with role `finance`, *Finance → + Generate Invoice* shows an
   empty **Klien** dropdown although two clients exist. `GET /clients` is
   restricted to `business_dev`/`management`/admin
   (`backend/app/core/permissions.py:56`), and six pages use that endpoint as
   a lookup. The same gap disables *+ Job Order Baru* for recruiters
   (`JobOrders.tsx:477`) and empties the client picker for HR/operations on
   project payroll (`Payroll.tsx:706`). Admin and management never see it.
2. **"I clicked the button and nothing happened."** **[LIVE]** *Run Payroll*
   for a period that already has a run returns 409; *Generate Invoice* for a
   period without payroll returns 422; creating a user with a duplicate email
   returns 409. In all three the screen shows nothing — and the user form
   **clears itself**, so it looks like success. A script found **108 of 223
   mutations with no failure path at all** (§4, C1).
3. **"Menu items I'm not allowed to use are all there, and the pages show
   zeros."** **[LIVE]** A finance user's sidebar lists Pipeline, Clients,
   Quotations, Agreements, Job Orders, Employees and Payroll; every one
   returns 403. `/payroll` then renders *0 karyawan aktif · 0 run tercatat*
   with a live *+ Run Payroll* button beside a "Tidak ada akses" table.
4. **"I typed one zero too many and it just saved."** **[LIVE]** Base salary
   on the employee page is a bare number field. Rp 6.600.000 became
   Rp 66.000.000 with one click: no thousands separators, no confirmation, no
   effective date, no "saved" message.
5. **"The work is below the fold."** **[LIVE]** On *Employees* the table
   starts at y = 593 px in a 585 px-high viewport, after a compliance panel,
   an AI question box, and four KPI cards.

None of this needs a redesign. Items 1–3 are each one cross-cutting fix.

---

## 2. Repository & Architecture Map

| Layer | Fact |
|---|---|
| Backend | FastAPI modular monolith, Python 3.12, SQLAlchemy 2, Alembic (102 revisions + drift test). 28 modules, 387 route handlers (401 OpenAPI paths), 83 test files |
| Tenancy | Shared schema; `TenantMixin` + ORM listener auto-filters and injects `tenant_id` (`core/tenancy.py`); explicit bypass used in 5 files (auth, bootstrap, security, billing payments, AI interview public token) |
| AuthZ | `core/permissions.py` role registry, `require_roles` (admin bypass), `require_platform_admin`, `require_active_subscription`; role matrix test |
| Sessions | JWT (480 min) in `localStorage` key `aeos_token`; token versioning revokes on password change |
| Money | `core/money.py` Decimal for payroll, invoice generation and journals. Billing wallet and several finance columns still `Mapped[float]` over `Numeric(14,2)` |
| Jobs | No queue or scheduler. `BackgroundTasks` only in `ai_interview`; renewals and digests run from external-cron endpoints (deliberate, Fase 28) |
| Payments | `core/payment` adapter: sandbox + Xendit. Xendit code carries 9 "TODO verifikasi" notes about unconfirmed API shapes (`core/payment/xendit.py:137-330`, `base.py:128-213`) |
| Frontend | React 18, TypeScript 5, Vite 5, Tailwind 3, TanStack Query 5, react-router 6, sonner, lucide, Recharts, Tiptap, LiveKit, wavesurfer, react-virtuoso |
| Routing | `App.tsx`: 11 public routes + 33 routes under `<Layout>`, all `lazy()` with a one-time reload on stale chunk |
| Data access | `api/client.ts` fetch wrapper; 197 `useQuery` + 224 `useMutation` written inline in pages. Shared hooks exist only for `useMe` and billing (`components/billing/hooks.ts`) |
| Design system | CSS variables in `index.css` + utility classes + `components/ui/*` (20 files, 1,790 lines) |
| Quality gates | CI: ruff, mypy, pytest, vitest (13 files, 117 tests — passed locally), `tsc && vite build`, agent/avatar tests, Docker builds. **No ESLint, no bundle budget.** CI installs with `npm install`, not `npm ci` (`.github/workflows/ci.yml`) |
| Other | `mobile/` Flutter staff app, `agent/`, `avatar-worker/`, `flashhead-server/` (out of scope) |

---

## 3. Product Surface Map

The product is a multi-tenant operating system for Indonesian outsourcing and
staffing firms, not a generic ERP. There is no inventory or purchasing module
and this audit does not treat that as a gap.

| Module | Route | Purpose | Main user | Complexity | UX risk |
|---|---|---|---|---|---|
| Overview | `/` | Cross-module KPIs, anomalies | Owner, management | High | Medium |
| Pipeline | `/leads` | Leads table/kanban, side panel, saved views | BD | High (1,662 LOC) | Medium |
| Clients | `/clients`, `/clients/:id` | Client master, sites, documents, portal | BD | Medium | **High** (other roles need it as a lookup) |
| Quotations / Agreements | `/quotations`, `/agreements` | Approval, pricing check, e-sign | BD, management | Medium | Medium (9 silent mutations) |
| Suppression List | `/suppressed-contacts` | Email suppression | BD | Low | Low |
| Job Orders | `/job-orders`, `/:id` | Requisitions, placement kanban, matching | Recruiter | High (1,289) | **High** (create disabled for recruiter) |
| Referrals | `/referral` | Referral rewards | Recruiter, finance | Low | Low |
| Talent Pool | `/talent-pool`, `/:id` | Candidate database | Recruiter | High | Medium |
| AI Interview | `/ai-interview` + public session | Templates, invites, evidence, voice/avatar | Recruiter | High (1,506) | Medium |
| Blacklist | `/blacklist` | Blocking check | Recruiter | Low | Low |
| Employees | `/employees`, `/:id` | Employee master, 8 tabs | HR, operations | **Very high** (2,519) | **High** (salary edit, 13 silent mutations) |
| Attendance | `/attendance` | Records, CSV import | HR, operations | Medium | Medium |
| Payroll | `/payroll` | Runs, Saltab grid, BPJS, client approval | HR, operations | High (1,491) | **High** (silent create/generate) |
| Payment Requests | `/payment-requests` | Approval chain | Ops, finance | Medium | Low |
| Finance | `/finance` | Invoices, e-Faktur, aging, forecast | Finance | High | **Critical** (role cannot invoice) |
| Accounting | `/accounting` | COA, journals, 8 tabs, bank reconciliation | Accountant | High (1,534 + 813) | Medium |
| Rates / Billing / Audit / Users | `/rates`, `/billing`, `/audit`, `/users` | Configuration, subscription, audit log, accounts | Admin, finance | Medium | Medium (Users form) |
| Chat / Pages | `/chat`, `/pages/:id` | Channels, presence, @AEOS; documents | All | High (1,794) | Medium (10 silent mutations) |
| My Portal | `/portal-saya` | ESS: payslips, leave, overtime, selfie attendance | Employee | High (1,408) | Medium |
| Platform | `/platform` | Tenant provisioning, licence, billing override | Platform admin | Medium | Medium |
| Public portals | careers, onboarding, payroll client, client portal, AI interview session | External users | External | Medium | Not re-tested |
| Auth | `/login`, `/forgot-password`, `/reset-password` | — | All | Low | Low |

Shared surfaces: top bar (tenant switcher, ⌘K palette, credit balance, inbox,
account menu), grouped sidebar, mobile drawer, floating *Tanya AEOS AI*, a
dismissible tip bar, sonner toaster, `ConfirmDialogHost`.

---

## 4. Code Quality Audit

### Keep
- **Type safety:** 0 `any`, 0 `@ts-ignore`, 0 non-null assertions on member
  access; 4 `as unknown as`, all in test seams (`lib/chat/*`) **[COUNT]**.
- **Comments record decisions and their reasons**, with dates.
- **Testable logic is being pulled out of pages:** `lib/chat/*` (7 modules,
  each with tests), `lib/billing.ts`, `components/ui/DataTable.test.ts`.
- **No TODO debt in the frontend** (1 hit, `lib/xendit.ts:6`).

### Problems

| # | Issue | Evidence | Impact |
|---|---|---|---|
| C1 | **Half the mutations have no failure path.** No `onError` in the definition, no `.error`/`.isError` read anywhere in the file, no `onError` at any call site, and no global `MutationCache` handler | **108 of 223** **[COUNT, script]**. Worst files: `EmployeeDetail.tsx` 13, `Chat.tsx` 10, `Leads.tsx` 9, `Payroll.tsx` 7 (`createRun`, `generateSlips`, `submitToClient`), `Accounting.tsx` 7 (`createEntry`, `reverseEntry`, `deleteEntry`, `reopenPeriod`), `ClientDetail.tsx` 6, `AIInterview.tsx` 6, `Agreements.tsx` 5, `PlatformTenants.tsx` 5, `Quotations.tsx` 4, `Finance.tsx` 2 (`generateInvoice`, `addCashflow`), `Users.tsx` 2. Three reproduced **[LIVE]** | Users cannot tell a rejected action from a slow one; they retry or assume success |
| C2 | **Validation errors render as `[object Object]`** | `api/client.ts:79-82` does `String(detail)`. FastAPI 422 bodies carry `detail` as a list of objects **[API]** (`/employees?limit=5000`) | Wherever an error *is* shown, schema-validation failures are unreadable |
| C3 | **Forms reset regardless of outcome** | `Users.tsx:133` calls `e.currentTarget.reset()` at submit time. **[LIVE]**: duplicate email → 409 → all three fields cleared, nothing shown | Lost input that looks like success |
| C4 | **Role model and data dependencies disagree** | `/clients` is used as a lookup in `Finance.tsx:141`, `JobOrders.tsx:253`, `JobOrderDetail.tsx:220`, `Payroll.tsx:706`, `Accounting.tsx:88`, `Dashboard.tsx:404`, but `CLIENTS_ROLES = ("business_dev", "management")`. Same for `/clients/sites` in `EmployeeDetail.tsx:433` and `/auth/users` in `Leads.tsx:323`, `JobOrderDetail.tsx:259` (admin only) | Core workflows silently unavailable to the roles they were built for (§14) |
| C5 | **God components grew** | `EmployeeDetail.tsx` 2,519 LOC (20 queries, 25 mutations); `Chat.tsx` 1,794; `Leads.tsx` 1,662; `Accounting.tsx` 1,534; `AIInterview.tsx` 1,506; `Payroll.tsx` 1,491; `MyPortal.tsx` 1,408; `JobOrderDetail.tsx` 1,289 | Review and regression cost; C1 is hardest to fix exactly here |
| C6 | **Still no data-access layer** | 308 local `interface`/`type` declarations in 81 files; query keys and URLs repeated as strings; the `["clients"]` key is shared by 6 pages with one URL (fine today, fragile) | Type drift between pages; no single place to add error handling, pagination, or role-aware lookups |
| C7 | **Inline styles remain the theming mechanism** | 1,124 `style={{…}}` in 78 files **[COUNT]** (1,136 in October) | Every token change is a sweep |
| C8 | **No linter** | No ESLint config, yet 5 `eslint-disable-next-line react-hooks/exhaustive-deps` comments exist (`Chat.tsx:503,736`, `Leads.tsx:366`, `AIInterviewRecording.tsx:104`, `TiptapEditor.tsx:59`) | Hook dependency mistakes are caught by nobody; 55 `useEffect` now (32 in October) |
| C9 | **Document numbers derived from row counts** | `finance/service.py:48-50` (`INV/{year}/{count+1}`), `:580-581` (payment requests) | Two concurrent requests compute the same number; the unique constraint turns the loser into a 500 **[INFERRED]** |
| C10 | **Wallet balance is read-modify-write on a float with no row lock** | `billing/service.py:473,491,499`; `with_for_update` appears nowhere in `backend/app` **[COUNT]**; columns typed `Mapped[float]` (`billing/models.py:223-226`) | Concurrent metered events can lose a debit or pass the insufficient-credit check twice **[INFERRED]** |
| C11 | **Input bounds missing on free-text fields** | `ClientCreate.name: str` with no `max_length`; column is `String(255)` (`clients/models.py:40`). **[LIVE]** a 400-character name and contract end date `0001-01-01` were accepted on SQLite | On PostgreSQL the same request overflows the column (a 500, not a 422) **[INFERRED]**; long unbroken text pushed every other column off the Clients table **[LIVE]** |
| C12 | **Key-by-index** | 27 `key={i|idx|index}` in 14 files **[COUNT]** | Wrong row state after reorder/delete in editable lists |

Retired from October: C8 (payroll journal floats → Decimal), C10 (locale
formatters: `toLocaleString` 16 → 7, raw `formatRupiah` now 166 uses), C11
(Vitest now in CI).

---

## 5. Architecture Audit (enterprise SaaS readiness)

| Capability | Status | Evidence / note |
|---|---|---|
| Multi-tenancy | **Already supported** | ORM-level filter; public-token lookups use `tenant_context(None)` |
| Multiple organisations per user | **Requires refactor** (deliberate v1 limit) | Email globally unique |
| Role-based access (enforcement) | **Already supported** | 403 confirmed for 5 roles across 16 endpoints **[API]**; self-deactivation blocked (422) |
| Role-based access (product fit) | **Partially supported** | Enforcement is per module; workflows cross modules (C4). No read-only lookup tier |
| Fine-grained permissions | **Architecturally possible** | 8 coarse roles. Defer |
| Audit trail | **Partially supported** | `log_event` referenced in 46 files. `/audit/logs` UI exists. Whether a base-salary change is logged was **not verified**; no per-record history on invoice or payroll run |
| Large datasets | **Partially supported** | 30 endpoints declare `limit`; **80 list endpoints return `list[...]` with no limit** **[COUNT, script]** — including `/accounting/journal` (`accounting/router.py:81`), `/finance/invoices`, `/attendance/records`, `/recruitment/placements`, `/quotations`, `/agreements`, `/notifications` |
| Financial records | **Partially supported** | Double-entry with balance guard, period close and reopen, Decimal posting. Auto-journals are best-effort (`finance/service.py:230` swallows exceptions) but a health check lists invoices without a journal (`accounting/ai_accounting.py:65-90`) |
| Reporting | **Partially supported** | Dashboard, aging, forecast, KPI anomalies; no export on most lists |
| Configurable rules | **Partially supported** | Versioned rates, custom fields, approval chains |
| Integrations | **Partially supported** | e-sign, bank validation, Google, LiveKit, payment adapter. Xendit path unverified against the real API (9 TODOs) |
| Background jobs | **Major gap (future)** | External cron hits internal endpoints with a platform-admin JWT that expires in 480 min |
| Notifications | **Partially supported** | In-app inbox; email inline |
| Subscription billing | **Partially supported** | Plans, auto-reload, receipts, dunning rules shipped (commit `062f096`); sandbox verified by the team, live gateway not |
| AI features | **Already supported** | All 10 October opportunities shipped with one pattern: deterministic findings + optional labelled AI text, never writes |

**MVP problems now:** C1, C2, C4, salary-edit safety, production config
guards (§14). **Future scalability:** unbounded lists, the job queue, the data
layer, wallet locking (becomes MVP the day commercial billing goes live).

---

## 6. UI Audit (visual)

- **Layout.** **[LIVE]** Calm and consistent: page header, KPI row, pill
  filters, one table. Reads as credible SaaS. Content is capped at 1440 px.
- **Typography.** Inter throughout; numeric columns right-aligned with
  tabular figures through `DataTable` and `.num`. Table headers are 12–13 px
  with sort affordances.
- **Colour.** Semantic tokens now exist (`--success`, `--warning`, `--danger`,
  `--danger-tint`, `--info`). 24 hardcoded `bg-{hue}-50/100` badges remain in
  10 files without dark variants **[COUNT]**.
- **Permanent alarm colour.** **[LIVE]** The top bar shows a red *Saldo: Rp 0*
  pill and a red *Top Up* button on every page, for every role, even with
  billing in internal (bypass) mode where nothing is ever charged.
- **Two page-header patterns.** **[LIVE]** Payroll and Employees open with
  "Selamat Sore, Administrator" above the title (`HeaderCanvas`); Finance,
  Clients and Users use an icon + title (`PageHeader`). A greeting is repeated
  on working pages where it carries no information.
- **Overlapping chrome.** **[LIVE]** The tip bar ("Tekan ⌘K untuk cari
  cepat…") and the floating *Tanya AEOS AI* button sit over the bottom of the
  content: they covered the inline salary editor and the Employees search box.
- **Language.** **[LIVE]** Sidebar says *Clients, Employees, Users*; the pages
  are titled *Klien, Karyawan, Pengguna*. "Payrol" and "Payroll" both appear
  (button "+ Run Payrol", title "Payroll", confirm text "Run Payroll",
  backend message "Payrol internal periode…").
- **Platform hints.** **[LIVE]** "⌘ + Enter untuk masuk" and "⌘K" are shown on
  Windows (`Login.tsx:256`, `Layout.tsx:553,794`, `CommandPalette.tsx:264`).

---

## 7. UX Audit (IA, navigation, orientation)

> Can a new business user understand where they are and what they can do?
> **As admin, yes. As any other role, not reliably.**

| # | Route / component | Problem | Impact | Recommendation |
|---|---|---|---|---|
| U1 | Sidebar `NAV_ITEMS` (`Layout.tsx:93-160`) | Eleven items have no `roles` filter (Pipeline, Clients, Quotations, Agreements, Suppression List, Job Orders, Referrals, Employees, Payroll, Finance, Accounting), so every role sees them **[LIVE as finance]** | Users explore dead ends; the product looks broken | Derive nav visibility from the same registry as the backend: expose allowed areas on `/auth/me` and filter `NAV_ITEMS` by it |
| U2 | Any page reached without permission | Page chrome renders with zero KPIs and live primary buttons; only the table area says "Tidak ada akses" **[LIVE `/payroll`, `/employees` as finance]** | Mixed message; clicking the primary button fails silently (C1) | One page-level forbidden state from the page's primary query; hide actions when it is 403 |
| U3 | Employees list | Table begins below the first screen: compliance digest, *Tanya Kontrak (AI)*, four KPIs come first **[LIVE]** (table top 593 px) | The list — the reason to open the page — needs a scroll every time | Collapse digest to one line, move the AI box into the Kontrak tab or ⌘K (open since October, U6), make KPIs a single compact strip |
| U4 | Detail pages | Back link only ("← Kembali ke Karyawan"); no breadcrumb; tabs are not in the URL **[LIVE]** | A reload or shared link loses the tab | `?tab=` param, as Leads already does for `?lead=` |
| U5 | Users page | Helper text says "lewat tombol '+ Pengguna Baru'"; the button reads "+ Buat" **[LIVE]** | Small, but it is the first admin task | Fix copy |
| U6 | Create flows | Primary button turns into a primary-styled "Tutup" while the form is open (Clients, Finance) **[LIVE]** | The most prominent control on the page now discards the form | Secondary style for "Tutup", or open the form in a panel |
| U7 | Run Payroll confirmation | Uses `confirmToast` (non-modal, top-right), which covers the balance, inbox and account menu and sits away from the form **[LIVE]** | Creating a run is consequential but is confirmed like deleting a tag | Use `confirmDialog` |

### Before / after for the major issues

**A. Cross-role lookups (C4, U1, U2)**
- *Current:* a finance officer opens Generate Invoice and gets an empty,
  required client dropdown; a recruiter finds *+ Job Order Baru* disabled.
- *Problem:* the role registry grants module access; the UI needs small
  read-only slices of other modules. Nothing reports the 403.
- *Target:* every role can pick from the reference data its own workflow
  needs, and sees only navigation it can use.
- *Implementation:* add read-only option endpoints (for example
  `GET /clients/options` → `id, name`, `GET /auth/users/options`) guarded by
  the union of roles that need them; switch the six call sites; add a
  role-matrix test case per workflow ("finance can generate an invoice"); add
  `allowed_areas` to `/auth/me` and filter the sidebar with it.

**B. Silent failures (C1–C3)**
- *Current:* the button returns to idle; nothing else changes.
- *Problem:* the user cannot distinguish "rejected", "failed" and "done".
- *Target:* every mutation ends in a visible success or a readable failure
  next to where the user acted, and never discards input on failure.
- *Implementation:* a `MutationCache({ onError })` in `App.tsx` that toasts
  `error.message` unless the mutation opts out via `meta`; format list-shaped
  `detail` in `api/client.ts` (field label + message); move form resets into
  `onSuccess`.

**C. Salary edit**
- *Current:* pencil → bare number box → *Simpan* → value replaced.
- *Problem:* no grouping separators, no review step, no effective date, on
  the number that drives payroll, BPJS and tax.
- *Target:* a formatted rupiah input, a confirmation that shows old → new and
  the percentage change, and a visible history entry.
- *Implementation:* a `CurrencyInput` built on the existing
  `parseRupiahInput`; `confirmDialog` when the change exceeds a threshold;
  show the audit entry in the *Riwayat* tab.

**D. List pages**
- *Current:* panels and KPI cards push the table off-screen.
- *Target:* table header visible without scrolling at 1280×720.
- *Implementation:* compact KPI strip (≈64 px), collapsed digest, AI entry
  point moved out of the list header.

---

## 8. Data UX Audit

> Can an accountant or HR officer work here for hours? **Closer than in
> October; reading is good, acting in bulk is not there yet.**

| Capability | State | Evidence |
|---|---|---|
| Sorting | **Present** | `DataTable` `sortValue`, `aria-sort`; 55 uses in 27 files |
| Sticky header / totals | **Present** | `DataTable.tsx:259,332` |
| Numeric alignment, currency, dates | **Mostly consistent** | Exceptions: raw ISO dates on `EmployeeDetail.tsx:856,870,937` **[LIVE]** |
| Search on list | Present on Clients, Employees, Leads, Talent Pool | **[LIVE]** |
| Pagination | Client-side in `DataTable`; server-side on 5 lists | Lookups fetch `?limit=1000` (`Leads.tsx:297`, `Quotations.tsx:90`, `Agreements.tsx:85`, `JobOrderDetail.tsx:255`, `Referral.tsx:98`, `SuppressedContacts.tsx:50`) and are silently cut at 1,000; only Employees/Attendance show a "terpotong" warning |
| Bulk actions / row selection | **Absent** | 0 checkboxes on Employees **[LIVE]** |
| Column visibility | **Absent** | — |
| Saved views | Leads only | — |
| Export | BPJS CSV, e-Faktur, receipts PDF; **no list export** on Employees, Clients, Invoices | **[LIVE]** |
| Long content | **Breaks layout** | 400-character client name widened the table until other columns left the card **[LIVE]**; no `truncate`/`max-w` on the name cell |
| Responsive tables | Card mode under 640 px; fit at 820 px | **[LIVE iframe]** |
| Status indicators | Three implementations (`pill p-*` 153 uses, `<Badge>` 24, `<StatusPill>` 5) | **[COUNT]** |

---

## 9. Form UX Audit

| Form | Finding | Evidence |
|---|---|---|
| Generate invoice (`Finance.tsx:486-560`) | Labels present. Fee is `type="number"` with no grouping. Server rejection shows nothing | **[LIVE]** |
| Run payroll (`Payroll.tsx:1190-1205`) | Toast confirmation; 409 shows nothing; year is a free number input | **[LIVE]** |
| Base salary (`EmployeeDetail.tsx`) | Unlabelled `type="number"` input (no `label`, no `aria-label`); one-click save; 10× error accepted | **[LIVE]** |
| New user (`Users.tsx:120-140`) | Placeholder-only labels ("Email *"); **password field is `type="text"`**, so the new user's password is displayed in clear and may be stored by browser autofill; native validation bubbles appear in English; form clears on failure | **[LIVE]** |
| New client (`Clients.tsx`) | Labels and required marker present (fixed since October). No length limits; no success message | **[LIVE]** |
| Login | Fields have no `autocomplete` attribute; show-password button has no accessible name | **[LIVE]** DOM read |
| Inline edit pattern | Role select on Users mutates on change with no confirmation — including changing another admin's role | **[CODE]** `Users.tsx:74` |
| Unsaved changes | No guard anywhere: 0 `beforeunload`/`useBlocker` | **[COUNT]** |
| Currency entry | 74 `type="number"` inputs; `parseRupiahInput` exists but is used only by asset disposal | **[COUNT]** |
| Success feedback | 19 `toast.success` calls in 12 files against 224 mutations | **[COUNT]** |

**Destructive and irreversible actions.** Verified in code that finalize
payroll, cancel e-Faktur, mark invoice paid, post journal and deactivate user
all use `confirmDialog`, with typed confirmation for the first two. Not on the
modal yet: *Run Payroll* (toast) and role change on Users (immediate).
Journal reversal does use `confirmDialog` with a reason field
(`Accounting.tsx:691`) and draft deletion uses a toast, which is
proportionate — but both `reverseEntry` and `deleteEntry` are in the silent
list (C1), so a rejected reversal, for example in a closed period, shows
nothing.

---

## 10. Responsive Audit

Measured through a same-origin iframe; the automation window itself cannot be
resized.

| Viewport | Finding | Type |
|---|---|---|
| **Desktop 1280** | No horizontal page scroll. Finance invoice table fits. List pages put the table below the fold (§7 U3). Floating AI button and tip bar overlap bottom content | Workflow |
| **Tablet 820** | `/payroll`, `/finance`, `/accounting`, `/leads`: document width equals viewport; header fits (was 1011 px in October); tables 777 px inside an 810 px page **[LIVE]** | Fixed |
| **Mobile 390** | Same four routes plus `/employees`: no overflow; tables switch to card lists; header fits **[LIVE]**. `/payroll` is 2,971 px tall — every section stacked on one page | Layout fits; payroll workflow is a long scroll |
| Touch targets | Sort header buttons are 16 px tall; inline-edit pencils and the sidebar "Halaman baru" button are 14×14 px **[LIVE]** | Workflow on touch |

Responsive layout now holds. The remaining gap is responsive *workflow* on
Payroll and the small targets.

---

## 11. Accessibility Audit

Code-level and DOM-level audit; axe-core was not re-run in this pass (the
October cycle ran it on 19 surfaces).

**P0:** none found.

**P1**
- **Five hand-built overlays still have no dialog semantics** — 0
  `role="dialog"`, 0 `aria-modal` in `src` **[COUNT]**; no focus trap or focus
  return: payslip preview (`EmployeeDetail.tsx:1875`, `Payroll.tsx:659`),
  terminal-stage dialog and its sibling (`JobOrderDetail.tsx:1173,1226`),
  selfie capture (`MyPortal.tsx:262`), and the command palette
  (`CommandPalette.tsx:190`). Keyboard focus can move behind them.
- **Failures are not perceivable by anyone** for 108 mutations (C1); for
  screen-reader users even the idle button is no signal.

**P2**
- **Target size (WCAG 2.5.8):** sort buttons 16 px high; pencil buttons
  14×14; "Halaman baru" 14×14 **[LIVE]**.
- **State by colour only:** `PillTabs` marks the active filter with
  background colour and nothing else — no `aria-pressed`, `aria-current` or
  tab roles (`components/ui/PillTabs.tsx:24-31`).
- **Unlabelled controls:** inline salary input; login show-password button
  **[LIVE]**; Users form relies on placeholders.
- **Confirmation by toast** for Run Payroll: not modal, focus is not moved.
- **`outline-none`** in 5 files (6 uses) — verify each has a visible
  replacement.

**P3**
- Native validation messages in English inside an Indonesian UI.
- 14 px icon buttons expose their name through `title` only.

Verified good: skip link present, single `<main>`, `ConfirmDialog` is a real
modal with labelled title and safe default focus, `ErrorState` uses
`role="alert"`, table rows are keyboard reachable.

---

## 12. Design System Audit

**Existing tokens (`index.css`):** `--bg`, `--bg-elevated`, `--sidebar`,
`--hover`, `--border`, `--text`, `--text-muted`, `--th-color`, `--accent`,
`--accent-tint`, `--accent-contrast`, `--success`, `--warning`, `--danger`,
`--danger-tint`, `--info`, `--cat-crm|recruitment|workforce|finance|administration`.

**Existing classes:** `.btn`, `.btn-secondary`, `.btn-ghost`, `.btn-danger`,
`.input`, `.card`, `.pill` + `.p-{gray,green,red,yellow,orange,blue,indigo,violet}`,
`.badge`, `.th`, `.td`, `.num`.

**Existing components:** Button, Badge, StatusPill, Card, KpiCard, PillTabs,
DataTable, Pagination, PeriodPicker, ConfirmDialog, dialogToast, states
(Skeleton, EmptyState, ErrorState, QueryState, TableStateRow,
DetailLoadState), PageFallback, HeaderCanvas, PreflightAlert, ProgressStep,
DonutChart, BlacklistBadge.

**Missing tokens:** type scale, spacing/density scale, elevation (the same
`boxShadow: "0 12px 40px rgba(15,15,15,0.25)"` is inlined in 6 overlays),
z-index layers (z-10/30/40/50 chosen ad hoc), tint pairs for
success/warning/info (only danger has one).

**Missing components:** `Dialog` (general modal; only the confirm variant
exists), `CurrencyInput`, `FormField` (label + control + error), `RowActions`,
`ForbiddenPage`, `Tabs` with semantics.

**Consistency matrix**

| Pattern | Implementations found | Recommendation |
|---|---|---|
| Button | `<Button>` 66 uses / 15 files; `.btn*` classes 233 / 40 files | Keep both, but one source of truth: `<Button>` should render the `.btn*` classes; migrate when a file is touched |
| Status | `pill p-*` 153; `<Badge>` 24; `<StatusPill>` 5; raw `bg-*-50` 24 | One `<StatusPill tone>` with a domain status→tone map |
| Modal | `ConfirmDialog` (native), `ReminderDraftDialog` (native), 5 hand-built overlays, sonner confirm/prompt toasts (19 + 6 uses) | One `Dialog` on native `<dialog>`; toasts only for non-consequential confirms |
| Table | `DataTable` 55; raw `<table>` 8 in 6 files (documented exceptions) | **Keep** — converged |
| Loading / empty / error | `states.tsx` in 14 files; "Memuat…" text still in 17 | Finish adoption |
| Page header | `HeaderCanvas` (greeting) vs `PageHeader` (icon) | Greeting on Overview only; `PageHeader` everywhere else |
| Period selection | `PeriodPicker` exists; Payroll header still uses select + free year input | Adopt `PeriodPicker` |
| Money input | 74 `type="number"`; 1 parser | `CurrencyInput` |
| Filter tabs | `PillTabs` | Keep; add state semantics |
| KPI | `KpiCard` | **Keep** |

---

## 13. Performance Audit

Build measured locally (`npm run build`, 19 s).

| Issue | Current impact | Future impact | Effort |
|---|---|---|---|
| Entry chunk 330 KB (101 KB gzip) | Low | Low | — (fixed since October) |
| `AIInterviewSession` 584 KB (155 KB gzip) on a **public, mobile** route (LiveKit) | Medium for candidates on mobile data | Medium | S–M: load LiveKit only when the voice call starts |
| `Dashboard` 380 KB (112 KB gzip) — Recharts on the landing page | Low–Medium | Medium | S: lazy-load chart panels |
| `Pages` 320 KB (97 KB gzip) — Tiptap | Low (only on that route) | Low | — |
| `/overview`: 125 ms cold, 42 ms warm on a small dataset **[API]** | None | Unknown at scale | — |
| 80 unbounded list endpoints; six `?limit=1000` lookups | None today | **High** for ledgers, attendance and invoices after a year of data | M per module |
| `/accounting/journal` filters with `extract(year|month)` (`accounting/service.py:332-334`) | None | Medium — defeats a date index | S: date range predicate |
| Non-virtualised tables (Saltab grid) | Low | Medium at 500+ employees | M |
| No bundle budget in CI | — | Regression risk | S |

---

## 14. Security & Trust UX Audit

- **Backend is the gate, and it holds.** 403 returned consistently for five
  non-admin roles across 16 endpoints; a tenant admin cannot deactivate
  themself **[API]**. Frontend role checks only hide controls, as the code
  comments say.
- **The gate is stricter than the workflows (C4).** This is a product
  failure, not a leak — but it will push teams to hand out `management` or
  `admin` to get work done, which *is* a security outcome.
- **Client-side visibility is wrong in the other direction (U1/U2).**
  Forbidden areas are shown and render with zeros.
- **Production fails open on configuration.** `core/config.py:22` defaults
  `secret_key` to `"dev-secret-key-change-me"` and `:27` defaults
  `admin_password` to `"admin1234"`; nothing refuses to start when
  `APP_ENV=production` and either is still the default **[CODE]**. A missing
  env var would mean forgeable tokens or a known admin password.
- **No security headers.** `deploy/Caddyfile` and `frontend/nginx.conf` set no
  `Content-Security-Policy`, `Strict-Transport-Security`, `X-Frame-Options` or
  `X-Content-Type-Options` **[CODE]**. With the session token in
  `localStorage`, any script injection reads it; a CSP is the cheap mitigation.
- **Passwords shown in clear** in the New user form (§9). Admin-set passwords
  have no forced change on first login **[not verified in backend]**.
- **Chat WebSocket authenticates with the JWT in the query string**
  (`chat/router.py:19`) — common, but it puts tokens in proxy access logs.
- **Xendit webhook** verifies a header token (`billing/router.py:363-372`);
  the adapter's assumptions about Xendit's API are explicitly unverified.
- **Uploads** are read fully into memory (`await file.read()` in 17 places);
  only nginx's 25 MB cap bounds them.
- **Session expiry UX:** fixed (redirect with `next`, open-redirect guard in
  `safeNextPath`).

---

## 15. AI-Native UX Audit

**State.** AI is embedded where decisions happen, which is the hard part and
it is done: payroll pre-finalise review inside the confirm dialog, receivables
reminder drafts, invoice↔attendance reconciliation, quotation margin check,
match-score reasons, KPI change explanations, bank-statement suggestions,
weekly compliance digest, natural-language ⌘K filters, KTP/NPWP reading in
onboarding. One pattern throughout: deterministic findings first, optional
labelled AI text, never writes or sends. Usage is metered (`core/ai_usage.py`).
The hard rule against emotion scoring in interviews is kept.

**Weak spots.** *Tanya Kontrak (AI)* still occupies the top of the Employees
list and looks disabled when nothing is indexed **[LIVE]**. The floating
button overlaps content. The credit pill presents AI cost as a permanent
alarm.

**Ten opportunities for the next round** (recommendations; none were found
already built in the surfaces inspected):

1. **Month-end close assistant** — turn the existing accounting health check
   (unposted memorials, invoices/payment requests without journals,
   unreconciled bank lines) into an ordered checklist with one-click
   navigation; AI only summarises.
2. **"Why can't I?" explanations** — when an action is rejected (no payroll
   for the period, run already exists, period closed), show the rule and the
   next step. Deterministic; fixes the worst UX gap and is the natural home
   for a short AI sentence.
3. **Attendance import triage** — flag duplicates, impossible hours and
   missing employees in the CSV before it is applied.
4. **Salary and component change review** — on any pay change, show the
   effect on take-home, BPJS and PPh 21 before saving.
5. **Client-facing payroll summary** — a plain-language variance note for the
   client approval portal, drafted from the run's deltas.
6. **Contract renewal drafts** — from the compliance digest, prepare the
   extension document for HR to review and send to e-sign.
7. **Stale-lead next action** — rank leads by inactivity and value; draft the
   follow-up for the owner.
8. **Payslip Q&A in My Portal** — answer "why is my deduction higher?" from
   the employee's own slip components only.
9. **e-Faktur pre-check** — NPWP format, DPP/PPN consistency and missing
   buyer data before submission, with an explanation.
10. **Audit-log question answering** — "who changed this employee's salary
    and when", restricted to audit readers.

---

## 16. Enterprise SaaS Gap Analysis

| NOW (before real customers) | NEXT (first 10 tenants) | LATER |
|---|---|---|
| Every role can complete its own workflow (lookup endpoints + matrix test) | Server pagination + search on ledgers, invoices, attendance, placements | Multi-organisation users |
| Every mutation reports success or failure; readable validation errors | Job queue/scheduler replacing cron + platform-admin JWT | Field-level permissions |
| Navigation and page actions match permissions | Bulk actions and CSV export on master lists | Report builder |
| Guarded edits on pay and other money fields; currency input | Record-level history on invoice, payroll run, employee | SSO/SAML |
| Production refuses default secret/admin password; security headers | Wallet debit under row lock, Decimal throughout; sequence-based document numbers | Public API and webhook catalogue |
| Xendit adapter verified against the live sandbox before commercial billing | Data-access layer + ESLint; split the 1,500+ line pages | Saved views and column visibility everywhere |

---

## 17. Top 20 Problems

| Rank | Area | Problem | Severity | Impact | Effort |
|---|---|---|---|---|---|
| 1 | Roles × workflows | `finance` cannot generate invoices, `recruiter` cannot create job orders, HR/ops cannot pick a client for project payroll: `/clients` lookup is 403 for them (`permissions.py:56`; `Finance.tsx:141`, `JobOrders.tsx:253,477`, `Payroll.tsx:706`) | **P0** | Core workflow blocked for every non-admin, non-management role | S–M |
| 2 | Feedback | 108 of 223 mutations have no failure path; Run Payroll, Generate Invoice and Create User fail silently | **P1** | Retries, duplicates, false sense of success | S (global handler) + M (review) |
| 3 | Feedback | 422 validation errors display as `[object Object]` (`api/client.ts:79-82`) | **P1** | Unreadable errors where errors exist | S |
| 4 | Permissions UX | Sidebar shows forbidden modules; forbidden pages render zeros and live buttons (`Layout.tsx:93-160`) | **P1** | Product looks broken to most roles | M |
| 5 | Data safety | Base salary: bare number input, one-click save, 10× accepted, no confirmation or feedback (`EmployeeDetail.tsx`) | **P1** | Wrong pay, BPJS and tax | S–M |
| 6 | Config | No startup guard against default `SECRET_KEY` / `admin1234` in production (`core/config.py:22,27`) | **P1** | Total compromise on one missing env var | S |
| 7 | Billing integrity | Wallet balance: float arithmetic, no row lock (`billing/service.py:473-499`) | **P1** when commercial billing is on | Lost or double debits | M |
| 8 | Billing readiness | Xendit adapter rests on 9 unverified API assumptions (`core/payment/xendit.py`) | **P1** before go-live | Payments or webhooks may not work | M |
| 9 | Forms | Users form clears on failure; password in clear text; placeholder labels (`Users.tsx:120-140`) | **P2** | Lost input; credential exposure | S |
| 10 | A11y | Five overlays without dialog semantics or focus management | **P2** | Keyboard and screen-reader users | S–M |
| 11 | Scale | 80 list endpoints unbounded; six lookups capped at 1,000 with no warning | **P2** | Slow pages, then silently missing rows | M per module |
| 12 | Validation | No length/date bounds on client fields; 400-char name accepted and breaks the table | **P2** | 500s on PostgreSQL; layout breakage | S |
| 13 | Security | No CSP/HSTS/frame/nosniff headers; JWT in `localStorage` | **P2** | XSS impact is full session theft | S |
| 14 | List UX | Work surface below the fold on Employees | **P2** | Daily friction | S |
| 15 | Safety | Run Payroll is confirmed by a toast and user role change is immediate; neither uses `confirmDialog` | **P2** | Mis-clicks on consequential actions | S |
| 16 | Integrity | Count-based invoice and payment-request numbers (`finance/service.py:48,580`) | **P2** | Collisions → 500 under concurrency | S–M |
| 17 | Maintainability | Eight pages over 1,200 LOC; no data layer; no ESLint | **P2** | Velocity; C1 lives here | L, incremental |
| 18 | A11y | Targets under 24 px (sort buttons, pencils); `PillTabs` state by colour only; unlabelled inputs | **P2** | Touch and assistive-tech use | S |
| 19 | Data UX | No bulk actions, list export, column visibility, or unsaved-changes guard | **P2** | Long-session efficiency | M–L |
| 20 | Polish | Mixed English/Indonesian labels, "Payrol"/"Payroll", ⌘ hints on Windows, raw ISO dates on employee detail, permanent red credit pill, overlapping tip bar and AI button | **P3** | Perceived quality | S |

Priority = user impact × business risk × frequency × technical risk. Items
7–8 rank below 1–6 only because commercial billing is not yet live.

---

## 18. Keep / Fix / Refactor / Redesign / Defer

- **KEEP:** tenancy model; role registry and matrix test; Alembic drift test;
  Decimal money core; `DataTable`, `ConfirmDialog`, `states.tsx`, `KpiCard`;
  token theming; route splitting; the deterministic-first AI pattern;
  explanatory comments; grouped sidebar.
- **FIX:** #1–#6, #9, #12–#16, #18, #20.
- **REFACTOR:** a thin data-access layer per domain (hooks + shared types +
  role-aware lookups), started with `clients` because it unlocks #1; a general
  `Dialog`; `CurrencyInput` and `FormField`; split `EmployeeDetail` by tab;
  wallet debit under lock with Decimal columns; ESLint with the hooks plugin.
- **REDESIGN:** nothing wholesale. Two bounded redesigns: list-page header
  density (KPI strip) and the permission experience (navigation + forbidden
  page).
- **DEFER:** job queue (until cron becomes an operational burden),
  multi-organisation users, field-level permissions, report builder, table
  virtualisation, inventory/purchasing.

---

## 19. Recommended Design Direction

- **Philosophy:** keep "quiet ledger" — numbers, status and next action lead.
  Add one rule: **the system always answers.** Every action ends in a visible
  result, and every refusal says why and what to do next.
- **Density:** comfortable for dashboards and detail pages; compact for
  ledgers (36 px rows, 13 px text). On list pages the table header must be
  visible at 1280×720 without scrolling.
- **Typography:** Inter, tabular figures for all quantities; define a
  four-step scale as tokens (12/13/14/20, 28 for KPI values).
- **Colour:** teal for primary action and selection only. Red means "act now"
  — never a resting state such as a zero balance. Complete the tint pairs for
  success, warning and info.
- **Navigation:** sidebar derived from permissions; one language for labels
  and page titles (Indonesian, with industry terms such as Payroll and Job
  Order kept); every record and tab addressable by URL; breadcrumbs on detail
  pages.
- **Tables:** `DataTable` everywhere; next capabilities in order — server
  pagination, row selection with bulk actions, CSV export, column visibility.
  Truncate long text with a tooltip.
- **Forms:** visible labels, required marker on the label, field-level server
  errors, `CurrencyInput` for every rupiah amount, review step for pay and
  tax fields, unsaved-changes guard on long forms, input preserved on failure.
- **Dashboards:** each KPI links to the filtered list it summarises and shows
  an as-of time.
- **Responsive:** desktop-first for the back office; no page-level horizontal
  scroll at any width (holds today); mobile is first-class for ESS, approvals
  and public portals; 24 px minimum targets, 44 px in ESS.
- **Interaction:** reversible actions are immediate with a confirmation toast
  that offers undo; consequential actions use the modal with the consequence
  spelled out; irreversible ones add typed confirmation.
- **AI interaction:** appears at the decision point, shows its source records,
  proposes while the human commits, is labelled, never writes to financial
  records, and is metered without alarm.

---

## 20. Prioritized Roadmap

Effort assumes one engineer familiar with the codebase.

| Phase | Scope | Files / components | Expected outcome | Depends on | Risk | Effort |
|---|---|---|---|---|---|---|
| **0 — Critical fixes** | Lookup endpoints for clients (and users, sites) with the right roles + role-workflow tests; global mutation error handler; readable 422s; form resets only on success; production config guard | `clients/router.py`, `auth/router.py`, `core/permissions.py`, `tests/test_rbac_matrix.py`; `Finance.tsx`, `JobOrders.tsx`, `JobOrderDetail.tsx`, `Payroll.tsx`, `Accounting.tsx`, `EmployeeDetail.tsx`, `Leads.tsx`; `App.tsx`, `api/client.ts`, `Users.tsx`; `core/config.py` | Every role completes its workflow; no silent failures | — | Low. The handler may double-report where a page already toasts — add a `meta` opt-out | 3–4 days |
| **1 — Design system foundation** | General `Dialog` (migrate 5 overlays); `CurrencyInput`; `FormField`; `ForbiddenPage`; `PillTabs` semantics; `<Button>` as the single button source; elevation and z-index tokens; ESLint with hooks plugin (warnings first) | `components/ui/*`, `index.css`, `EmployeeDetail.tsx`, `Payroll.tsx`, `JobOrderDetail.tsx`, `MyPortal.tsx`, `CommandPalette.tsx`, `package.json`, CI | Primitives for Phases 2–4 | Phase 0 | Low | 4–6 days |
| **2 — Core UX** | Permission-aware navigation (`allowed_areas` on `/auth/me`); page-level forbidden state; guarded salary and pay edits; `confirmDialog` for Run Payroll and role change; tab state in URL; list-page header density | `auth/schemas.py`, `Layout.tsx`, `EmployeeDetail.tsx`, `Payroll.tsx`, `Accounting.tsx`, `Users.tsx`, `Employees.tsx` | Non-admin roles get a coherent product; pay edits are safe | Phases 0–1 | Medium (navigation touches every role — test each) | 1–1.5 weeks |
| **3 — Data UX** | Server pagination + search on journal, invoices, attendance, placements, quotations, agreements; replace `?limit=1000` lookups with search selects; bulk selection and CSV export in `DataTable`; long-text truncation; input bounds in schemas | 6–8 routers and services, `DataTable.tsx`, list pages, `*/schemas.py` | Lists stay correct and fast as data grows | Phase 1 | Medium (one module per PR) | 2–3 weeks |
| **4 — Responsive + accessibility** | 24 px targets; labels on inline editors and Users form; `autocomplete` on login; axe re-run on new primitives and on interactive states; Payroll mobile flow by step | `DataTable.tsx`, `EmployeeDetail.tsx`, `Users.tsx`, `Login.tsx`, `Payroll.tsx` | WCAG 2.2 AA on core flows including dialogs | Phases 1–2 | Low | 1 week |
| **5 — Enterprise polish** | Security headers (CSP in report-only first); wallet debit under lock + Decimal columns (migration); sequence-based document numbers; Xendit verification against the real sandbox; lazy LiveKit and charts; bundle budget; terminology pass; OS-aware shortcut hints; split `EmployeeDetail` by tab; domain hooks | `deploy/Caddyfile`, `nginx.conf`, `billing/*`, `finance/service.py`, `core/payment/xendit.py`, `AIInterviewSession.tsx`, `Dashboard.tsx`, `Layout.tsx`, `Login.tsx` | Ready for commercial billing and outside scrutiny | — (parallel) | Medium (billing migration; CSP can break inline styles — report-only first) | 2–3 weeks |
| **6 — AI-native UX** | §15 in order: rejection explanations (#2), month-end close assistant (#1), pay-change review (#4), attendance import triage (#3) | `ai/*`, `accounting/ai_accounting.py`, Payroll, Finance, Attendance | AI that removes steps from real workflows | Phases 0–3 (correct, complete data first) | Medium | Ongoing, one feature at a time |

---

## 21. Browser QA Findings

Isolated stack, scratch database, seeded with 2 clients, 6 employees, 3 leads
and one October payroll run. All test data lives in the scratch directory.

| # | Flow | Result |
|---|---|---|
| 1 | Authentication | Wrong password → inline error. Correct login → Overview. "⌘ + Enter" hint on Windows; subscription notice permanently visible; inputs lack `autocomplete`; show-password button unnamed |
| 2 | Dashboard | Loads cleanly; clear hierarchy (one hero card, supporting cards). Outstanding card uses a warning icon at Rp 0. Tip bar overlaps the lower content |
| 3 | Navigation | Grouped sidebar clear. English labels vs Indonesian page titles. As `finance`: 7 visible modules that all return 403 |
| 4 | List/table (Clients, Employees) | Sort, search, sticky header, formatted dates, right-aligned numbers all work. Employees table starts at 593 px. No selection or export |
| 5 | Create form (Clients) | Labels and required marker present. 400-character name + year-0001 date accepted; table layout broke; no success message |
| 6 | Create form (Users) | Short password → native English bubble. Duplicate email → 409, **nothing shown, form cleared**. Password typed in clear text |
| 7 | Create (Finance → Generate Invoice) | As admin, period without payroll → 422, **nothing shown**. As `finance` → **client dropdown empty** |
| 8 | Create (Payroll → Run Payroll) | Existing period → toast confirmation → 409, **nothing shown** |
| 9 | Detail (Employee) | Clean summary with per-field edit. Raw ISO dates. Tabs not in URL |
| 10 | Edit (base salary) | 6.600.000 → 66.000.000 saved in one click, no confirmation, no feedback |
| 11 | Reversible action (Kunci Payroll) | Immediate, state badge appears, undo available — appropriate |
| 12 | Destructive / modal | `ConfirmDialog` verified in code as a true modal; the Run Payroll path showed the toast variant live. Five hand-built overlays lack dialog semantics (code) |
| 13 | Permission states | `/payroll` and `/employees` as `finance`: "Tidak ada akses" in tables, zeros in header and KPIs, primary buttons enabled |
| 14 | Responsive | 390 px and 820 px: no horizontal scroll on 5 routes, card-mode tables on mobile, header fits |

One screenshot timed out right after login; the page itself was responsive
(checked by script), so this is treated as an automation artefact, not a
product issue.

---

## 22. Final Assessment

AEOS has moved from "correct but unsafe" to "safe for an admin on the happy
path." The foundations — tenancy, enforcement, money handling, the table and
dialog primitives, the AI pattern — are in better shape than most products at
this stage. What blocks a launch to real teams is narrower and more
embarrassing than anything architectural: people who are not admins cannot
finish their jobs, and the interface does not tell anyone when something
fails. Both come from testing as one role and coding the success path, and
both are fixable in days because the fixes are cross-cutting.

### AUDIT VERDICT: **NEEDS TARGETED REFACTOR**

**Why not "Ready for UI polish":** the top six problems are functional — a
blocked workflow per role, silent failures, unsafe pay edits, fail-open
production config. Polishing first would decorate screens that some roles
cannot use.

**Why not "Needs major UX redesign":** information architecture, page
patterns, tables, dialogs and responsive behaviour all work. The two
redesigns proposed are bounded (list header density, permission experience).

**Why not "Needs architectural rework":** nothing structural is wrong. The
required changes are a lookup tier on top of the existing role registry, one
global error handler, a handful of primitives, and a locking fix in billing.

*Stopping here. No implementation until a scope is approved.*
