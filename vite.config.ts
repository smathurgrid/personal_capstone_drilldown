import path from "node:path";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitest/config";

export default defineConfig({
  root: "./frontend",
  envDir: ".",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@shared/types": path.resolve(__dirname, "packages/types/src/index.ts"),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: false,
    proxy: {
      "/api": "http://127.0.0.1:8001",
      "/uploads": "http://127.0.0.1:8001",
      "/dataset": "http://127.0.0.1:8001",
      "/static": "http://127.0.0.1:8001",
    },
  },
  test: {
    include: ["../tests/frontend/**/*.test.ts"],
    environment: "node",
  },
});
