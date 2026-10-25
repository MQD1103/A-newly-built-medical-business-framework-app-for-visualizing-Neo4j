import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api, apiUpload } from '../api'
import type {
  MedicationCheck,
  MedicationCheckList,
  MedicationMode,
} from '../types'
import { formatDateTime } from '../utils'

const MODES: { value: MedicationMode; label: string; hint: string }[] = [
  { value: 'oral', label: '口服药', hint: '对准药片与入口动作' },
  { value: 'inhale', label: '吸入剂', hint: '对准吸入装置与吸气动作' },
]

export default function AiCheck() {
  const [mode, setMode] = useState<MedicationMode>('oral')
  const [cameraOn, setCameraOn] = useState(false)
  const [cameraReady, setCameraReady] = useState(false)
  const [shot, setShot] = useState<Blob | null>(null)
  const [shotUrl, setShotUrl] = useState('')
  const [result, setResult] = useState<MedicationCheck | null>(null)
  const [history, setHistory] = useState<MedicationCheck[]>([])
  const [retentionDays, setRetentionDays] = useState(30)
  const [disclaimer, setDisclaimer] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [loading, setLoading] = useState(true)

  const videoRef = useRef<HTMLVideoElement>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const shotUrlRef = useRef('')

  useEffect(() => {
    shotUrlRef.current = shotUrl
  }, [shotUrl])

  function stopCamera() {
    streamRef.current?.getTracks().forEach((t) => t.stop())
    streamRef.current = null
    setCameraOn(false)
    setCameraReady(false)
  }

  useEffect(() => {
    return () => {
      streamRef.current?.getTracks().forEach((t) => t.stop())
      streamRef.current = null
      if (shotUrlRef.current) URL.revokeObjectURL(shotUrlRef.current)
    }
  }, [])

  // 摄像头开启后才渲染 video，等元素挂载后再绑定流
  useEffect(() => {
    if (!cameraOn) return
    const video = videoRef.current
    const stream = streamRef.current
    if (!video || !stream) return
    if (video.srcObject !== stream) video.srcObject = stream
    void video.play().catch(() => undefined)
  }, [cameraOn])

  async function loadHistory() {
    setLoading(true)
    try {
      const data = await api<MedicationCheckList>(
        '/api/ai/medication-checks?page_size=20',
      )
      setHistory(data.items)
      setRetentionDays(data.retention_days)
      setDisclaimer(data.disclaimer)
    } catch (e) {
      setError(e instanceof Error ? e.message : '记录加载失败')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadHistory()
  }, [])

  function clearShot() {
    if (shotUrl) URL.revokeObjectURL(shotUrl)
    setShot(null)
    setShotUrl('')
    setResult(null)
  }

  async function startCamera() {
    setError('')
    clearShot()
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('当前浏览器不支持摄像头，请改用「选择图片」')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'environment' },
        audio: false,
      })
      streamRef.current = stream
      setCameraOn(true)
      setCameraReady(false)
    } catch {
      stopCamera()
      setError('无法打开摄像头，请检查权限，或改用「选择图片」')
    }
  }

  async function takePhoto() {
    const video = videoRef.current
    if (!video || !video.videoWidth) return
    const canvas = document.createElement('canvas')
    canvas.width = video.videoWidth
    canvas.height = video.videoHeight
    const ctx = canvas.getContext('2d')
    if (!ctx) return
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise<Blob | null>((resolve) =>
      canvas.toBlob((b) => resolve(b), 'image/jpeg', 0.9),
    )
    if (!blob) {
      setError('拍照失败，请重试')
      return
    }
    stopCamera()
    setShot(blob)
    setShotUrl(URL.createObjectURL(blob))
    setResult(null)
  }

  function pickFile(file: File | null) {
    if (!file) return
    if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
      setError('仅支持 JPG / PNG / WebP 图片')
      return
    }
    setError('')
    stopCamera()
    clearShot()
    setShot(file)
    setShotUrl(URL.createObjectURL(file))
  }

  async function submit() {
    if (!shot || submitting) return
    setSubmitting(true)
    setError('')
    try {
      const data = await apiUpload<MedicationCheck>(
        '/api/ai/medication-checks',
        shot,
        { mode },
        'medication.jpg',
      )
      setResult(data)
      setDisclaimer(data.disclaimer)
      await loadHistory()
    } catch (e) {
      setError(e instanceof Error ? e.message : '检测失败，请重试')
    } finally {
      setSubmitting(false)
    }
  }

  async function removeHistory(id: number) {
    if (!confirm('删除这条检测记录？')) return
    try {
      await api(`/api/ai/medication-checks/${id}`, { method: 'DELETE' })
      setHistory((prev) => prev.filter((x) => x.id !== id))
    } catch (e) {
      setError(e instanceof Error ? e.message : '删除失败')
    }
  }

  const activeMode = MODES.find((m) => m.value === mode) ?? MODES[0]

  return (
    <div className="screen stack-gap">
      <Link to="/services" className="back-link">
        ← 返回服务
      </Link>
      <div className="page-title">
        <div>
          <h1>用药动作检测</h1>
          <p className="sub">拍下用药过程，仅反馈步骤是否完成</p>
        </div>
      </div>

      {error ? <p className="error">{error}</p> : null}

      <div className="chip-row">
        {MODES.map((m) => (
          <button
            key={m.value}
            type="button"
            className={`chip${mode === m.value ? ' active' : ''}`}
            onClick={() => {
              setMode(m.value)
              clearShot()
            }}
          >
            {m.label}
          </button>
        ))}
      </div>
      <p className="meta" style={{ margin: 0 }}>
        {activeMode.hint}
      </p>

      <section className="item-card ai-camera-card">
        <div className="ai-viewport">
          {shotUrl ? (
            <img src={shotUrl} alt="待检测的用药画面" className="ai-shot" />
          ) : cameraOn ? (
            <video
              ref={videoRef}
              className="ai-video"
              playsInline
              muted
              autoPlay
              onCanPlay={() => setCameraReady(true)}
            />
          ) : (
            <div className="ai-placeholder">
              <span>📷</span>
              <p>打开摄像头拍摄，或选择一张图片</p>
            </div>
          )}
        </div>

        <div className="row-actions ai-actions">
          {shotUrl ? (
            <>
              <button
                type="button"
                className="btn primary small"
                disabled={submitting}
                onClick={() => void submit()}
              >
                {submitting ? '检测中…' : '开始检测'}
              </button>
              <button
                type="button"
                className="btn small"
                disabled={submitting}
                onClick={() => {
                  clearShot()
                  void startCamera()
                }}
              >
                重新拍摄
              </button>
            </>
          ) : cameraOn ? (
            <>
              <button
                type="button"
                className="btn primary small"
                disabled={!cameraReady}
                onClick={() => void takePhoto()}
              >
                拍照
              </button>
              <button type="button" className="btn small" onClick={stopCamera}>
                关闭摄像头
              </button>
            </>
          ) : (
            <>
              <button type="button" className="btn primary small" onClick={() => void startCamera()}>
                打开摄像头
              </button>
              <button
                type="button"
                className="btn small"
                onClick={() => fileRef.current?.click()}
              >
                选择图片
              </button>
            </>
          )}
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          hidden
          onChange={(e) => {
            pickFile(e.target.files?.[0] ?? null)
            e.target.value = ''
          }}
        />
        <p className="meta" style={{ marginBottom: 0 }}>
          原始影像仅用于本次检测，处理后立即丢弃，不保存到服务器。
        </p>
      </section>

      {result ? (
        <section className="item-card">
          <div className="lesson-head">
            <h3 className="section-label">检测结果</h3>
            <span className="badge soft">
              {result.mode === 'inhale' ? '吸入剂' : '口服药'}
              {result.provider === 'demo' ? ' · 演示' : ''}
            </span>
          </div>
          {result.steps.length === 0 ? (
            <p className="muted">本次没有可用的步骤结果。</p>
          ) : (
            <ul className="ai-steps">
              {result.steps.map((step, i) => (
                <li key={`${step.name}-${i}`} className={step.done ? 'done' : 'todo'}>
                  <span className="ai-step-mark">{step.done ? '✓' : '○'}</span>
                  <span>{step.name}</span>
                  <span className="meta">{step.done ? '已完成' : '待完成'}</span>
                </li>
              ))}
            </ul>
          )}
          <p className={result.needs_retry ? 'error' : 'ok-tip'}>
            {result.needs_retry
              ? '还有步骤未完成，可以重拍一次，或回看课程中的用药示范。'
              : '本次步骤均已完成。'}
          </p>
          {result.message ? <p className="meta">{result.message}</p> : null}
          {result.needs_retry ? (
            <Link to="/courses" className="linkish primary">
              回看课程 →
            </Link>
          ) : null}
          <p className="meta">{result.disclaimer || disclaimer}</p>
        </section>
      ) : null}

      <section>
        <h3 className="section-label">检测记录</h3>
        <p className="meta" style={{ marginTop: 0 }}>
          仅保存步骤摘要，保留 {retentionDays} 天后自动清理。
        </p>
        {loading ? (
          <p className="muted">加载中…</p>
        ) : history.length === 0 ? (
          <p className="muted">暂无检测记录</p>
        ) : (
          <ul className="list-card">
            {history.map((item) => {
              const done = item.steps.filter((s) => s.done).length
              return (
                <li key={item.id}>
                  <h3>
                    {item.status === 'failed'
                      ? '检测失败'
                      : `${item.mode === 'inhale' ? '吸入剂' : '口服药'}检测`}
                    <span className={`badge ${item.status === 'failed' ? 'danger' : 'soft'}`}>
                      {item.status === 'failed'
                        ? '失败'
                        : `${done}/${item.steps.length} 步`}
                    </span>
                  </h3>
                  <p className="meta">{formatDateTime(item.created_at)}</p>
                  {item.message ? <p className="meta">{item.message}</p> : null}
                  <div className="row-actions">
                    <button
                      type="button"
                      className="linkish"
                      onClick={() => void removeHistory(item.id)}
                    >
                      删除
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
        {disclaimer ? <p className="mall-footnote">{disclaimer}</p> : null}
      </section>
    </div>
  )
}
