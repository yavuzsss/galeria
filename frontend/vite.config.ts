import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// In development the API runs separately (`galeria serve`); Vite proxies /api to it so the
// browser sees a single origin, exactly like the nginx setup in Docker.
const apiTarget = process.env.GALERIA_API ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": apiTarget },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
  },
});
