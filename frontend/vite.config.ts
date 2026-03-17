import path from "path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import tailwindcss from "@tailwindcss/vite";
import { visualizer } from "rollup-plugin-visualizer";

export default defineConfig(({ mode }) => ({
  base: process.env.VITE_BASE_PATH ?? "/clinic-tracker/",  // Must match GitHub repo name for project sites
  plugins: [
    react(),
    tailwindcss(),
    mode === "analyze" && visualizer({
      filename: "./dist/stats.html",
      gzipSize: true,
      brotliSize: true,
      open: true,
    }),
  ].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          "vendor-recharts": ["recharts"],
          "vendor-react": ["react", "react-dom", "react-router-dom"],
          "vendor-state": ["zustand"],
          "vendor-ui": ["axios", "sonner", "lucide-react"],
        },
      },
    },
  },
}));
