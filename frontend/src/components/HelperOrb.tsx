import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { SUGGESTIONS, isAdminOnlyRequest, matchIntent, type Intent } from '../helperIntents'

/**
 * 首页小助手：一颗可对话的球体。
 * - 点击：展开面板，输入自然语言后按关键词权重跳转到对应功能。
 * - 长按：直接唤起浏览器语音识别（Web Speech API），说完自动跳转。
 * 关键词匹配在本地完成；语音识别由浏览器自带的语音服务提供。
 */

type SpeechResultAlternative = { transcript: string }
type SpeechResult = {
  isFinal: boolean
  length: number
  [index: number]: SpeechResultAlternative
}
type SpeechResultList = {
  length: number
  [index: number]: SpeechResult
}
type SpeechResultEvent = { resultIndex: number; results: SpeechResultList }
type SpeechRecognitionLike = {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  start: () => void
  stop: () => void
  abort: () => void
  onstart: (() => void) | null
  onresult: ((event: SpeechResultEvent) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
}
type SpeechRecognitionCtor = new () => SpeechRecognitionLike

function getSpeechCtor(): SpeechRecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionCtor
    webkitSpeechRecognition?: SpeechRecognitionCtor
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

function speechErrorText(code: string): string {
  switch (code) {
    case 'not-allowed':
    case 'service-not-allowed':
      return '麦克风权限被拒绝，允许后长按再试一次'
    case 'no-speech':
      return '没听清，再说一次试试'
    case 'audio-capture':
      return '没有找到麦克风，先打字吧'
    case 'network':
      return '语音服务连不上，先打字吧'
    default:
      return '语音识别失败，先打字吧'
  }
}

/** 长按多久算“唤起语音” */
const LONG_PRESS_MS = 420

export default function HelperOrb() {
  const navigate = useNavigate()
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const [reply, setReply] = useState('')
  const [listening, setListening] = useState(false)
  const [voiceSupported] = useState(() => Boolean(getSpeechCtor()))
  const inputRef = useRef<HTMLInputElement>(null)
  const timerRef = useRef<number | null>(null)
  const pressTimerRef = useRef<number | null>(null)
  const longPressedRef = useRef(false)
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null)
  const voiceFinalRef = useRef('')

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearTimeout(timerRef.current)
      if (pressTimerRef.current) window.clearTimeout(pressTimerRef.current)
      recognitionRef.current?.abort()
    }
  }, [])

  function go(intent: Intent) {
    setReply(`好的，这就带你去「${intent.label}」`)
    if (timerRef.current) window.clearTimeout(timerRef.current)
    timerRef.current = window.setTimeout(() => {
      navigate(intent.to)
      setOpen(false)
      setReply('')
      setText('')
    }, 520)
  }

  function ask(raw: string) {
    const query = raw.trim()
    if (!query) return
    const intent = matchIntent(query, isAdmin)
    if (intent) {
      go(intent)
      return
    }
    if (!isAdmin && isAdminOnlyRequest(query)) {
      setReply('管理中心与代办功能仅管理员可用哦')
      return
    }
    setReply('还没找到对应功能，试试下面的快捷入口 👇')
  }

  function clearPressTimer() {
    if (pressTimerRef.current) {
      window.clearTimeout(pressTimerRef.current)
      pressTimerRef.current = null
    }
  }

  function closePanel() {
    setOpen(false)
    recognitionRef.current?.abort()
    recognitionRef.current = null
    setListening(false)
    voiceFinalRef.current = ''
  }

  function stopVoice() {
    recognitionRef.current?.stop()
  }

  function startVoice() {
    if (listening) {
      stopVoice()
      return
    }
    setOpen(true)
    voiceFinalRef.current = ''
    const Ctor = getSpeechCtor()
    if (!Ctor) {
      setReply('当前浏览器不支持语音输入，直接打字也可以～')
      return
    }
    const recognition = new Ctor()
    recognition.lang = 'zh-CN'
    recognition.continuous = false
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setListening(true)
      setReply('正在听，请说…')
    }

    recognition.onresult = (event) => {
      let interim = ''
      let finalText = ''
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i]
        const text = result[0]?.transcript ?? ''
        if (result.isFinal) finalText += text
        else interim += text
      }
      if (interim) {
        setText(interim)
        setReply(`听到：${interim}`)
      }
      if (finalText) {
        voiceFinalRef.current = finalText
        setText(finalText)
        setReply(`听到了「${finalText}」，正在识别…`)
      }
    }

    recognition.onerror = (event) => {
      setListening(false)
      voiceFinalRef.current = ''
      if (event.error !== 'aborted') setReply(speechErrorText(event.error))
    }

    recognition.onend = () => {
      setListening(false)
      recognitionRef.current = null
      const finalText = voiceFinalRef.current
      voiceFinalRef.current = ''
      if (finalText) ask(finalText)
    }

    recognitionRef.current = recognition
    try {
      recognition.start()
    } catch {
      setListening(false)
      recognitionRef.current = null
      setReply('语音启动失败，先打字吧')
    }
  }

  function onSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    ask(text)
  }

  function onOrbPointerDown() {
    longPressedRef.current = false
    clearPressTimer()
    pressTimerRef.current = window.setTimeout(() => {
      longPressedRef.current = true
      startVoice()
    }, LONG_PRESS_MS)
  }

  function onOrbClick() {
    // 长按已经触发语音，松手时不要再把面板关掉
    if (longPressedRef.current) {
      longPressedRef.current = false
      return
    }
    if (open) closePanel()
    else setOpen(true)
  }

  return (
    <div className="helper-wrap">
      {open && (
        <section
          className="helper-panel"
          role="dialog"
          aria-label="小医助手"
          onKeyDown={(e) => {
            if (e.key === 'Escape') closePanel()
          }}
        >
          <header className="helper-head">
            <span className="helper-head-dot" aria-hidden="true" />
            <div>
              <strong>小医助手</strong>
              <em>{listening ? '正在聆听，请说话…' : '打字，或长按球体说话'}</em>
            </div>
            <button
              type="button"
              className="helper-close"
              onClick={closePanel}
              aria-label="关闭小助手"
            >
              ×
            </button>
          </header>

          <p className={`helper-reply${listening ? ' listening' : ''}`} aria-live="polite">
            {reply || '例如：我的成绩 / 买课 / 加好友'}
          </p>

          <form className="helper-form" onSubmit={onSubmit}>
            <input
              ref={inputRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder={listening ? '正在听…' : '想去哪儿？'}
              aria-label="输入要去的功能"
              maxLength={40}
            />
            {voiceSupported && (
              <button
                type="button"
                className={`helper-mic${listening ? ' listening' : ''}`}
                onClick={startVoice}
                aria-label={listening ? '停止语音输入' : '语音输入'}
                title={listening ? '停止' : '语音输入'}
              >
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <path
                    d="M12 4a3 3 0 0 1 3 3v5a3 3 0 0 1-6 0V7a3 3 0 0 1 3-3Z"
                    fill="currentColor"
                  />
                  <path
                    d="M6.5 11.5a5.5 5.5 0 0 0 11 0M12 17v3"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            )}
            <button type="submit" className="helper-send" aria-label="跳转">
              →
            </button>
          </form>

          <div className="helper-chips">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => {
                  setText(s)
                  ask(s)
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </section>
      )}

      <button
        type="button"
        className={`helper-orb${open ? ' open' : ''}${listening ? ' listening' : ''}`}
        onClick={onOrbClick}
        onPointerDown={onOrbPointerDown}
        onPointerUp={clearPressTimer}
        onPointerLeave={clearPressTimer}
        onPointerCancel={clearPressTimer}
        onContextMenu={(e) => e.preventDefault()}
        aria-expanded={open}
        aria-label={open ? '收起小助手' : '打开小助手'}
        title="点击打开 · 长按说话"
      >
        <span className="helper-orb-ring" aria-hidden="true" />
        <svg className="helper-orb-icon" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M11.6 3.1c.5 3.1 2.5 5.1 5.6 5.6-3.1.5-5.1 2.5-5.6 5.6-.5-3.1-2.5-5.1-5.6-5.6 3.1-.5 5.1-2.5 5.6-5.6Z" />
          <path d="M18.1 14.4c.24 1.5 1.2 2.46 2.7 2.7-1.5.24-2.46 1.2-2.7 2.7-.24-1.5-1.2-2.46-2.7-2.7 1.5-.24 2.46-1.2 2.7-2.7Z" />
        </svg>
        <em>{listening ? '聆听中' : '助手'}</em>
      </button>
    </div>
  )
}
