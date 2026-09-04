import axios from "axios";
import type { TokenResponse, HealthResponse } from "@/types";

const api = axios.create({
  baseURL: "/api/v1",
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
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true;
      const refresh = localStorage.getItem("refresh_token");
      if (refresh) {
        try {
          const { data } = await axios.post<TokenResponse>(
            "/api/v1/auth/refresh",
            { refresh_token: refresh },
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
  list: (params?: Record<string, unknown>) => api.get("/documents", { params }),
  get: (id: string) => api.get(`/documents/${id}`),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return api.post("/documents/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },
  process: (id: string) => api.post(`/documents/${id}/process`),
  delete: (id: string) => api.delete(`/documents/${id}`),
};

export const landRecordsApi = {
  list: (params?: Record<string, unknown>) =>
    api.get("/land-records", { params }),
  get: (id: string) => api.get(`/land-records/${id}`),
};

export const dashboardApi = {
  stats: () => api.get("/dashboard/stats"),
};

export default api;
