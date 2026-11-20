import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { AuthProvider } from './auth'
import { registerServiceWorker } from './push'
import './styles.css'

// 提前注册通知用 Service Worker；不支持/非 HTTPS 时静默跳过
void registerServiceWorker()

// 部分浏览器不支持 WindowClient.navigate，由页面接收消息后自行跳转
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.addEventListener('message', (event: MessageEvent) => {
    const data = event.data as { type?: string; url?: string } | null
    const url = data?.url
    if (
      data?.type === 'notification-click' &&
      typeof url === 'string' &&
      url.startsWith('/') &&
      !url.startsWith('//')
    ) {
      window.location.assign(url)
    }
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
