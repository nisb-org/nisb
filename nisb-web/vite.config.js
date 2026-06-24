import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: false
  },
  build: {
    // 针对你当前的环境做的优化配置
    target: 'esnext',     // 只面向现代浏览器，减少转译开销
    outDir: 'dist',
    minify: 'esbuild',    // 使用 esbuild 压缩，比 terser 快很多 [web:96][web:119]
    sourcemap: false      // 关闭生产 sourcemap，减少时间和体积 [web:98]
  }
})

