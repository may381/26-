import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
export default defineConfig({
  plugins: [react()],
  server: {
    // Keep Anzhi separate from uni-app projects that commonly use Vite's 5173.
    port: 5174,
    strictPort: true,
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (/node_modules[\\/](react|react-dom|scheduler)[\\/]/.test(id)) return "react";
          if (/node_modules[\\/](recharts|recharts-scale|d3-[^\\/]+|victory-vendor)[\\/]/.test(id)) return "charts";
        },
      },
    },
  },
});
