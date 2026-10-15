import { Link } from 'react-router-dom'
import { useAuth } from '../auth'

const entries = [
  {
    to: '/courses',
    title: '课程',
    desc: 'COPD 系列售课，标价购买开通',
    descAdmin: 'COPD 系列课程，管理员免费开放',
    tone: 'a' as const,
  },
  {
    to: '/supervision',
    title: '监督',
    desc: '健康监督与随访提醒入口',
    descAdmin: '健康监督与随访提醒入口',
    tone: 'b' as const,
  },
  {
    to: '/service-shop',
    title: '服务',
    desc: '远程随访、康复指导等付费服务',
    descAdmin: '远程随访、康复指导，管理员免费开放',
    tone: 'a' as const,
  },
]

export default function Mall() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  return (
    <div className="screen stack-gap">
      <div className="page-title">
        <div>
          <h1>商城</h1>
          <p className="sub">
            {isAdmin ? '课程 · 监督 · 服务（管理员免费开放）' : '课程 · 监督 · 服务售卖'}
          </p>
        </div>
      </div>

      <div className="hub-grid">
        {entries.map((e) => (
          <Link key={e.to} to={e.to} className={`hub-card tone-${e.tone}`}>
            <strong>{e.title}</strong>
            <p>{isAdmin ? e.descAdmin : e.desc}</p>
            <span className="hub-go">进入 ›</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
