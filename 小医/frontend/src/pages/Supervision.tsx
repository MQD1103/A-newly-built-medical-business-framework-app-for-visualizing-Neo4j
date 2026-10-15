import { Link } from 'react-router-dom'

const items = [
  {
    title: '症状日记',
    desc: '记录咳嗽、气促与痰量变化（后续接入）',
  },
  {
    title: '用药打卡',
    desc: '吸入装置与用药依从性监督（后续接入）',
  },
  {
    title: '随访提醒',
    desc: '复诊与检查节点提醒，可联动提醒页',
  },
]

export default function Supervision() {
  return (
    <div className="screen stack-gap">
      <Link to="/mall" className="back-link">
        ← 返回商城
      </Link>
      <div className="page-title">
        <div>
          <h1>监督</h1>
          <p className="sub">COPD 健康监督 · 逐步完善</p>
        </div>
      </div>

      <ul className="list-card">
        {items.map((it) => (
          <li key={it.title}>
            <h3>{it.title}</h3>
            <p className="meta">{it.desc}</p>
          </li>
        ))}
      </ul>

      <p className="muted">
        需要日程提醒时可前往{' '}
        <Link to="/reminders" style={{ color: '#2f74c8' }}>
          提醒
        </Link>
      </p>
    </div>
  )
}
