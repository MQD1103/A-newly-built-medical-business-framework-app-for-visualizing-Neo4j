import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

type TabKey = 'sat' | 'pef' | 'weight' | 'bp'

const TABS: { key: TabKey; label: string; icon: string }[] = [
  { key: 'sat', label: '血氧', icon: '🫁' },
  { key: 'pef', label: '峰流速', icon: '💨' },
  { key: 'weight', label: '体重', icon: '⚖️' },
  { key: 'bp', label: '血压血糖', icon: '🩺' },
]

type Row = Record<string, string>

const STORAGE = {
  sat: 'xy.vitals.sat',
  pef: 'xy.vitals.pef',
  weight: 'xy.vitals.weight',
  bp: 'xy.vitals.bp',
  pefBest: 'xy.vitals.pefBest',
} as const

function pad(n: number): string {
  return String(n).padStart(2, '0')
}

function nowLocal(): string {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function todayLocal(): string {
  const d = new Date()
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function shortDate(value: string): string {
  const raw = value.slice(0, 10)
  const parts = raw.split('-')
  if (parts.length !== 3) return value
  return `${Number(parts[1])}/${Number(parts[2])}`
}

function timeOf(value: string): string {
  const t = value.split('T')[1]
  return t ? t.slice(0, 5) : ''
}

function loadRows(key: string): Row[] {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.map((item) => {
      const src = (item ?? {}) as Record<string, unknown>
      const row: Row = {}
      for (const [k, v] of Object.entries(src)) row[k] = typeof v === 'string' ? v : String(v ?? '')
      return row
    })
  } catch {
    return []
  }
}

function useStoredRows(key: string) {
  const [rows, setRows] = useState<Row[]>(() => loadRows(key))
  useEffect(() => {
    localStorage.setItem(key, JSON.stringify(rows))
  }, [key, rows])
  return [rows, setRows] as const
}

function num(value: string | undefined): number | null {
  if (!value) return null
  const n = Number(value)
  return Number.isFinite(n) ? n : null
}

function bandOf(values: number[]): [number, number] {
  if (values.length === 0) return [0, 1]
  const lo = Math.min(...values)
  const hi = Math.max(...values)
  if (lo === hi) return [lo - 1, hi + 1]
  return [lo, hi]
}

/** 迷你折线图：带参考区间带、最新值标注 */
function Trend({
  points,
  unit,
  band,
  times,
}: {
  points: number[]
  unit: string
  band?: [number, number]
  times?: string[]
}) {
  if (points.length === 0) {
    return <p className="muted vitals-empty">还没有数据，录入后这里会显示趋势。</p>
  }

  const W = 320
  const H = 96
  const PX = 12
  const PY = 14
  const [bLo, bHi] = band ?? bandOf(points)
  const all = band ? [...points, bLo, bHi] : points
  const lo0 = Math.min(...all)
  const hi0 = Math.max(...all)
  const span = hi0 - lo0 || 1
  const lo = lo0 - span * 0.15
  const hi = hi0 + span * 0.15

  const x = (i: number) =>
    points.length === 1 ? W / 2 : PX + (i * (W - PX * 2)) / (points.length - 1)
  const y = (v: number) => H - PY - ((v - lo) / (hi - lo)) * (H - PY * 2)
  const line = points
    .map((v, i) => `${i === 0 ? 'M' : 'L'}${x(i).toFixed(1)},${y(v).toFixed(1)}`)
    .join(' ')
  const last = points[points.length - 1]

  return (
    <div className="vitals-chart">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="趋势图">
        {band ? (
          <rect
            x={0}
            y={y(bHi)}
            width={W}
            height={Math.max(0, y(bLo) - y(bHi))}
            fill="rgba(58, 163, 138, 0.12)"
          />
        ) : null}
        <line
          x1={0}
          y1={H - PY}
          x2={W}
          y2={H - PY}
          stroke="#e3edf8"
          strokeWidth="1"
        />
        <path d={line} fill="none" stroke="#5ba3f5" strokeWidth="2" strokeLinecap="round" />
        {points.map((v, i) => (
          <circle
            key={`${i}-${v}`}
            cx={x(i)}
            cy={y(v)}
            r={i === points.length - 1 ? 3.4 : 2.2}
            fill={i === points.length - 1 ? '#3b86e0' : '#9ec8f5'}
          />
        ))}
        <text x={W - 2} y={y(last) - 6} textAnchor="end" fontSize="10" fill="#3b86e0">
          {last} {unit}
        </text>
        <text x={2} y={y(hi0) + 3} fontSize="9" fill="#9db2c6">
          {hi0}
        </text>
        <text x={2} y={y(lo0) + 3} fontSize="9" fill="#9db2c6">
          {lo0}
        </text>
      </svg>
      {times && times.length > 0 ? (
        <div className="vitals-chart-axis">
          <span>{times[0]}</span>
          <span>{times[times.length - 1]}</span>
        </div>
      ) : null}
    </div>
  )
}

/** CSV 导出（带 BOM，Excel 直接打开不乱码） */
function exportCsv(name: string, header: string[], rows: string[][]) {
  const body = [header, ...rows]
    .map((r) => r.map((cell) => `"${(cell ?? '').replace(/"/g, '""')}"`).join(','))
    .join('\n')
  const blob = new Blob([`\ufeff${body}`], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${name}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

function verdict(text: string, tone: 'ok' | 'warn' | 'bad') {
  return { text, tone }
}

export default function Vitals() {
  const [tab, setTab] = useState<TabKey>('sat')
  const [tip, setTip] = useState('')

  useEffect(() => {
    window.scrollTo({ top: 0 })
  }, [tab])

  return (
    <div className="screen stack-gap vitals">
      <div className="page-title no-print">
        <div>
          <h1>健康监测</h1>
          <p className="sub">血氧 · 峰流速 · 体重 · 血压血糖</p>
        </div>
        <Link to="/services" className="linkish">
          返回服务
        </Link>
      </div>

      <div className="vitals-note">
        <span aria-hidden="true">📱</span>
        <p>
          记录只保存在本机浏览器，不上传服务器。复诊时用「导出 CSV」或直接打印给医生看；
          换设备或清理浏览器数据会丢失。
        </p>
      </div>

      <div className="vitals-tabs no-print">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            className={`vitals-tab${tab === t.key ? ' active' : ''}`}
            onClick={() => {
              setTab(t.key)
              setTip('')
            }}
          >
            <span aria-hidden="true">{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'sat' ? <SatPanel onTip={setTip} /> : null}
      {tab === 'pef' ? <PefPanel onTip={setTip} /> : null}
      {tab === 'weight' ? <WeightPanel onTip={setTip} /> : null}
      {tab === 'bp' ? <BpPanel onTip={setTip} /> : null}

      {tip ? <p className="vitals-toast no-print">{tip}</p> : null}

      <p className="meta tk-foot no-print">
        本工具用于自我记录与趋势观察，不替代医生的诊断。数值异常或症状加重时，请及时联系主管医生或拨打 120。
        也建议配合「症状日记」一起记录咳嗽、气短与痰量。
      </p>
    </div>
  )
}

/* ---------------- 血氧 ---------------- */

function SatPanel({ onTip }: { onTip: (t: string) => void }) {
  const [rows, setRows] = useStoredRows(STORAGE.sat)
  const [at, setAt] = useState(nowLocal())
  const [spo2, setSpo2] = useState('')
  const [hr, setHr] = useState('')
  const [breath, setBreath] = useState('0')

  const ordered = useMemo(() => {
    const arr = rows
      .map((r) => ({
        at: r.at ?? '',
        spo2: num(r.spo2),
        hr: num(r.hr),
        breath: num(r.breath) ?? 0,
      }))
      .filter((r) => r.spo2 !== null)
    arr.sort((a, b) => a.at.localeCompare(b.at))
    return arr
  }, [rows])

  const recent = ordered.slice(-14)
  const latest = ordered[ordered.length - 1]

  const check = useMemo(() => {
    if (!latest || latest.spo2 === null) return null
    if (latest.spo2 < 88) {
      return verdict('血氧低于 88%，若吸氧后仍不上升，属于需要立即处理的情况（拨打 120）。', 'bad')
    }
    if (latest.spo2 < 92) {
      return verdict('血氧偏低，按医生设定的目标复查；若伴气短加重，当天联系医生。', 'warn')
    }
    if (latest.hr !== null && latest.hr > 100) {
      return verdict(`血氧正常，但心率 ${latest.hr} 次/分偏快，休息后复测。`, 'warn')
    }
    return verdict('血氧在常见目标范围内。看趋势比看单次更有意义。', 'ok')
  }, [latest])

  function submit(e: FormEvent) {
    e.preventDefault()
    const s = num(spo2)
    if (s === null || s < 50 || s > 100) {
      onTip('请输入 50–100 之间的血氧数值')
      return
    }
    setRows((prev) => [...prev, { at, spo2: String(s), hr, breath }])
    onTip('已记录一条血氧')
    setSpo2('')
    setHr('')
    setAt(nowLocal())
  }

  return (
    <>
      <section className="item-card">
        <div className="tk-head">
          <h2>记录血氧</h2>
          <span className="tk-badge">静息 5 分钟后测</span>
        </div>
        <p className="muted tk-intro">
          手指温暖、不涂指甲油，坐位静息 5 分钟再测。同时记下心率与当时的气短程度。
        </p>
        <form className="vitals-form" onSubmit={submit}>
          <label className="vitals-field wide">
            <span>时间</span>
            <input type="datetime-local" value={at} onChange={(e) => setAt(e.target.value)} />
          </label>
          <label className="vitals-field">
            <span>血氧 SpO₂ (%)</span>
            <input
              type="number"
              inputMode="numeric"
              min={50}
              max={100}
              placeholder="95"
              value={spo2}
              onChange={(e) => setSpo2(e.target.value)}
            />
          </label>
          <label className="vitals-field">
            <span>心率 (次/分)</span>
            <input
              type="number"
              inputMode="numeric"
              min={30}
              max={200}
              placeholder="82"
              value={hr}
              onChange={(e) => setHr(e.target.value)}
            />
          </label>
          <div className="vitals-field wide">
            <span>呼吸困难程度</span>
            <div className="vitals-seg">
              {['无', '轻度', '中度', '重度', '极重'].map((label, i) => (
                <button
                  key={label}
                  type="button"
                  className={breath === String(i) ? 'active' : ''}
                  onClick={() => setBreath(String(i))}
                >
                  {i} {label}
                </button>
              ))}
            </div>
          </div>
          <button type="submit" className="btn small primary vitals-submit">
            保存记录
          </button>
        </form>
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>趋势</h2>
          <span className="tk-badge">{ordered.length} 条</span>
        </div>
        <Trend
          points={recent.map((r) => r.spo2 as number)}
          unit="%"
          band={[88, 92]}
          times={recent.map((r) => shortDate(r.at))}
        />
        {check ? (
          <div className="vitals-verdict">
            <p className={`tk-result-title tone-${check.tone}`}>
              最近一次 {latest?.spo2}%{latest?.hr !== null ? ` · 心率 ${latest?.hr}` : ''}
            </p>
            <p className="meta">{check.text}</p>
          </div>
        ) : null}
        <p className="meta tk-note">
          参考：多数慢阻肺患者的目标由医生设定，常见 88–92%；静息心率 60–100 次/分为常见范围。
          记录时尽量固定时间与状态，趋势才有可比性。
        </p>
      </section>

      <RecordTable
        title="血氧记录"
        rows={rows}
        onDelete={(i) => setRows((prev) => prev.filter((_, idx) => idx !== i))}
        columns={['时间', '血氧 %', '心率', '气短']}
        render={(r) => [
          `${shortDate(r.at ?? '')} ${timeOf(r.at ?? '')}`,
          r.spo2 ?? '',
          r.hr ?? '',
          ['无', '轻度', '中度', '重度', '极重'][Number(r.breath ?? 0)] ?? '',
        ]}
        csvName="血氧记录"
        csvHeader={['时间', '血氧SpO2(%)', '心率(次/分)', '呼吸困难(0-4)']}
        csvRow={(r) => [r.at ?? '', r.spo2 ?? '', r.hr ?? '', r.breath ?? '']}
      />
    </>
  )
}

/* ---------------- 峰流速 ---------------- */

function PefPanel({ onTip }: { onTip: (t: string) => void }) {
  const [rows, setRows] = useStoredRows(STORAGE.pef)
  const [best, setBest] = useState(() => localStorage.getItem(STORAGE.pefBest) ?? '')
  const [date, setDate] = useState(todayLocal())
  const [slot, setSlot] = useState<'早' | '晚'>('早')
  const [value, setValue] = useState('')

  useEffect(() => {
    localStorage.setItem(STORAGE.pefBest, best)
  }, [best])

  const ordered = useMemo(() => {
    const arr = rows
      .map((r) => ({ date: r.date ?? '', slot: r.slot ?? '', value: num(r.value) }))
      .filter((r) => r.value !== null)
    arr.sort((a, b) => (a.date + a.slot).localeCompare(b.date + b.slot))
    return arr
  }, [rows])

  const recent = ordered.slice(-14)
  const bestNum = num(best)

  const zone = useMemo(() => {
    const last = ordered[ordered.length - 1]
    if (!last || last.value === null || !bestNum || bestNum <= 0) return null
    const pct = Math.round((last.value / bestNum) * 100)
    if (pct >= 80) return { pct, tone: 'ok' as const, text: '绿区：气流接近个人最佳，按计划维持用药与康复训练。' }
    if (pct >= 60)
      return {
        pct,
        tone: 'warn' as const,
        text: '黄区：气流下降，检查吸入药是否按时使用、有无诱发因素；连续 2 天在黄区请联系医生。',
      }
    return {
      pct,
      tone: 'bad' as const,
      text: '红区：明显低于个人最佳，按医生事先给的方案处理，并尽快就诊。',
    }
  }, [ordered, bestNum])

  function submit(e: FormEvent) {
    e.preventDefault()
    const v = num(value)
    if (v === null || v <= 0) {
      onTip('请输入有效的峰流速数值')
      return
    }
    setRows((prev) => [...prev, { date, slot, value: String(v) }])
    if (!bestNum || v > bestNum) setBest(String(v))
    onTip('已记录一次峰流速')
    setValue('')
  }

  return (
    <>
      <section className="item-card">
        <div className="tk-head">
          <h2>记录峰流速（PEF）</h2>
          <span className="tk-badge">早晚各一次</span>
        </div>
        <p className="muted tk-intro">
          每天起床后、睡前各吹 3 次，取最好的一次记录。站直、深吸气后用力快速吹出。
          连续记录两周后，「个人最佳值」才有参考意义。
        </p>
        <form className="vitals-form" onSubmit={submit}>
          <label className="vitals-field wide">
            <span>日期</span>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          <div className="vitals-field wide">
            <span>时段</span>
            <div className="vitals-seg">
              {(['早', '晚'] as const).map((s) => (
                <button
                  key={s}
                  type="button"
                  className={slot === s ? 'active' : ''}
                  onClick={() => setSlot(s)}
                >
                  {s}起 / {s === '早' ? '起床后' : '睡前'}
                </button>
              ))}
            </div>
          </div>
          <label className="vitals-field">
            <span>PEF (L/min)</span>
            <input
              type="number"
              inputMode="numeric"
              min={30}
              max={900}
              placeholder="320"
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
          </label>
          <label className="vitals-field">
            <span>个人最佳 (L/min)</span>
            <input
              type="number"
              inputMode="numeric"
              min={30}
              max={900}
              placeholder="记录后自动更新"
              value={best}
              onChange={(e) => setBest(e.target.value)}
            />
          </label>
          <button type="submit" className="btn small primary vitals-submit">
            保存记录
          </button>
        </form>
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>气流变化</h2>
          <span className="tk-badge">{ordered.length} 次</span>
        </div>
        <Trend
          points={recent.map((r) => r.value as number)}
          unit="L/min"
          times={recent.map((r) => shortDate(r.date))}
        />
        {zone ? (
          <div className="vitals-verdict">
            <p className={`tk-result-title tone-${zone.tone}`}>
              最近一次为个人最佳的 {zone.pct}%
            </p>
            <p className="meta">{zone.text}</p>
          </div>
        ) : (
          <p className="meta tk-note">填入「个人最佳」后，会按绿 / 黄 / 红三区给出提示。</p>
        )}
        <p className="meta tk-note">
          分区参考：≥80% 绿区、60–79% 黄区、&lt;60% 红区。个人最佳应在病情稳定期连续测量两周取最高值，
          具体分区阈值以医生给你的行动计划为准。
        </p>
      </section>

      <RecordTable
        title="峰流速记录"
        rows={rows}
        onDelete={(i) => setRows((prev) => prev.filter((_, idx) => idx !== i))}
        columns={['日期', '时段', 'PEF']}
        render={(r) => [shortDate(r.date ?? ''), r.slot ?? '', `${r.value ?? ''} L/min`]}
        csvName="峰流速记录"
        csvHeader={['日期', '时段', 'PEF(L/min)']}
        csvRow={(r) => [r.date ?? '', r.slot ?? '', r.value ?? '']}
      />
    </>
  )
}

/* ---------------- 体重 ---------------- */

function WeightPanel({ onTip }: { onTip: (t: string) => void }) {
  const [rows, setRows] = useStoredRows(STORAGE.weight)
  const [date, setDate] = useState(todayLocal())
  const [kg, setKg] = useState('')
  const [note, setNote] = useState('')

  const ordered = useMemo(() => {
    const arr = rows
      .map((r) => ({ date: r.date ?? '', kg: num(r.kg), note: r.note ?? '' }))
      .filter((r) => r.kg !== null)
    arr.sort((a, b) => a.date.localeCompare(b.date))
    return arr
  }, [rows])

  const recent = ordered.slice(-14)
  const latest = ordered[ordered.length - 1]

  const drop = useMemo(() => {
    if (ordered.length < 2 || !latest) return null
    const latestDate = new Date(`${latest.date}T00:00:00`).getTime()
    const target = latestDate - 7 * 24 * 3600 * 1000
    const past = [...ordered].reverse().find((r) => new Date(`${r.date}T00:00:00`).getTime() <= target)
    if (!past || past.kg === null || latest.kg === null) return null
    const diff = Number((latest.kg - past.kg).toFixed(1))
    if (diff <= -2) return { diff, tone: 'warn' as const, text: '一周内体重下降超过 2 公斤，属于需要告诉医生的信号（营养不良或消耗增加）。' }
    if (diff >= 2) return { diff, tone: 'warn' as const, text: '一周内体重上升超过 2 公斤，注意有无下肢水肿、气短加重，可能是体液潴留。' }
    return { diff, tone: 'ok' as const, text: '近一周体重基本稳定。' }
  }, [ordered, latest])

  function submit(e: FormEvent) {
    e.preventDefault()
    const v = num(kg)
    if (v === null || v < 20 || v > 200) {
      onTip('请输入 20–200 之间的体重')
      return
    }
    setRows((prev) => [...prev, { date, kg: String(v), note }])
    onTip('已记录体重')
    setKg('')
    setNote('')
  }

  return (
    <>
      <section className="item-card">
        <div className="tk-head">
          <h2>记录体重</h2>
          <span className="tk-badge">固定时间称</span>
        </div>
        <p className="muted tk-intro">
          建议晨起排空后、同一台秤、穿相近衣物称重。慢阻肺患者体重下降常见，
          但短期内明显波动也可能是水肿，两者要分清。
        </p>
        <form className="vitals-form" onSubmit={submit}>
          <label className="vitals-field wide">
            <span>日期</span>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          <label className="vitals-field">
            <span>体重 (kg)</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.1"
              min={20}
              max={200}
              placeholder="58.5"
              value={kg}
              onChange={(e) => setKg(e.target.value)}
            />
          </label>
          <label className="vitals-field">
            <span>备注（可选）</span>
            <input
              placeholder="如：水肿 / 食欲差"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>
          <button type="submit" className="btn small primary vitals-submit">
            保存记录
          </button>
        </form>
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>体重趋势</h2>
          <span className="tk-badge">{ordered.length} 条</span>
        </div>
        <Trend
          points={recent.map((r) => r.kg as number)}
          unit="kg"
          times={recent.map((r) => shortDate(r.date))}
        />
        {drop ? (
          <div className="vitals-verdict">
            <p className={`tk-result-title tone-${drop.tone}`}>
              近一周变化 {drop.diff > 0 ? '+' : ''}
              {drop.diff} kg
            </p>
            <p className="meta">{drop.text}</p>
          </div>
        ) : (
          <p className="meta tk-note">至少需要间隔一周的两条记录，才能计算周变化。</p>
        )}
        <p className="meta tk-note">
          参考：一周内下降 ≥2 kg 或持续下降，提示营养风险；上升 ≥2 kg 需排查水肿。
          BMI 需结合身高计算，可在复诊时由医生评估。
        </p>
      </section>

      <RecordTable
        title="体重记录"
        rows={rows}
        onDelete={(i) => setRows((prev) => prev.filter((_, idx) => idx !== i))}
        columns={['日期', '体重', '备注']}
        render={(r) => [shortDate(r.date ?? ''), `${r.kg ?? ''} kg`, r.note ?? '']}
        csvName="体重记录"
        csvHeader={['日期', '体重(kg)', '备注']}
        csvRow={(r) => [r.date ?? '', r.kg ?? '', r.note ?? '']}
      />
    </>
  )
}

/* ---------------- 血压 / 血糖 ---------------- */

function BpPanel({ onTip }: { onTip: (t: string) => void }) {
  const [rows, setRows] = useStoredRows(STORAGE.bp)
  const [date, setDate] = useState(todayLocal())
  const [sys, setSys] = useState('')
  const [dia, setDia] = useState('')
  const [glucose, setGlucose] = useState('')
  const [timing, setTiming] = useState<'空腹' | '餐后'>('空腹')

  const ordered = useMemo(() => {
    const arr = rows
      .map((r) => ({
        date: r.date ?? '',
        sys: num(r.sys),
        dia: num(r.dia),
        glucose: num(r.glucose),
        timing: r.timing ?? '',
      }))
      .filter((r) => r.sys !== null || r.glucose !== null)
    arr.sort((a, b) => a.date.localeCompare(b.date))
    return arr
  }, [rows])

  const recent = ordered.filter((r) => r.sys !== null).slice(-14)
  const latest = ordered[ordered.length - 1]

  const check = useMemo(() => {
    if (!latest) return null
    if (latest.sys !== null && latest.dia !== null && (latest.sys >= 180 || latest.dia >= 120)) {
      return verdict('血压达到 180/120 mmHg 及以上，若伴头痛、胸闷、视物模糊，立即就医。', 'bad')
    }
    if (latest.sys !== null && latest.dia !== null && (latest.sys >= 140 || latest.dia >= 90)) {
      return verdict('血压高于常见目标（140/90），连续多天偏高请告诉医生，不要自行加药。', 'warn')
    }
    if (latest.glucose !== null) {
      const g = latest.glucose
      if (latest.timing === '空腹' && g >= 7) {
        return verdict(`空腹血糖 ${g} mmol/L 偏高，连续偏高需调整方案，请咨询医生。`, 'warn')
      }
      if (latest.timing === '餐后' && g >= 11.1) {
        return verdict(`餐后血糖 ${g} mmol/L 偏高，记录饮食内容并告知医生。`, 'warn')
      }
    }
    return verdict('本次数值在常见范围内。血压血糖看多次平均值，单次偏高先复测。', 'ok')
  }, [latest])

  function submit(e: FormEvent) {
    e.preventDefault()
    const s = num(sys)
    const d = num(dia)
    const g = num(glucose)
    if (s === null && g === null) {
      onTip('血压和血糖至少填写一项')
      return
    }
    if (s !== null && d === null) {
      onTip('填写收缩压时请同时填写舒张压')
      return
    }
    setRows((prev) => [
      ...prev,
      { date, sys: s === null ? '' : String(s), dia: d === null ? '' : String(d), glucose: g === null ? '' : String(g), timing },
    ])
    onTip('已记录一条血压血糖')
    setSys('')
    setDia('')
    setGlucose('')
  }

  return (
    <>
      <section className="item-card">
        <div className="tk-head">
          <h2>记录血压 / 血糖</h2>
          <span className="tk-badge">合并症管理</span>
        </div>
        <p className="muted tk-intro">
          测血压前静坐 5 分钟、不说话、手臂与心脏同高；血糖记录测量时点（空腹 / 餐后 2 小时）。
          两项可只填其中一项。
        </p>
        <form className="vitals-form" onSubmit={submit}>
          <label className="vitals-field wide">
            <span>日期</span>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
          <label className="vitals-field">
            <span>收缩压 (mmHg)</span>
            <input
              type="number"
              inputMode="numeric"
              min={60}
              max={260}
              placeholder="128"
              value={sys}
              onChange={(e) => setSys(e.target.value)}
            />
          </label>
          <label className="vitals-field">
            <span>舒张压 (mmHg)</span>
            <input
              type="number"
              inputMode="numeric"
              min={30}
              max={160}
              placeholder="78"
              value={dia}
              onChange={(e) => setDia(e.target.value)}
            />
          </label>
          <label className="vitals-field">
            <span>血糖 (mmol/L)</span>
            <input
              type="number"
              inputMode="decimal"
              step="0.1"
              min={1}
              max={40}
              placeholder="6.2"
              value={glucose}
              onChange={(e) => setGlucose(e.target.value)}
            />
          </label>
          <div className="vitals-field">
            <span>血糖时点</span>
            <div className="vitals-seg">
              {(['空腹', '餐后'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  className={timing === t ? 'active' : ''}
                  onClick={() => setTiming(t)}
                >
                  {t}
                </button>
              ))}
            </div>
          </div>
          <button type="submit" className="btn small primary vitals-submit">
            保存记录
          </button>
        </form>
      </section>

      <section className="item-card">
        <div className="tk-head">
          <h2>收缩压趋势</h2>
          <span className="tk-badge">{recent.length} 条</span>
        </div>
        <Trend
          points={recent.map((r) => r.sys as number)}
          unit="mmHg"
          band={[90, 140]}
          times={recent.map((r) => shortDate(r.date))}
        />
        {check ? (
          <div className="vitals-verdict">
            <p className={`tk-result-title tone-${check.tone}`}>
              {latest?.sys !== null && latest?.dia !== null
                ? `${latest?.sys}/${latest?.dia} mmHg`
                : ''}
              {latest?.glucose !== null ? ` · 血糖 ${latest?.glucose} mmol/L` : ''}
            </p>
            <p className="meta">{check.text}</p>
          </div>
        ) : null}
        <p className="meta tk-note">
          参考：合并高血压者常见目标 &lt;140/90 mmHg（部分人更低，按医嘱）；空腹血糖常见 4.4–7.0、
          餐后 2 小时 &lt;10.0 mmol/L。糖尿病患者的个体目标请以医生设定为准。
        </p>
      </section>

      <RecordTable
        title="血压血糖记录"
        rows={rows}
        onDelete={(i) => setRows((prev) => prev.filter((_, idx) => idx !== i))}
        columns={['日期', '血压', '血糖']}
        render={(r) => [
          shortDate(r.date ?? ''),
          r.sys ? `${r.sys}/${r.dia ?? '-'} mmHg` : '—',
          r.glucose ? `${r.glucose} mmol/L${r.timing ? `（${r.timing}）` : ''}` : '—',
        ]}
        csvName="血压血糖记录"
        csvHeader={['日期', '收缩压(mmHg)', '舒张压(mmHg)', '血糖(mmol/L)', '血糖时点']}
        csvRow={(r) => [r.date ?? '', r.sys ?? '', r.dia ?? '', r.glucose ?? '', r.timing ?? '']}
      />
    </>
  )
}

/* ---------------- 通用记录表 ---------------- */

function RecordTable({
  title,
  rows,
  onDelete,
  columns,
  render,
  csvName,
  csvHeader,
  csvRow,
}: {
  title: string
  rows: Row[]
  onDelete: (index: number) => void
  columns: string[]
  render: (row: Row) => string[]
  csvName: string
  csvHeader: string[]
  csvRow: (row: Row) => string[]
}) {
  const indexed = rows.map((row, index) => ({ row, index })).reverse()

  return (
    <section className="item-card">
      <div className="tk-head">
        <h2>{title}</h2>
        <span className="tk-badge">{rows.length} 条</span>
      </div>
      <div className="tk-table-wrap">
        <table className="tk-table vitals-table">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c}>{c}</th>
              ))}
              <th className="no-print" style={{ width: '40px' }}>
                {' '}
              </th>
            </tr>
          </thead>
          <tbody>
            {indexed.length === 0 ? (
              <tr>
                <td colSpan={columns.length + 1} className="tk-empty">
                  还没有记录，在上方表单录入一条试试。
                </td>
              </tr>
            ) : (
              indexed.slice(0, 30).map(({ row, index }) => (
                <tr key={index}>
                  {render(row).map((cell, i) => (
                    <td key={`${index}-${i}`}>{cell}</td>
                  ))}
                  <td className="no-print">
                    <button
                      type="button"
                      className="tk-del"
                      aria-label="删除该条记录"
                      onClick={() => onDelete(index)}
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
          className="btn small"
          disabled={rows.length === 0}
          onClick={() => exportCsv(csvName, csvHeader, [...rows].reverse().map(csvRow))}
        >
          导出 CSV
        </button>
        <button type="button" className="btn small" onClick={() => window.print()}>
          打印
        </button>
      </div>
      <p className="meta tk-note">列表显示最近 30 条；导出与打印包含全部记录。</p>
    </section>
  )
}
