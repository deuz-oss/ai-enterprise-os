const API_URL = import.meta.env.VITE_API_URL ?? "/api/v1";

const TOKEN_KEY = "aeos_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function rawRequest(path: string, options: RequestInit = {}): Promise<{ resp: Response; data: unknown }> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (options.body && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const resp = await fetch(`${API_URL}${path}`, { ...options, headers });
  const data = resp.status === 204 ? undefined : await resp.json().catch(() => null);
  if (!resp.ok) {
    if (resp.status === 401) clearToken();
    const detail =
      data && typeof data === "object" && "detail" in data
        ? String((data as Record<string, unknown>).detail)
        : resp.statusText;
    throw new ApiError(resp.status, detail);
  }
  return { resp, data };
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const { data } = await rawRequest(path, options);
  return data as T;
}

export interface PagedResult<T> {
  data: T[];
  total: number;
}

/** Untuk list endpoint yang kirim header `X-Total-Count` (lihat backend Batch 1c:
 * `limit`/`offset` di /candidates dan /job-orders). Total fallback ke panjang
 * array kalau header tidak ada (endpoint lama belum dipaginasi). */
async function requestPaged<T>(path: string): Promise<PagedResult<T>> {
  const { resp, data } = await rawRequest(path);
  const totalHeader = resp.headers.get("x-total-count");
  const rows = (data as T[]) ?? [];
  return { data: rows, total: totalHeader ? parseInt(totalHeader, 10) : rows.length };
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  getPaged: <T>(path: string) => requestPaged<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", body: formData }),
};

/** Unduh file (mis. CSV ekspor BPJS) dengan header auth lalu simpan via browser. */
export async function downloadFile(path: string): Promise<void> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const resp = await fetch(`${API_URL}${path}`, { headers });
  if (!resp.ok) throw new ApiError(resp.status, `Gagal mengunduh (${resp.status})`);
  const disposition = resp.headers.get("content-disposition") ?? "";
  const match = /filename="?([^";]+)"?/.exec(disposition);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = match?.[1] ?? "unduhan.csv";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function formatRupiah(value: number | null | undefined): string {
  if (value === null || value === undefined) return "-";
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 0,
  }).format(value);
}
