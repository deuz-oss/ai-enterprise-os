import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import Accounting from "./pages/Accounting";
import Audit from "./pages/Audit";
import Candidates from "./pages/Candidates";
import Clients from "./pages/Clients";
import Dashboard from "./pages/Dashboard";
import Employees from "./pages/Employees";
import Finance from "./pages/Finance";
import JobOrders from "./pages/JobOrders";
import Leads from "./pages/Leads";
import Login from "./pages/Login";
import MyPortal from "./pages/MyPortal";
import Payroll from "./pages/Payroll";
import PlatformTenants from "./pages/PlatformTenants";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/leads" element={<Leads />} />
            <Route path="/clients" element={<Clients />} />
            <Route path="/job-orders" element={<JobOrders />} />
            <Route path="/candidates" element={<Candidates />} />
            <Route path="/employees" element={<Employees />} />
            <Route path="/payroll" element={<Payroll />} />
            <Route path="/finance" element={<Finance />} />
            <Route path="/accounting" element={<Accounting />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="/portal-saya" element={<MyPortal />} />
            <Route path="/platform" element={<PlatformTenants />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
