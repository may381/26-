import { defineConfig } from 'vite';
import uni from '@dcloudio/vite-plugin-uni';
// H5 开发时把 /api 代理到本地 P2 后端，避免跨域；小程序/App 请在 .env.local 配 VITE_API_BASE。
export default defineConfig({
  plugins: [uni()],
  server: {
    host: '0.0.0.0',
    port: 5190,
    proxy: {
      '/api': { target: 'http://127.0.0.1:8080', changeOrigin: false }
    }
  }
});
