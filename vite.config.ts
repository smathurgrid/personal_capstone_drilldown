import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  root: "./frontend",
  plugins: [react()],
  server: {
    port: 5174,
    strictPort: true
  }
});
