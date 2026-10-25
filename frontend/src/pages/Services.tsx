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
    desc: '用药、复查提醒与截止倒计时',
    tone: 'b' as const,
  },
  {
    to: '/notifications',
    title: '消息通知',
    desc: '开启手机通知，提醒直接推送到通知栏',
    tone: 'b' as const,
  },
  {
    to: '/symptom-diary',
    title: '症状日记',
    desc: '记录咳嗽、气短与痰量变化',
    tone: 'a' as const,
  },
  {
    to: '/ai-check',
    title: '用药动作检测',
    desc: '拍摄用药过程，检查步骤是否完成',
    tone: 'b' as const,
  },
  {
    to: '/hospital',
    title: '医院资料',
    desc: '授权后只读查看病情资料与医生嘱托',
    tone: 'a' as const,
  },
  {
    to: '/orders',
    title: '我的订单',
    desc: '我的课程、订单、退款与团购兑换',
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
