import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const host = process.env.TAURI_DEV_HOST;

// https://vite.dev/config/
export default defineConfig(async () => ({
  base: '/',
  plugins: [
    react(),
  ],

  // Vite options tailored for Tauri development and only applied in `tauri dev` or `tauri build`
  //
  // 1. prevent Vite from obscuring rust errors
  clearScreen: false,
  // 2. tauri expects a fixed port, fail if that port is not available
  optimizeDeps: {
    exclude: ['@duckdb/duckdb-wasm'],
  },
  server: {
    port: 1420,
    strictPort: true,
    host: host || false,
    allowedHosts: ["eea.ent4i.com", "localhost"],
    // headers: {
    //   'Cross-Origin-Opener-Policy': 'same-origin',
    //   'Cross-Origin-Embedder-Policy': 'require-corp',
    // },
    hmr: host
      ? {
          protocol: "ws",
          host,
          port: 1421,
        }
      : undefined,
    watch: {
      ignored: ["**/src-tauri/**"],
    },
    proxy: {
      // All Data Agent Ragic endpoints → Rust Gateway (port 6500)
      // The gateway proxies unified_agents so frontend never talks to Python services directly.
      '/api/v1/da/ragic': {
        target: 'http://localhost:6500',
        changeOrigin: true,
      },
      // SkillsRAG → Python SkillsRAG service (port 8012)
      // Strip /skills-rag prefix since SkillsRAG routes are at root level
      // Order Secretary / 預訂購 → Rust API Gateway (port 6500)
      '/order-secretary': {
        target: 'http://localhost:6500',
        changeOrigin: true,
      },
      // SkillsRAG → Python SkillsRAG service (port 8012)
      '/skills-rag': {
        target: 'http://localhost:8012',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/skills-rag/, ''),
      },
      // All other API → Rust Gateway (port 6500)
      '/api': {
        target: 'http://localhost:6500',
        changeOrigin: true,
        rewrite: (path) => path,
      },
    },
  },
}));
