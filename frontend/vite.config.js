import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    chunkSizeWarningLimit: 900,
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
  optimizeDeps: {
    include: ["react-markdown", "remark-gfm"],
  },
});
