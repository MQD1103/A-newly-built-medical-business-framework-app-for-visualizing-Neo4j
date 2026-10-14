import { Link } from 'react-router-dom'

const entries = [
  {
    to: '/courses',
    title: '课程',
    desc: 'COPD 系列售课，标价购买开通',
    tone: 'a' as const,
  },
  {
    to: '/supervision',
    title: '监督',
    desc: '健康监督与随访提醒入口',
    tone: 'b' as const,
  },
  {
    to: '/service-shop',
    title: '服务',
    desc: '远程随访、康复指导等付费服务',
    tone: 'a' as const,
  },
]

export default function Mall() {
  return (
    <div className="screen stack-gap">
      <div className="page-title">
        <div>
          <h1>商城</h1>
          <p className="sub">课程 · 监督 · 服务售卖</p>
        </div>
      </div>

      <div className="hub-grid">
        {entries.map((e) => (
          <Link key={e.to} to={e.to} className={`hub-card tone-${e.tone}`}>
            <strong>{e.title}</strong>
            <p>{e.desc}</p>
            <span className="hub-go">进入 ›</span>
          </Link>
        ))}
      </div>
    </div>
  )
}
