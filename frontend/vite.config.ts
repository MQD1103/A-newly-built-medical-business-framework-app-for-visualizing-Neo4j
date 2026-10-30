import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  // 未配置 VITE_API_BASE 时，代理到本机后端；团队可改 .env
  const backend = (env.VITE_API_BASE || 'http://127.0.0.1:8001').replace(/\/$/, '')

  return {
    plugins: [react()],
    server: {
      // 默认本机；每人各自启动，不依赖别人的电脑
      host: '127.0.0.1',
      port: 5174,
      strictPort: true,
      proxy: {
        '/api': {
          target: backend,
          changeOrigin: true,
        },
        '/uploads': {
          target: backend,
          changeOrigin: true,
        },
      },
    },
  }
})
