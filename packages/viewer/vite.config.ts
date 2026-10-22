import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Single IIFE bundle with fixed names: dist/viewer.js + dist/viewer.css.
export default defineConfig(({ command }) => ({
  plugins: [react()],
  define: command === "build" ? { "process.env.NODE_ENV": JSON.stringify("production") } : {},
  build: {
    lib: {
      entry: "src/main.tsx",
      formats: ["iife"],
      name: "AgentsDiagramViewer",
      fileName: () => "viewer.js",
      cssFileName: "viewer",
    },
    cssCodeSplit: false,
    assetsInlineLimit: Number.MAX_SAFE_INTEGER,
    rollupOptions: { output: { inlineDynamicImports: true } },
  },
  test: { environment: "node" },
}));
