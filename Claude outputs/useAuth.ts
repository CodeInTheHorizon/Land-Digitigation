import { create } from "zustand";
import type { User } from "@/types";
import { authApi } from "@/services/api";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => void;
  loadUser: () => Promise<void>;
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  isLoading: true,
  isAuthenticated: false,

  login: async (email, password) => {
    const { data } = await authApi.login(email, password);
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    const me = await authApi.me();
    set({ user: me.data, isAuthenticated: true, isLoading: false });
  },

  register: async (email, password, fullName) => {
    await authApi.register(email, password, fullName);
  },

  logout: () => {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    set({ user: null, isAuthenticated: false, isLoading: false });
  },

  loadUser: async () => {
    const token = localStorage.getItem("access_token");
    if (!token) {
      set({ isLoading: false });
      return;
    }
    try {
      const { data } = await authApi.me();
      set({ user: data, isAuthenticated: true, isLoading: false });
    } catch {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
      set({ user: null, isAuthenticated: false, isLoading: false });
    }
  },
}));
