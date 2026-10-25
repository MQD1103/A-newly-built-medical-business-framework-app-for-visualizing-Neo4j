/* 小医 Service Worker
 * 只负责手机通知：接收推送、点击回到前端。
 * 不做页面缓存，避免开发期和版本更新时出现旧资源。
 */

self.addEventListener('install', () => {
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    data = { body: event.data ? event.data.text() : '' }
  }

  const title = typeof data.title === 'string' && data.title ? data.title : '小医提醒'
  const options = {
    body: typeof data.body === 'string' ? data.body : '',
    icon: typeof data.icon === 'string' ? data.icon : '/icon-192.png',
    badge: '/icon-192.png',
    lang: 'zh-CN',
    data: {
      url: typeof data.url === 'string' && data.url.startsWith('/') ? data.url : '/notifications',
    },
  }
  if (typeof data.tag === 'string' && data.tag) {
    options.tag = data.tag
    options.renotify = true
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const rawUrl = event.notification.data && event.notification.data.url
  const path = typeof rawUrl === 'string' && rawUrl.startsWith('/') ? rawUrl : '/notifications'
  const target = new URL(path, self.location.origin)

  event.waitUntil(
    (async () => {
      const windowClients = await self.clients.matchAll({
        type: 'window',
        includeUncontrolled: true,
      })
      for (const client of windowClients) {
        if (new URL(client.url).origin !== self.location.origin) continue
        try {
          await client.focus()
        } catch {
          /* 忽略聚焦失败，继续尝试导航 */
        }
        if ('navigate' in client) {
          try {
            await client.navigate(target.href)
            return
          } catch {
            /* 某些浏览器不支持 navigate，退回到消息通知 */
          }
        }
        client.postMessage({ type: 'notification-click', url: target.pathname + target.search })
        return
      }
      await self.clients.openWindow(target.href)
    })(),
  )
})
