import { Link } from 'react-router-dom'

const entries = [
  {
    to: '/schedule',
    title: '课表',
    desc: '查看与课程关联的日程安排',
    tone: 'a' as const,
  },
  {
    to: '/reminders',
    title: '提醒',
    desc: '个人与管理提醒、截止倒计时',
    tone: 'b' as const,
  },
  {
    to: '/linked',
    title: '关联信息',
    desc: '家人、医院与课程关联',
    tone: 'a' as const,
  },
]

export default function Services() {
  return (
    <div className="screen stack-gap">
      <div className="page-title">
        <div>
          <h1>服务</h1>
          <p className="sub">常用服务入口</p>
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
