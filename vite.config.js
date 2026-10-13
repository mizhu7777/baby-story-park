import { defineConfig } from 'vite'

// 相对基路径，方便部署到 GitHub Pages 等子目录（https://<user>.github.io/<repo>/）
export default defineConfig({
  base: './',
  build: {
    target: 'es2019',
    assetsDir: 'assets',
  },
  server: {
    host: true,
    port: 5173,
  },
})
