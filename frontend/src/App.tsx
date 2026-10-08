import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, type ComponentType } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { ApiError } from "./api/client";
import Layout from "./components/Layout";
import { PageFallback } from "./components/ui/PageFallback";
import Login from "./pages/Login";

// Code splitting per route (audit 2026-10-08 §13): dulu semua halaman satu
// chunk 2,25 MB, termasuk portal publik (karier, onboarding) yang ikut
// mengunduh LiveKit/Tiptap/Recharts. Layout & Login tetap eager (shell/entry);
// Suspense untuk halaman internal ada di Layout supaya sidebar tidak berkedip.

/** `lazy()` + satu kali reload otomatis kalau chunk gagal dimuat -- terjadi di
 * tab yang masih terbuka saat deploy baru menghapus chunk lama (hash berubah). */
function lazyPage<T extends ComponentType<object>>(load: () => Promise<{ default: T }>) {
  return lazy(() =>
    load()
      .then((mod) => {
        sessionStorage.removeItem("aeos_chunk_reload");
        return mod;
      })
      .catch((err: unknown) => {
        if (!sessionStorage.getItem("aeos_chunk_reload")) {
          sessionStorage.setItem("aeos_chunk_reload", "1");
          window.location.reload();
        }
        throw err;
      })
  );
}
const Accounting = lazyPage(() => import("./pages/Accounting"));
const Agreements = lazyPage(() => import("./pages/Agreements"));
const AIInterview = lazyPage(() => import("./pages/AIInterview"));
const AIInterviewSession = lazyPage(() => import("./pages/AIInterviewSession"));
const Audit = lazyPage(() => import("./pages/Audit"));
const Billing = lazyPage(() => import("./pages/Billing"));
const Blacklist = lazyPage(() => import("./pages/Blacklist"));
const Clients = lazyPage(() => import("./pages/Clients"));
const ClientDetail = lazyPage(() => import("./pages/ClientDetail"));
const Dashboard = lazyPage(() => import("./pages/Dashboard"));
const Attendance = lazyPage(() => import("./pages/Attendance"));
const CareerDetail = lazyPage(() => import("./pages/CareerPortal").then((m) => ({ default: m.CareerDetail })));
const CareerListing = lazyPage(() => import("./pages/CareerPortal").then((m) => ({ default: m.CareerListing })));
const CareerTrack = lazyPage(() => import("./pages/CareerPortal").then((m) => ({ default: m.CareerTrack })));
const PayrollClientPortal = lazyPage(() => import("./pages/PayrollClientPortal"));
const ClientPortal = lazyPage(() => import("./pages/ClientPortal"));
const Chat = lazyPage(() => import("./pages/Chat"));
const Employees = lazyPage(() => import("./pages/Employees"));
const EmployeeDetail = lazyPage(() => import("./pages/EmployeeDetail"));
const Finance = lazyPage(() => import("./pages/Finance"));
const ForgotPassword = lazyPage(() => import("./pages/ForgotPassword"));
const JobOrderDetail = lazyPage(() => import("./pages/JobOrderDetail"));
const OnboardingSelfService = lazyPage(() => import("./pages/OnboardingSelfService"));
const JobOrders = lazyPage(() => import("./pages/JobOrders"));
const Leads = lazyPage(() => import("./pages/Leads"));
const MyPortal = lazyPage(() => import("./pages/MyPortal"));
const PaymentRequests = lazyPage(() => import("./pages/PaymentRequests"));
const Payroll = lazyPage(() => import("./pages/Payroll"));
const PlatformTenants = lazyPage(() => import("./pages/PlatformTenants"));
const Quotations = lazyPage(() => import("./pages/Quotations"));
const Rates = lazyPage(() => import("./pages/Rates"));
const Referral = lazyPage(() => import("./pages/Referral"));
const ResetPassword = lazyPage(() => import("./pages/ResetPassword"));
const SuppressedContacts = lazyPage(() => import("./pages/SuppressedContacts"));
const TalentPool = lazyPage(() => import("./pages/TalentPool"));
const TalentPoolDetail = lazyPage(() => import("./pages/TalentPoolDetail"));
const Pages = lazyPage(() => import("./pages/Pages"));
const Users = lazyPage(() => import("./pages/Users"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // 4xx (403 role, 404, 422) tidak akan berubah kalau diulang -- langsung
      // tampilkan error-nya. Retry sekali hanya untuk jaringan/5xx.
      retry: (failureCount, error) =>
        !(error instanceof ApiError && error.status >= 400 && error.status < 500) && failureCount < 1,
      refetchOnWindowFocus: false,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense fallback={<PageFallback fullScreen />}>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route path="/careers/track" element={<CareerTrack />} />
          <Route path="/careers/track/:token" element={<CareerTrack />} />
          <Route path="/careers/:tenantSlug/:jobId" element={<CareerDetail />} />
          <Route path="/careers/:tenantSlug" element={<CareerListing />} />
          <Route path="/payroll/client/:token" element={<PayrollClientPortal />} />
          <Route path="/clients/portal/:token" element={<ClientPortal />} />
          <Route path="/onboarding/:token" element={<OnboardingSelfService />} />
          <Route path="/ai-interview/session/:token" element={<AIInterviewSession />} />
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/leads" element={<Leads />} />
            <Route path="/clients" element={<Clients />} />
            <Route path="/clients/:id" element={<ClientDetail />} />
            <Route path="/quotations" element={<Quotations />} />
            <Route path="/agreements" element={<Agreements />} />
            <Route path="/suppressed-contacts" element={<SuppressedContacts />} />
            <Route path="/job-orders" element={<JobOrders />} />
            <Route path="/job-orders/:id" element={<JobOrderDetail />} />
            <Route path="/candidates" element={<Navigate to="/talent-pool" replace />} />
            <Route path="/referral" element={<Referral />} />
            <Route path="/talent-pool" element={<TalentPool />} />
            <Route path="/talent-pool/:id" element={<TalentPoolDetail />} />
            <Route path="/ai-interview" element={<AIInterview />} />
            <Route path="/blacklist" element={<Blacklist />} />
            <Route path="/pages" element={<Pages />} />
            <Route path="/pages/:id" element={<Pages />} />
            <Route path="/employees" element={<Employees />} />
            <Route path="/employees/:id" element={<EmployeeDetail />} />
            <Route path="/attendance" element={<Attendance />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/payment-requests" element={<PaymentRequests />} />
            <Route path="/payroll" element={<Payroll />} />
            <Route path="/finance" element={<Finance />} />
            <Route path="/accounting" element={<Accounting />} />
            <Route path="/rates" element={<Rates />} />
            <Route path="/billing" element={<Billing />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/users" element={<Users />} />
            <Route path="/portal-saya" element={<MyPortal />} />
            <Route path="/platform" element={<PlatformTenants />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
