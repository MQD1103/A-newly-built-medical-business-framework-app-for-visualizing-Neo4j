import { useEffect, useRef, useState } from 'react'

/**
 * 搜索框语音输入麦克风按钮（可复用）。
 * - 点击开始识别（Web Speech API，zh-CN），说话时实时把文字写进搜索框；
 * - 识别中按钮变红脉冲，上方气泡提示「正在听，请开始讲话…」；
 * - 浏览器不支持 / 麦克风被拒 / 网络不通时，用气泡给出原因；
 * - 用法：<VoiceMic onInterim={setSearch} onFinal={setSearch} />
 */

type SpeechAlt = { transcript: string }
type SpeechResult = { isFinal: boolean; length: number; [index: number]: SpeechAlt }
type SpeechResultList = { length: number; [index: number]: SpeechResult }
type SpeechEvent = { resultIndex: number; results: SpeechResultList }
type RecognitionLike = {
  lang: string
  continuous: boolean
  interimResults: boolean
  maxAlternatives: number
  start: () => void
  stop: () => void
  abort: () => void
  onstart: (() => void) | null
  onresult: ((event: SpeechEvent) => void) | null
  onerror: ((event: { error: string }) => void) | null
  onend: (() => void) | null
}
type RecognitionCtor = new () => RecognitionLike

function getSpeechCtor(): RecognitionCtor | null {
  const w = window as unknown as {
    SpeechRecognition?: RecognitionCtor
    webkitSpeechRecognition?: RecognitionCtor
  }
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null
}

function errorText(code: string): string {
  switch (code) {
    case 'not-allowed':
    case 'service-not-allowed':
      return '麦克风权限被拒：点地址栏左侧 🔒 → 麦克风 → 允许，再刷新页面'
    case 'no-speech':
      return '没听清，再点一次麦克风试试'
    case 'audio-capture':
      return '没有找到麦克风设备'
    case 'network':
      return '语音服务连不上，请直接打字'
    default:
      return '语音识别失败，请直接打字'
  }
}

const TIP_LISTEN = '正在听，请开始讲话…'

type Props = {
  /** 中间结果（边说边出字） */
  onInterim: (text: string) => void
  /** 最终结果（说完确认） */
  onFinal: (text: string) => void
}

export default function VoiceMic({ onInterim, onFinal }: Props) {
  const [listening, setListening] = useState(false)
  const [tip, setTip] = useState('')
  const recognitionRef = useRef<RecognitionLike | null>(null)
  const finalRef = useRef('')
  const tipTimerRef = useRef<number | null>(null)
  /** 本次识别是否已用气泡报过错；结束时避免把错误提示立刻冲掉 */
  const erroredRef = useRef(false)

  useEffect(() => {
    return () => {
      recognitionRef.current?.abort()
      recognitionRef.current = null
      if (tipTimerRef.current) window.clearTimeout(tipTimerRef.current)
    }
  }, [])

  function showTip(text: string, autoHideMs = 0) {
    setTip(text)
    if (tipTimerRef.current) {
      window.clearTimeout(tipTimerRef.current)
      tipTimerRef.current = null
    }
    if (autoHideMs > 0) {
      tipTimerRef.current = window.setTimeout(() => setTip(''), autoHideMs)
    }
  }

  function toggle() {
    if (listening) {
      recognitionRef.current?.stop()
      return
    }
    const Ctor = getSpeechCtor()
    if (!Ctor) {
      showTip('当前浏览器不支持语音输入，直接打字也可以～', 2800)
      return
    }
    finalRef.current = ''
    erroredRef.current = false
    const recognition = new Ctor()
    recognition.lang = 'zh-CN'
    recognition.continuous = false
    recognition.interimResults = true
    recognition.maxAlternatives = 1

    recognition.onstart = () => {
      setListening(true)
      showTip(TIP_LISTEN)
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
      if (finalText) {
        finalRef.current += finalText
        onInterim(finalRef.current)
      } else if (interim) {
        onInterim(interim)
      }
    }

    recognition.onerror = (event) => {
      setListening(false)
      recognitionRef.current = null
      if (event.error !== 'aborted') {
        erroredRef.current = true
        showTip(errorText(event.error), 3000)
      }
    }

    recognition.onend = () => {
      setListening(false)
      recognitionRef.current = null
      if (finalRef.current) {
        onFinal(finalRef.current)
        showTip('✓ 已识别', 1200)
      } else if (!erroredRef.current) {
        // 没说也没报错（例如直接点了停止）：收起气泡
        showTip('')
      }
    }

    recognitionRef.current = recognition
    try {
      recognition.start()
    } catch {
      setListening(false)
      recognitionRef.current = null
      showTip('语音启动失败，请直接打字', 2600)
    }
  }

  return (
    <span className="voice-mic-wrap">
      {tip && (
        <span className="voice-tip" role="status" aria-live="polite">
          {tip}
        </span>
      )}
      <button
        type="button"
        className={`voice-mic${listening ? ' listening' : ''}`}
        onClick={toggle}
        aria-label={listening ? '停止语音输入' : '语音输入'}
        title={listening ? '停止语音' : '语音输入'}
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
    </span>
  )
}
