/**
 * 中文语音朗读封装（浏览器内置 Web Speech API）
 *
 * 已知限制（README 中有说明）：
 *  - 依赖设备本地安装的中文语音包。iPad / Windows 一般自带中文语音，但
 *    是否能完全离线朗读取决于系统语音包是否已下载完毕。
 *  - 本模块只做「请求朗读」，无法保证离线可用性，因此界面会在不支持时
 *    明确提示，而不是让按钮看起来正常却毫无反应。
 */

const synth = typeof window !== 'undefined' ? window.speechSynthesis : undefined

export const speechSupported = Boolean(synth && typeof window.SpeechSynthesisUtterance === 'function')

let voices = []
let voiceReady = false
let current = null
let state = 'idle' // idle | speaking | paused
let keepAlive = null

function pickChineseVoice() {
  if (!voices.length) return null
  const zh = voices.filter((v) => /^zh/i.test(v.lang || ''))
  if (!zh.length) return null
  // 优先普通话
  const mandarin = zh.filter((v) => /zh[-_]?(CN|Hans|SG)/i.test(v.lang || ''))
  const pool = mandarin.length ? mandarin : zh
  // 本地语音优先（online=false 的语音包一般随系统安装，离线更可能可用）
  return pool.find((v) => v.localService) || pool[0]
}

function loadVoices() {
  if (!speechSupported) return
  voices = synth.getVoices() || []
  if (voices.length && !voiceReady) {
    voiceReady = true
    synth.onvoiceschanged = () => {
      voices = synth.getVoices() || []
    }
  }
}

if (speechSupported) {
  loadVoices()
  // 某些浏览器需要监听一次才会填充语音列表
  synth.addEventListener?.('voiceschanged', loadVoices)
}

/** iOS Safari 上长句朗读会在 ~15s 后静默暂停，这里定时唤醒。 */
function startKeepAlive() {
  stopKeepAlive()
  if (!speechSupported) return
  keepAlive = setInterval(() => {
    if (synth.speaking && !synth.paused) {
      synth.pause()
      synth.resume()
    }
  }, 9000)
}

function stopKeepAlive() {
  if (keepAlive) {
    clearInterval(keepAlive)
    keepAlive = null
  }
}

export function getState() {
  return state
}

/**
 * 朗读一段文字。会先取消正在进行的朗读。
 * @returns {boolean} 是否成功发起朗读
 */
export function speak(text) {
  if (!speechSupported) return false
  stop()
  const u = new SpeechSynthesisUtterance(text)
  u.lang = 'zh-CN'
  u.rate = 0.85 // 给小朋友听，稍慢一点
  u.pitch = 1.06
  u.volume = 1
  const v = pickChineseVoice()
  if (v) u.voice = v
  u.onstart = () => {
    state = 'speaking'
    startKeepAlive()
  }
  u.onend = () => {
    state = 'idle'
    stopKeepAlive()
    notify()
  }
  u.onerror = () => {
    state = 'idle'
    stopKeepAlive()
    notify()
  }
  current = u
  state = 'speaking'
  synth.speak(u)
  return true
}

export function pause() {
  if (!speechSupported || !synth.speaking || synth.paused) return
  synth.pause()
  state = 'paused'
  stopKeepAlive()
  notify()
}

export function resume() {
  if (!speechSupported || !synth.speaking || !synth.paused) return
  synth.resume()
  state = 'speaking'
  startKeepAlive()
  notify()
}

/** 停止朗读（切换页面、切换故事、离开应用时都要调用）。 */
export function stop() {
  stopKeepAlive()
  if (!speechSupported) return
  current = null
  state = 'idle'
  try {
    synth.cancel()
  } catch {
    /* 部分浏览器在未开始朗读时 cancel 会抛错，忽略即可 */
  }
  notify()
}

const listeners = new Set()
function notify() {
  listeners.forEach((fn) => fn(state))
}
export function onStateChange(fn) {
  listeners.add(fn)
  return () => listeners.delete(fn)
}

/** 浏览器是否装了中文语音包（用于给出更精确的提示）。 */
export function hasChineseVoice() {
  loadVoices()
  return Boolean(pickChineseVoice())
}
