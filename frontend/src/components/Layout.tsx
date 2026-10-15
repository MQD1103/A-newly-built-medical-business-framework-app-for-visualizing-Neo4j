import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth'

const tabs = [
  { to: '/', label: '首页', icon: HomeIcon, end: true },
  { to: '/mall', label: '商城', icon: MallIcon },
  { to: '/services', label: '服务', icon: ServiceIcon },
  { to: '/community', label: '社区', icon: CommunityIcon },
  { to: '/me', label: '我的', icon: MeIcon },
]

export default function Layout() {
  const { pathname } = useLocation()
  const { user, impersonating, stopImpersonating } = useAuth()
  const hideTab =
    pathname.startsWith('/notices/') ||
    pathname.startsWith('/manage') ||
    pathname.startsWith('/admin-user')

  const mallActive =
    pathname.startsWith('/mall') ||
    pathname.startsWith('/courses') ||
    pathname.startsWith('/service-shop') ||
    pathname.startsWith('/supervision') ||
    pathname.startsWith('/materials') ||
    pathname.startsWith('/scores')

  const servicesActive =
    pathname.startsWith('/services') ||
    pathname.startsWith('/schedule') ||
    pathname.startsWith('/reminders') ||
    pathname.startsWith('/linked')

  return (
    <div className="phone-stage">
      <div className={`app-frame${hideTab ? ' no-tab' : ''}`}>
        {/* 身份切换横幅：与 hideTab 无关，任何页面都要能看到并退出 */}
        {impersonating && (
          <div className="impersonate-bar">
            <span className="impersonate-text">
              正在以「{user?.full_name ?? '该用户'}」的身份操作
            </span>
            <button
              type="button"
              className="impersonate-exit"
              onClick={() => void stopImpersonating()}
            >
              退出切换
            </button>
          </div>
        )}
        <main className="app-main">
          <Outlet />
        </main>
        {!hideTab && (
          <nav className="tabbar" aria-label="主导航">
            {tabs.map((t) => (
              <NavLink
                key={t.to}
                to={t.to}
                end={t.end}
                className={({ isActive }) => {
                  let on = isActive
                  if (t.to === '/mall') on = mallActive
                  if (t.to === '/services') on = servicesActive
                  return `tab-item${on ? ' active' : ''}`
                }}
              >
                <t.icon />
                <span>{t.label}</span>
              </NavLink>
            ))}
          </nav>
        )}
      </div>
    </div>
  )
}

function HomeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4.5 10.5 12 4l7.5 6.5V20a1 1 0 0 1-1 1h-4.5v-6h-4v6H5.5a1 1 0 0 1-1-1v-9.5Z" />
    </svg>
  )
}

function MallIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 8h12l-1 12H7L6 8Z" />
      <path d="M9 8V6.5a3 3 0 0 1 6 0V8" />
    </svg>
  )
}

function ServiceIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3.5v2.2M12 18.3v2.2M3.5 12h2.2M18.3 12h2.2M6.2 6.2l1.6 1.6M16.2 16.2l1.6 1.6M17.8 6.2l-1.6 1.6M7.8 16.2l-1.6 1.6" />
    </svg>
  )
}

function CommunityIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="9" cy="9" r="2.6" />
      <circle cx="16" cy="10.5" r="2.2" />
      <path d="M4.5 18.5c1.2-2.4 3-3.6 4.5-3.6s3.3 1.2 4.5 3.6" />
      <path d="M12.8 18.5c.7-1.6 1.9-2.5 3.2-2.5 1.4 0 2.5.9 3.3 2.5" />
    </svg>
  )
}

function MeIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="9" r="3.2" />
      <path d="M5.5 19.2c1.4-3 3.7-4.5 6.5-4.5s5.1 1.5 6.5 4.5" />
    </svg>
  )
}
