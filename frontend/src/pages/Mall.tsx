import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

/** 简洁线性图标（统一蓝色描边，保持页面干净） */
function IconBook() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path
        d="M4 5.5A1.5 1.5 0 0 1 5.5 4H10a2.5 2.5 0 0 1 2 1 2.5 2.5 0 0 1 2-1h4.5A1.5 1.5 0 0 1 20 5.5v11a1.5 1.5 0 0 1-1.5 1.5H14a2.5 2.5 0 0 0-2 1 2.5 2.5 0 0 0-2-1H5.5A1.5 1.5 0 0 1 4 16.5Zm8 1.8v11.7"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function IconMonitor() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path
        d="M12 3l7 3v5c0 4.5-3 8-7 10-4-2-7-5.5-7-10V6Zm-3 9l2.2 2.2L15.5 10"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function IconService() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" aria-hidden="true">
      <path
        d="M5 3v6a5 5 0 0 0 10 0V3M10 14v2a5 5 0 0 0 5 5 5 5 0 0 0 5-5v-1.5M20 12.5a1.5 1.5 0 1 0 .01 0M5 3H3.5M15 3h1.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

const entries = [
  {
    to: '/courses',
    title: '课程',
    desc: 'COPD 系列售课，标价购买开通',
    descAdmin: 'COPD 系列课程，管理员免费开放',
    meta: 'system',
    Icon: IconBook,
  },
  {
    to: '/supervision',
    title: '监督',
    desc: '健康监督与随访提醒入口',
    descAdmin: '健康监督与随访提醒入口',
    meta: 'monitor',
    Icon: IconMonitor,
  },
  {
    to: '/service-shop',
    title: '服务',
    desc: '远程随访、康复指导等付费服务',
    descAdmin: '远程随访、康复指导，管理员免费开放',
    meta: 'service',
    Icon: IconService,
  },
]

const features = [
  {
    title: '内容专业',
    desc: '课程由医护团队整理，围绕 COPD 全程管理编排，循序渐进。',
  },
  {
    title: '学习灵活',
    desc: '视频课程随时观看，进度自动保存，复习巩固不受时间限制。',
  },
  {
    title: '服务贴心',
    desc: '配套健康监督与随访提醒，帮助您把康复计划坚持下来。',
  },
]

export default function Mall() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [courseCount, setCourseCount] = useState<number | null>(null)

  useEffect(() => {
    let cancelled = false
    api<{ id: number }[]>('/api/courses')
      .then((list) => {
        if (!cancelled) setCourseCount(list.length)
      })
      .catch(() => {
        /* 商城首页静默处理，课程数仅作展示 */
      })
    return () => {
      cancelled = true
    }
  }, [])

  const entryMeta: Record<string, string> = {
    system: courseCount != null ? `共 ${courseCount} 门` : '系列课程',
    monitor: '随访提醒',
    service: '按需选购',
  }

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

      <section className="mall-hero">
        <h2>专业守护，每一次呼吸</h2>
        <p>
          {isAdmin
            ? '管理员模式下所有课程与服务免费开放，可进入各板块查看详情。'
            : '从认识 COPD 到康复训练、营养与疫苗防护，一站式获取系统课程与健康服务。'}
        </p>
        <div className="mall-hero-stats">
          <div>
            <strong>{courseCount != null ? courseCount : '—'}</strong>
            <span>系列课程</span>
          </div>
          <div>
            <strong>3</strong>
            <span>服务板块</span>
          </div>
          <div>
            <strong>7×24</strong>
            <span>随时回看</span>
          </div>
        </div>
      </section>

      <div className="mall-section-label">选择板块</div>
      <div className="hub-grid">
        {entries.map((e) => (
          <Link key={e.to} to={e.to} className={`hub-card tone-${e.meta === 'monitor' ? 'b' : 'a'}`}>
            <div className="hub-card-top">
              <span className="hub-card-icon">
                <e.Icon />
              </span>
              <strong>{e.title}</strong>
              <span className="hub-card-tag">{entryMeta[e.meta]}</span>
            </div>
            <p>{isAdmin ? e.descAdmin : e.desc}</p>
            <span className="hub-go">进入 ›</span>
          </Link>
        ))}
      </div>

      <div className="mall-section-label">为什么选择小医商城</div>
      <section className="mall-features">
        {features.map((f) => (
          <div key={f.title} className="mall-feature">
            <strong>{f.title}</strong>
            <p>{f.desc}</p>
          </div>
        ))}
      </section>

      <p className="mall-footnote">
        所有课程均为虚拟内容，购买后即可在线观看；支付流程为演示环境模拟，不产生真实扣费。
      </p>
    </div>
  )
}
