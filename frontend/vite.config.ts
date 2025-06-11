import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import tailwindcss from "@tailwindcss/vite";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/app/",
  resolve: {
    alias: {
      "@": path.resolve(new URL(".", import.meta.url).pathname, "./src"),
    },
  },
  server: {
    proxy: {
      // Proxy API requests to the Gemini backend server
      "/api": {
        target: "http://127.0.0.1:2024", // Gemini backend on port 2024
        changeOrigin: true,
        // Optionally rewrite path if needed (e.g., remove /api prefix if backend doesn't expect it)
        // rewrite: (path) => path.replace(/^\/api/, ''),
      },
      // Proxy assistants endpoint directly to backend
      "/assistants": {
        target: "http://127.0.0.1:2024",
        changeOrigin: true,
      },
    },
  },
});
