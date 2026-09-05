import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  if (command === "build") {
    const backend = env.VITE_API_URL;
    // Existing same-origin Docker hosting remains supported; Vercel needs an origin.
    if (process.env.VERCEL && !backend) throw new Error("Set VITE_API_URL to the Render HTTPS origin");
    if (backend) {
      const url = new URL(backend);
      if (url.protocol !== "https:" || url.hostname === "localhost" || url.hostname === "127.0.0.1" || url.pathname !== "/" || url.search || url.hash || url.username || url.password) {
        throw new Error("VITE_API_URL must be the deployed HTTPS origin without /api/v1");
      }
    }
  }
  return {
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: process.env.VITE_API_PROXY_TARGET || "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  };
});
