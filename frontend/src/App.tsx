import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Accounting from "./pages/Accounting";
import Apps from "./pages/Apps";
import Audit from "./pages/Audit";
import Candidates from "./pages/Candidates";
import Clients from "./pages/Clients";
import Dashboard from "./pages/Dashboard";
import Attendance from "./pages/Attendance";
import Chat from "./pages/Chat";
import Employees from "./pages/Employees";
import Finance from "./pages/Finance";
import ForgotPassword from "./pages/ForgotPassword";
import GovernCloudOverview from "./pages/GovernCloudOverview";
import JobOrders from "./pages/JobOrders";
import Leads from "./pages/Leads";
import Login from "./pages/Login";
import MyPortal from "./pages/MyPortal";
import PaymentRequests from "./pages/PaymentRequests";
import Payroll from "./pages/Payroll";
import PlatformTenants from "./pages/PlatformTenants";
import Rates from "./pages/Rates";
import ResetPassword from "./pages/ResetPassword";
import TalentCloudOverview from "./pages/TalentCloudOverview";
import TalentPool from "./pages/TalentPool";
import Pages from "./pages/Pages";
import RevenueCloudOverview from "./pages/RevenueCloudOverview";
import Users from "./pages/Users";
import WorkforceCloudOverview from "./pages/WorkforceCloudOverview";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/forgot-password" element={<ForgotPassword />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/apps" element={<Apps />} />
            <Route path="/talent-cloud" element={<TalentCloudOverview />} />
            <Route path="/leads" element={<Leads />} />
            <Route path="/clients" element={<Clients />} />
            <Route path="/job-orders" element={<JobOrders />} />
            <Route path="/candidates" element={<Candidates />} />
            <Route path="/talent-pool" element={<TalentPool />} />
            <Route path="/pages" element={<Pages />} />
            <Route path="/pages/:id" element={<Pages />} />
            <Route path="/workforce-cloud" element={<WorkforceCloudOverview />} />
            <Route path="/employees" element={<Employees />} />
            <Route path="/attendance" element={<Attendance />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/payment-requests" element={<PaymentRequests />} />
            <Route path="/revenue-cloud" element={<RevenueCloudOverview />} />
            <Route path="/payroll" element={<Payroll />} />
            <Route path="/finance" element={<Finance />} />
            <Route path="/govern-cloud" element={<GovernCloudOverview />} />
            <Route path="/accounting" element={<Accounting />} />
            <Route path="/rates" element={<Rates />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/users" element={<Users />} />
            <Route path="/portal-saya" element={<MyPortal />} />
            <Route path="/platform" element={<PlatformTenants />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
