import { fileURLToPath } from "node:url";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL(".", import.meta.url)),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup/vitest-setup.ts"],
    include: ["tests/unit/**/*.test.{ts,tsx}", "lib/**/*.test.{ts,tsx}"],
    exclude: ["tests/e2e/**", "node_modules/**"],
  },
});
