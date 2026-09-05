import axios from "axios";
import type { TokenResponse, HealthResponse, Document, DocumentPage, ExtractionResult, LandRecord, PaginatedResponse } from "@/types";

const apiBaseURL = `${(import.meta.env.VITE_API_URL || "").replace(/\/+$/, "")}/api/v1`;
const requestTimeout = 60000;

const api = axios.create({
  baseURL: apiBaseURL,
  timeout: requestTimeout,
  headers: { "Content-Type": "application/json" },
});

// ---------- JWT interceptor ----------

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("access_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && original && !original._retry) {
      original._retry = true;
      const refresh = localStorage.getItem("refresh_token");
      if (refresh) {
        try {
          const { data } = await axios.post<TokenResponse>(
            `${apiBaseURL}/auth/refresh`,
            { refresh_token: refresh },
            { timeout: requestTimeout },
          );
          localStorage.setItem("access_token", data.access_token);
          localStorage.setItem("refresh_token", data.refresh_token);
          original.headers.Authorization = `Bearer ${data.access_token}`;
          return api(original);
        } catch {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/login";
        }
      }
    }
    if (!error.response) {
      error.message = error.code === "ECONNABORTED"
        ? "The request timed out. Check document status before retrying an upload or processing request."
        : "Cannot reach the server. Please check your connection and try again.";
    } else if (error.response.status >= 500) {
      error.message = "The server is temporarily unavailable. Please try again shortly.";
    }
    return Promise.reject(error);
  },
);

// ---------- API methods ----------

export const authApi = {
  login: (email: string, password: string) =>
    api.post<TokenResponse>("/auth/login", { email, password }),
  register: (email: string, password: string, full_name: string) =>
    api.post("/auth/register", { email, password, full_name }),
  refresh: (refresh_token: string) =>
    api.post<TokenResponse>("/auth/refresh", { refresh_token }),
  me: () => api.get("/auth/me"),
};

export const healthApi = {
  check: () => api.get<HealthResponse>("/health"),
};

export const documentsApi = {
  list: (params?: Record<string, unknown>) => api.get<PaginatedResponse<Document>>("/documents", { params }),
  get: (id: string) => api.get<Document>(`/documents/${id}`),
  pages: (id: string) => api.get<DocumentPage[]>(`/documents/${id}/pages`),
  extraction: (id: string) => api.get<ExtractionResult>(`/extraction/${id}`),
  review: (id: string, land_record_id: string, fields: Record<string, string>) => api.post(`/extraction/${id}/review`, { land_record_id, actions: Object.entries(fields).map(([field_name, new_value]) => ({ field_name, action: "edit", new_value })) }),
  upload: (file: File, language?: string) => {
    const form = new FormData();
    form.append("file", file);
    // Optional hint only; the pipeline detects language automatically when omitted.
    if (language) form.append("language", language);
    return api.post<Document>("/documents/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  process: (id: string) => api.post(`/documents/${id}/process`),
  delete: (id: string) => api.delete(`/documents/${id}`),
};

export const landRecordsApi = {
  list: (params?: Record<string, unknown>) =>
    api.get<PaginatedResponse<LandRecord>>("/land-records", { params }),
  get: (id: string) => api.get<LandRecord>(`/land-records/${id}`),
};

export const dashboardApi = {
  stats: () => api.get("/dashboard/stats"),
};

export const exportApi = { download: (format: "csv" | "json" | "xlsx") => api.get(`/exports/land-records/${format}`, { responseType: "blob" }) };

export default api;
