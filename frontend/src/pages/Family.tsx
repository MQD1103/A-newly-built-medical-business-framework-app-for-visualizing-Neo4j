import { useEffect, useMemo, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  BOUNDARIES,
  BURNOUT_ITEMS,
  BURNOUT_OPTIONS,
  DAILY_RHYTHM,
  FAMILY_COURSES,
  FAMILY_FAQS,
  FAMILY_MODULES,
  SIGNAL_LEVELS,
  burnoutResult,
} from '../data/family'

type MedRow = { name: string; device: string; dose: string; time: string; left: string }

const EMPTY_MED: MedRow = { name: '', device: '', dose: '', time: '', left: '' }

const MED_STORAGE = 'xy.family.meds'
const BURNOUT_STORAGE = 'xy.family.burnout'

const MODULE_ANCHOR: Record<string, string> = {
  observe: '观察病情',
  meds: '协助用药',
  airway: '帮助排痰',
  refer: '何时送医',
  self: '照护者自己',
}

function loadMeds(): MedRow[] {
  try {
    const raw = localStorage.getItem(MED_STORAGE)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.map((item) => {
      const src = item as Record<string, unknown>
      const row: MedRow = { ...EMPTY_MED }
      for (const key of Object.keys(EMPTY_MED) as (keyof MedRow)[]) {
        const value = src[key]
        row[key] = typeof value === 'string' ? value : ''
      }
      return row
    })
  } catch {
    return []
  }
}

function loadBurnout(): number[] {
  try {
    const raw = localStorage.getItem(BURNOUT_STORAGE)
    if (!raw) return BURNOUT_ITEMS.map(() => -1)
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed) || parsed.length !== BURNOUT_ITEMS.length) {
      return BURNOUT_ITEMS.map(() => -1)
    }
    return parsed.map((v) => (typeof v === 'number' && v >= 0 && v <= 2 ? v : -1))
  } catch {
    return BURNOUT_ITEMS.map(() => -1)
  }
}

export default function Family() {
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({})
  const [activeAnchor, setActiveAnchor] = useState('observe')

  // 照护者自评
  const [answers, setAnswers] = useState<number[]>(loadBurnout)

  // 用药清单
  const [meds, setMeds] = useState<MedRow[]>(loadMeds)

  // 常见问答展开项
  const [openFaq, setOpenFaq] = useState<string | null>(null)

  useEffect(() => {
    localStorage.setItem(BURNOUT_STORAGE, JSON.stringify(answers))
  }, [answers])

  useEffect(() => {
    localStorage.setItem(MED_STORAGE, JSON.stringify(meds))
  }, [meds])

  const burnoutScore = useMemo(() => {
    if (answers.some((v) => v < 0)) return null
    return answers.reduce((a, b) => a + b, 0)
  }, [answers])

  const burnout = burnoutScore === null ? null : burnoutResult(burnoutScore)

  function jump(key: string) {
    setActiveAnchor(key)
    const el = sectionRefs.current[key]
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function updateMed(index: number, key: keyof MedRow, value: string) {
    setMeds((prev) => prev.map((row, i) => (i === index ? { ...row, [key]: value } : row)))
  }

  return (
    <div className="screen stack-gap family">
      <div className="page-title no-print">
        <div>
          <h1>家属照护专区</h1>
          <p className="sub">看得出变化 · 帮得上手 · 知道何时求助</p>
        </div>
        <Link to="/me" className="linkish">
          返回我的
        </Link>
      </div>

      <section className="family-hero">
        <span className="family-hero-emoji" aria-hidden="true">
          👨‍👩‍👧
        </span>
        <div>
          <h2>照护不是做得更多，而是做对几件事</h2>
          <p>
            会测血氧、会叩背排痰、能识别危险信号——这三件事做到位，比整天守在床边更有价值。
          </p>
        </div>
        <div className="family-hero-stats">
          <div>
            <strong>5</strong>
            <span>个主题</span>
          </div>
          <div>
            <strong>3</strong>
            <span>级预警</span>
          </div>
          <div>
            <strong>8</strong>
            <span>题自评</span>
          </div>
        </div>
      </section>

      <div className="family-anchors no-print">
        {FAMILY_MODULES.map((m) => (
          <button
            key={m.key}
            type="button"
            className={`family-anchor${activeAnchor === m.key ? ' active' : ''}`}
            onClick={() => jump(m.key)}
          >
            <span aria-hidden="true">{m.icon}</span>
            {MODULE_ANCHOR[m.key]}
          </button>
        ))}
      </div>

      {FAMILY_MODULES.map((m) => (
        <section
          key={m.key}
          className="item-card family-module"
          ref={(el) => {
            sectionRefs.current[m.key] = el
          }}
        >
          <div className="family-module-head">
            <span className="family-module-icon" aria-hidden="true">
              {m.icon}
            </span>
            <div>
              <h2>{m.title}</h2>
              <p className="family-lead">{m.lead}</p>
            </div>
          </div>

          <h3 className="family-sub">{m.todoTitle}</h3>
          <ul className="family-todo">
            {m.todo.map((item, i) => (
              <li key={item}>
                <span className="family-num">{i + 1}</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>

          <h3 className="family-sub family-sub-warn">容易做错的地方</h3>
          <ul className="family-mistakes">
            {m.mistakes.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>

          <p className="family-tip">
            <span aria-hidden="true">💡</span>
            {m.tip}
          </p>
        </section>
      ))}

      <section className="item-card family-signals">
        <div className="tk-head">
          <h2>三级预警速查</h2>
          <span className="tk-badge">贴电话旁</span>
        </div>
        <p className="muted tk-intro">
          家属最需要背下来的部分。判断只看三件事：意识、口唇颜色、能不能说完整句子。
        </p>
        {SIGNAL_LEVELS.map((lv) => (
          <div key={lv.tone} className={`family-signal tone-${lv.tone}`}>
            <div className="family-signal-top">
              <strong>{lv.label}</strong>
              <span>{lv.action}</span>
            </div>
            <ul>
              {lv.items.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ))}
        <div className="row-actions no-print">
          <button type="button" className="btn small" onClick={() => window.print()}>
            打印整份专区
          </button>
        </div>
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>一日照护节奏</h2>
          <span className="tk-badge">三次记录</span>
        </div>
        <div className="family-rhythm">
          {DAILY_RHYTHM.map((r) => (
            <div key={r.time} className="family-rhythm-item">
              <span className="family-rhythm-time">{r.time}</span>
              <div>
                <strong>{r.title}</strong>
                <ul className="tk-dot-list">
                  {r.items.map((i) => (
                    <li key={i}>{i}</li>
                  ))}
                </ul>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>哪些事家属不能自己决定</h2>
          <span className="tk-badge">边界</span>
        </div>
        <p className="muted tk-intro">
          这条边界不是不信任家属，而是这四类操作一旦判断错，代价很高。
        </p>
        <ul className="family-boundary">
          {BOUNDARIES.map((b) => (
            <li key={b.thing}>
              <span className={`family-boundary-tag tag-${b.family === '不可以' ? 'no' : b.family === '协助' ? 'half' : 'yes'}`}>
                {b.family}
              </span>
              {b.thing}
            </li>
          ))}
        </ul>
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>用药清单</h2>
          <span className="tk-badge">本地保存 · 可打印</span>
        </div>
        <p className="muted tk-intro">
          把药名、装置、剂量、时间写清楚，贴冰箱或放钱包。急诊时直接交给医生，比自己回忆可靠。
        </p>
        <div className="tk-table-wrap">
          <table className="tk-table">
            <thead>
              <tr>
                <th style={{ width: '27%' }}>药名</th>
                <th style={{ width: '23%' }}>装置</th>
                <th style={{ width: '18%' }}>剂量</th>
                <th style={{ width: '16%' }}>时间</th>
                <th style={{ width: '16%' }}>剩余</th>
                <th className="no-print" style={{ width: '40px' }}>
                  {' '}
                </th>
              </tr>
            </thead>
            <tbody>
              {meds.length === 0 ? (
                <tr>
                  <td colSpan={6} className="tk-empty">
                    还没有记录，点「添加一种药」开始。
                  </td>
                </tr>
              ) : (
                meds.map((row, index) => (
                  <tr key={index}>
                    <td>
                      <input
                        className="tk-cell"
                        value={row.name}
                        placeholder="噻托溴铵"
                        onChange={(e) => updateMed(index, 'name', e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        className="tk-cell"
                        value={row.device}
                        placeholder="都保"
                        onChange={(e) => updateMed(index, 'device', e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        className="tk-cell"
                        value={row.dose}
                        placeholder="1 吸"
                        onChange={(e) => updateMed(index, 'dose', e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        className="tk-cell"
                        value={row.time}
                        placeholder="早晚"
                        onChange={(e) => updateMed(index, 'time', e.target.value)}
                      />
                    </td>
                    <td>
                      <input
                        className="tk-cell"
                        value={row.left}
                        placeholder="30 剂"
                        onChange={(e) => updateMed(index, 'left', e.target.value)}
                      />
                    </td>
                    <td className="no-print">
                      <button
                        type="button"
                        className="tk-del"
                        aria-label="删除该行"
                        onClick={() => setMeds((prev) => prev.filter((_, i) => i !== index))}
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <div className="row-actions no-print">
          <button
            type="button"
            className="btn small primary"
            onClick={() => setMeds((prev) => [...prev, { ...EMPTY_MED }])}
          >
            添加一种药
          </button>
          <button type="button" className="btn small" onClick={() => window.print()}>
            打印
          </button>
          <button
            type="button"
            className="linkish"
            onClick={() => {
              if (window.confirm('确定清空用药清单吗？')) setMeds([])
            }}
          >
            清空
          </button>
        </div>
        <p className="meta tk-note">
          清单只保存在本机浏览器，不上传服务器。药名与剂量请照处方抄写，不要凭记忆填写。
        </p>
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>照护者疲劳自评</h2>
          <span className="tk-badge">8 题 · 每月一次</span>
        </div>
        <p className="muted tk-intro">
          回顾最近两周的真实状态，选最接近的一项。这不是诊断，只是提醒你该不该调整节奏。
        </p>
        <div className="family-burnout">
          {BURNOUT_ITEMS.map((item, index) => (
            <div key={item.text} className="family-burnout-item">
              <p>{item.text}</p>
              <div className="family-burnout-opts">
                {BURNOUT_OPTIONS.map((opt) => (
                  <button
                    key={opt.label}
                    type="button"
                    className={`family-burnout-opt${answers[index] === opt.score ? ' active' : ''}`}
                    onClick={() =>
                      setAnswers((prev) => prev.map((v, i) => (i === index ? opt.score : v)))
                    }
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
        <div className="tk-result">
          {burnoutScore === null || !burnout ? (
            <p className="meta">
              已作答 {answers.filter((v) => v >= 0).length}/{BURNOUT_ITEMS.length} 题，全部作答后显示结果。
            </p>
          ) : (
            <>
              <p className={`tk-result-title tone-${burnout.tone}`}>
                总分 {burnoutScore}/16 · {burnout.level}
              </p>
              <p className="meta">{burnout.advice}</p>
            </>
          )}
        </div>
        <div className="row-actions no-print">
          <button
            type="button"
            className="btn small"
            onClick={() => setAnswers(BURNOUT_ITEMS.map(() => -1))}
          >
            重新填写
          </button>
        </div>
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>配套课程</h2>
          <span className="tk-badge">边看边做</span>
        </div>
        <div className="family-courses">
          {FAMILY_COURSES.map((c) => (
            <Link
              key={c.title}
              to={`/courses?kw=${encodeURIComponent(c.keyword)}`}
              className="family-course"
            >
              <span className="family-course-main">
                <strong>{c.title}</strong>
                <span className="meta">{c.desc}</span>
              </span>
              <span className="chev">›</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>家属常问</h2>
          <span className="tk-badge">{FAMILY_FAQS.length} 条</span>
        </div>
        <div className="tk-faqs">
          {FAMILY_FAQS.map((f) => (
            <details
              key={f.q}
              className="tk-faq"
              open={openFaq === f.q}
              onToggle={(e) => {
                if ((e.target as HTMLDetailsElement).open) setOpenFaq(f.q)
              }}
            >
              <summary>{f.q}</summary>
              <p>{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      <p className="meta tk-foot no-print">
        本专区为健康宣教材料，不能替代医生的面诊、诊断与处方。病情判断有疑问时，优先联系主管医生或拨打 120。
      </p>
    </div>
  )
}
