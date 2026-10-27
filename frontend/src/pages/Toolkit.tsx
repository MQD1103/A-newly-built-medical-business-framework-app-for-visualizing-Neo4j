import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  CASES,
  CAT_ITEMS,
  EMERGENCY_PREP,
  EMERGENCY_SIGNALS,
  EMERGENCY_STEPS,
  FAMILY_GUIDE,
  FAQS,
  MMRC_LEVELS,
  MYTHS,
  RECORD_SHEETS,
  VIDEO_ITEMS,
  catGrade,
  type RecordSheet,
} from '../data/toolkit'

type TabKey = 'assess' | 'records' | 'handbook' | 'media' | 'family' | 'faq' | 'cases'

const TABS: { key: TabKey; label: string }[] = [
  { key: 'assess', label: '评估量表' },
  { key: 'records', label: '记录表' },
  { key: 'handbook', label: '应急手册' },
  { key: 'media', label: '视频图文' },
  { key: 'family', label: '家属专区' },
  { key: 'faq', label: '常见问答' },
  { key: 'cases', label: '案例分享' },
]

type Row = Record<string, string>

/** 空表常量：避免每次渲染都产生新数组，让 rows 引用保持稳定 */
const EMPTY_ROWS: Row[] = []

function storageKey(key: string): string {
  return `xy.toolkit.${key}`
}

function loadRows(key: string, columns: string[]): Row[] {
  try {
    const raw = localStorage.getItem(storageKey(key))
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.map((item) => {
      const row: Row = {}
      for (const col of columns) {
        const value = (item as Record<string, unknown>)[col]
        row[col] = typeof value === 'string' ? value : ''
      }
      return row
    })
  } catch {
    return []
  }
}

function today(): string {
  const d = new Date()
  return `${d.getMonth() + 1}/${d.getDate()}`
}

function emptyRow(sheet: RecordSheet): Row {
  const row: Row = {}
  for (const col of sheet.columns) row[col.key] = ''
  row.date = today()
  return row
}

export default function Toolkit() {
  const [tab, setTab] = useState<TabKey>('assess')

  // 评估量表
  const [mmrc, setMmrc] = useState<number | null>(null)
  const [cat, setCat] = useState<number[]>(() => CAT_ITEMS.map(() => -1))

  // 记录表
  const [sheetIndex, setSheetIndex] = useState(0)
  const sheet = RECORD_SHEETS[sheetIndex]
  const [records, setRecords] = useState<Record<string, Row[]>>(() => {
    const map: Record<string, Row[]> = {}
    for (const s of RECORD_SHEETS) {
      map[s.key] = loadRows(s.key, s.columns.map((c) => c.key))
    }
    return map
  })
  const rows = records[sheet.key] ?? EMPTY_ROWS

  function setRows(updater: Row[] | ((prev: Row[]) => Row[])) {
    setRecords((prev) => {
      const current = prev[sheet.key] ?? EMPTY_ROWS
      return {
        ...prev,
        [sheet.key]: typeof updater === 'function' ? updater(current) : updater,
      }
    })
  }

  // 问答
  const [faqKeyword, setFaqKeyword] = useState('')
  const [openFaq, setOpenFaq] = useState<string | null>(null)

  useEffect(() => {
    localStorage.setItem(storageKey(sheet.key), JSON.stringify(rows))
  }, [rows, sheet.key])

  const catScore = useMemo(() => {
    if (cat.some((v) => v < 0)) return null
    return cat.reduce((a, b) => a + b, 0)
  }, [cat])

  const catResult = catScore === null ? null : catGrade(catScore)

  const mmrcLevel = mmrc === null ? null : MMRC_LEVELS[mmrc]

  const filteredFaqs = useMemo(() => {
    const kw = faqKeyword.trim()
    if (!kw) return FAQS
    return FAQS.filter((f) => `${f.q}${f.a}${f.tag}`.includes(kw))
  }, [faqKeyword])

  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [tab])

  function updateCell(index: number, key: string, value: string) {
    setRows((prev) =>
      prev.map((row, i) => (i === index ? { ...row, [key]: value } : row)),
    )
  }

  function addRow() {
    setRows((prev) => [...prev, emptyRow(sheet)])
  }

  function removeRow(index: number) {
    setRows((prev) => prev.filter((_, i) => i !== index))
  }

  function exportCsv() {
    const header = sheet.columns.map((c) => c.label).join(',')
    const body = rows
      .map((row) =>
        sheet.columns
          .map((c) => `"${(row[c.key] ?? '').replace(/"/g, '""')}"`)
          .join(','),
      )
      .join('\n')
    const blob = new Blob([`\ufeff${header}\n${body}`], {
      type: 'text/csv;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${sheet.title}.csv`
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="screen stack-gap toolkit">
      <div className="page-title no-print">
        <div>
          <h1>学习工具箱</h1>
          <p className="sub">
            量表自评 · 记录表 · 应急手册 · 家属指南 · 问答与案例
          </p>
        </div>
        <Link to="/courses" className="linkish">
          回到课程
        </Link>
      </div>

      <div className="tk-tabs no-print">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`tk-tab${tab === t.key ? ' active' : ''}`}
            onClick={() => setTab(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'assess' ? (
        <>
          <section className="item-card">
            <div className="tk-head">
              <h2>mMRC 呼吸困难自评</h2>
              <span className="tk-badge">1 分钟</span>
            </div>
            <p className="muted tk-intro">
              选一个最符合你日常状态的说法。它反映的是「因为气短，活动被限制到什么程度」。
            </p>
            <div className="tk-options">
              {MMRC_LEVELS.map((lv) => (
                <button
                  key={lv.level}
                  type="button"
                  className={`tk-option${mmrc === lv.level ? ' active' : ''}`}
                  onClick={() => setMmrc(lv.level)}
                >
                  <span className="tk-option-label">{lv.label}</span>
                  <span className="tk-option-desc">{lv.desc}</span>
                </button>
              ))}
            </div>
            {mmrcLevel ? (
              <div className="tk-result">
                <p className="tk-result-title">
                  当前：{mmrcLevel.label}
                </p>
                <p className="meta">{mmrcLevel.tip}</p>
              </div>
            ) : null}
          </section>

          <section className="item-card">
            <div className="tk-head">
              <h2>CAT 生活质量评分</h2>
              <span className="tk-badge">8 题 · 0–40 分</span>
            </div>
            <p className="muted tk-intro">
              每一项 0–5 分：0 分表示完全没影响，5 分表示影响最严重。全部选完自动算分。
            </p>
            <div className="cat-list">
              {CAT_ITEMS.map((item, index) => (
                <div key={item.left} className="cat-item">
                  <div className="cat-scale">
                    <span className="cat-anchor">{item.left}</span>
                    <div className="cat-buttons">
                      {[0, 1, 2, 3, 4, 5].map((score) => (
                        <button
                          key={score}
                          type="button"
                          className={`cat-btn${
                            cat[index] === score ? ' active' : ''
                          }`}
                          onClick={() =>
                            setCat((prev) =>
                              prev.map((v, i) => (i === index ? score : v)),
                            )
                          }
                        >
                          {score}
                        </button>
                      ))}
                    </div>
                    <span className="cat-anchor right">{item.right}</span>
                  </div>
                </div>
              ))}
            </div>
            <div className="tk-result">
              {catScore === null || !catResult ? (
                <p className="meta">
                  已作答 {cat.filter((v) => v >= 0).length}/{CAT_ITEMS.length} 项，
                  全部选完后显示总分。
                </p>
              ) : (
                <>
                  <p className={`tk-result-title tone-${catResult.tone}`}>
                    总分 {catScore}/40 · {catResult.level}
                  </p>
                  <p className="meta">{catResult.tip}</p>
                  <p className="meta">
                    参考：0–9 轻微、10–19 中等、20–29 严重、≥30 非常严重。分数变化比单次分数更有意义，建议每月测一次。
                  </p>
                </>
              )}
            </div>
            <div className="row-actions no-print">
              <button
                type="button"
                className="btn small"
                onClick={() => setCat(CAT_ITEMS.map(() => -1))}
              >
                重新填写
              </button>
              <button type="button" className="btn small" onClick={() => window.print()}>
                打印量表
              </button>
            </div>
          </section>
        </>
      ) : null}

      {tab === 'records' ? (
        <section className="item-card">
          <div className="tk-head">
            <h2>记录表</h2>
            <span className="tk-badge">本地保存</span>
          </div>
          <div className="tk-chips no-print">
            {RECORD_SHEETS.map((s, index) => (
              <button
                key={s.key}
                type="button"
                className={`tk-chip${index === sheetIndex ? ' active' : ''}`}
                onClick={() => setSheetIndex(index)}
              >
                {s.title}
              </button>
            ))}
          </div>
          <p className="muted tk-intro">{sheet.desc}</p>

          <div className="tk-table-wrap">
            <table className="tk-table">
              <thead>
                <tr>
                  {sheet.columns.map((col) => (
                    <th key={col.key} style={col.width ? { width: col.width } : undefined}>
                      {col.label}
                    </th>
                  ))}
                  <th className="no-print" style={{ width: '44px' }}>
                    {' '}
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 ? (
                  <tr>
                    <td colSpan={sheet.columns.length + 1} className="tk-empty">
                      还没有记录，点下方「添加一行」开始。
                    </td>
                  </tr>
                ) : (
                  rows.map((row, index) => (
                    <tr key={index}>
                      {sheet.columns.map((col) => (
                        <td key={col.key}>
                          <input
                            className="tk-cell"
                            value={row[col.key] ?? ''}
                            placeholder={col.placeholder ?? ''}
                            onChange={(e) => updateCell(index, col.key, e.target.value)}
                          />
                        </td>
                      ))}
                      <td className="no-print">
                        <button
                          type="button"
                          className="tk-del"
                          aria-label="删除该行"
                          onClick={() => removeRow(index)}
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
            <button type="button" className="btn small primary" onClick={addRow}>
              添加一行
            </button>
            <button type="button" className="btn small" onClick={exportCsv} disabled={!rows.length}>
              导出 CSV
            </button>
            <button type="button" className="btn small" onClick={() => window.print()}>
              打印
            </button>
            <button
              type="button"
              className="linkish"
              onClick={() => {
                if (window.confirm('确定清空这张表的全部记录吗？')) setRows([])
              }}
            >
              清空
            </button>
          </div>
          <p className="meta tk-note">
            记录仅保存在本机浏览器，不上传服务器；换设备或清理浏览器数据会丢失，重要记录请打印或导出。
          </p>
        </section>
      ) : null}

      {tab === 'handbook' ? (
        <>
          <section className="item-card tk-poster">
            <div className="tk-poster-top">
              <span className="tk-poster-badge">居家应急口袋卡</span>
              <h2>出现这些情况，立即就医或拨打 120</h2>
            </div>
            <ul className="tk-signal-list">
              {EMERGENCY_SIGNALS.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ul>
            <div className="tk-poster-bottom">
              <div>
                <strong>急救电话</strong>
                <span>120</span>
              </div>
              <div>
                <strong>我的诊断</strong>
                <span>慢阻肺（COPD）· ______ 级</span>
              </div>
              <div>
                <strong>紧急联系人</strong>
                <span>__________ / __________</span>
              </div>
              <div>
                <strong>常去医院 / 科室</strong>
                <span>__________ / 呼吸内科</span>
              </div>
            </div>
            <p className="meta tk-note">
              建议打印后对折放进钱包或贴在冰箱上；家人也要知道放在哪。
            </p>
          </section>

          <section className="item-card">
            <h2>紧急情况四步走</h2>
            <ol className="tk-steps">
              {EMERGENCY_STEPS.map((s) => (
                <li key={s}>{s}</li>
              ))}
            </ol>
            <h3 className="tk-sub">急救包里放什么</h3>
            <ul className="tk-dot-list">
              {EMERGENCY_PREP.map((p) => (
                <li key={p}>{p}</li>
              ))}
            </ul>
            <div className="row-actions no-print">
              <button type="button" className="btn small" onClick={() => window.print()}>
                打印口袋卡
              </button>
            </div>
          </section>

          <section className="item-card">
            <div className="tk-head">
              <h2>常见误区辟谣</h2>
              <span className="tk-badge">{MYTHS.length} 条</span>
            </div>
            <div className="tk-myths">
              {MYTHS.map((m, i) => (
                <details key={m.myth} className="tk-myth" open={i === 0}>
                  <summary>
                    <span className="tk-myth-tag">误区</span>
                    {m.myth}
                  </summary>
                  <p>
                    <span className="tk-truth-tag">事实</span>
                    {m.truth}
                  </p>
                </details>
              ))}
            </div>
          </section>
        </>
      ) : null}

      {tab === 'media' ? (
        <>
          <section className="item-card">
            <div className="tk-head">
              <h2>实操短视频</h2>
              <span className="tk-badge">跟做版</span>
            </div>
            <p className="muted tk-intro">
              点开可直接跳到对应课程课时，边看边跟着做一遍最有效。
            </p>
            <div className="tk-videos">
              {VIDEO_ITEMS.map((v) => (
                <Link key={v.title} to={`/courses?kw=${encodeURIComponent(v.keyword)}`} className="tk-video">
                  <span className="tk-video-play">▶</span>
                  <span className="tk-video-main">
                    <strong>{v.title}</strong>
                    <span className="meta">{v.desc}</span>
                  </span>
                  <span className="tk-video-time">{v.minutes}</span>
                </Link>
              ))}
            </div>
          </section>

          <section className="item-card tk-poster tk-poster-danger">
            <div className="tk-poster-top">
              <span className="tk-poster-badge">危险信号速览</span>
              <h2>记住「三个不能等」</h2>
            </div>
            <div className="tk-quick-grid">
              <div>
                <strong>不能等：说话断续</strong>
                <p>只能说单词、说不成整句，说明通气已经很差。</p>
              </div>
              <div>
                <strong>不能等：口唇发紫</strong>
                <p>嘴唇、指甲发紫是明显缺氧，立即拨打 120。</p>
              </div>
              <div>
                <strong>不能等：意识改变</strong>
                <p>嗜睡、叫不醒、胡言乱语，可能已二氧化碳潴留。</p>
              </div>
              <div>
                <strong>不能等：痰色突变</strong>
                <p>白痰转黄绿、量明显增多，尽快联系医生。</p>
              </div>
            </div>
            <p className="meta tk-note">建议打印贴在电话旁，家属一眼能看到。</p>
          </section>
        </>
      ) : null}

      {tab === 'family' ? (
        <section className="item-card">
          <div className="tk-head">
            <h2>家属照护指南</h2>
            <span className="tk-badge">给家人</span>
          </div>
          <p className="muted tk-intro">
            照护不是「多做一点」，而是「做对几件事」：会测血氧、会叩背排痰、能识别危险信号。
          </p>
          <Link to="/family" className="toolkit-jump">
            👨‍👩‍👧 进入家属照护专区：观察病情 · 协助用药 · 排痰 · 送医判断 · 照护者自评 ›
          </Link>
          <div className="tk-family">
            {FAMILY_GUIDE.map((g) => (
              <div key={g.title} className="tk-family-card">
                <h3>{g.title}</h3>
                <ul className="tk-dot-list">
                  {g.points.map((p) => (
                    <li key={p}>{p}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {tab === 'faq' ? (
        <section className="item-card">
          <div className="tk-head">
            <h2>常见问答</h2>
            <span className="tk-badge">{filteredFaqs.length} 条</span>
          </div>
          <input
            className="tk-search"
            value={faqKeyword}
            placeholder="搜一搜：抽烟、吸氧、抗生素、坐飞机…"
            onChange={(e) => setFaqKeyword(e.target.value)}
          />
          <div className="tk-faqs">
            {filteredFaqs.map((f) => (
              <details
                key={f.q}
                className="tk-faq"
                open={openFaq === f.q}
                onToggle={(e) => {
                  if ((e.target as HTMLDetailsElement).open) setOpenFaq(f.q)
                }}
              >
                <summary>
                  <span className="tk-faq-tag">{f.tag}</span>
                  {f.q}
                </summary>
                <p>{f.a}</p>
              </details>
            ))}
            {filteredFaqs.length === 0 ? (
              <p className="muted">没有找到相关问答，换个关键词试试。</p>
            ) : null}
          </div>
        </section>
      ) : null}

      {tab === 'cases' ? (
        <section className="item-card">
          <div className="tk-head">
            <h2>案例分享</h2>
            <span className="tk-badge">匿名整理</span>
          </div>
          <p className="muted tk-intro">
            以下为教学用的匿名案例，情节经过改写，不指向任何具体个人；不作为诊疗依据。
          </p>
          <div className="tk-cases">
            {CASES.map((c) => (
              <article key={c.title} className="tk-case">
                <span className="tk-case-tag">{c.tag}</span>
                <h3>{c.title}</h3>
                <p className="meta">{c.profile}</p>
                <ul className="tk-dot-list">
                  {c.story.map((s) => (
                    <li key={s}>{s}</li>
                  ))}
                </ul>
                <p className="tk-case-takeaway">启示：{c.takeaway}</p>
              </article>
            ))}
          </div>
        </section>
      ) : null}

      <p className="meta tk-foot no-print">
        本工具箱内容为健康宣教材料，不能替代医生的面诊、诊断与处方。量表结果仅供自我了解，若症状加重请及时就医。
      </p>
    </div>
  )
}
