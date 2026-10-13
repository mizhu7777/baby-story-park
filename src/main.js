import './styles.css'
import storiesUrl from './data/stories.json?url'
import * as speech from './speech.js'

/* ------------------------------------------------------------------ 常量 */
const APP_BASE = new URL(import.meta.env.BASE_URL, location.href)
const asset = (p) => new URL(p, APP_BASE).href

const app = document.getElementById('app')
let stories = []

/* ------------------------------------------------------------------ 工具 */
const el = (html) => {
  const t = document.createElement('template')
  t.innerHTML = html.trim()
  return t.content.firstElementChild
}

const escapeHtml = (s) =>
  String(s).replace(
    /[&<>"']/g,
    (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c],
  )

const LETTERS = ['A', 'B', 'C', 'D', 'E']

function parseHash() {
  const raw = location.hash.replace(/^#/, '') || '/'
  const parts = raw.split('/').filter(Boolean)
  if (parts[0] === 'story' && parts[1]) {
    const story = stories.find((s) => s.id === parts[1])
    if (story) {
      if (parts[2] === 'quiz') return { view: 'quiz', story }
      return { view: 'reader', story, page: Math.min(Math.max(Number(parts[2]) || 1, 1), story.pages.length) }
    }
  }
  return { view: 'home' }
}

/* ================================================================== 首页 */
function renderHome() {
  speech.stop()
  const cards = stories
    .map(
      (s) => `
      <button class="card" data-story="${s.id}">
        <img class="card__img" src="${asset(s.cover)}" alt="${escapeHtml(s.title)}" loading="lazy" decoding="async" />
        <div class="card__body">
          <div class="card__name">${escapeHtml(s.title)}</div>
          <div class="card__theme">${escapeHtml(s.theme)}</div>
          <div class="card__go"><span class="btn__emoji">▶</span>读故事</div>
        </div>
      </button>`,
    )
    .join('')

  app.replaceChildren(
    el(`
    <div class="view home">
      <div class="home__head">
        <h1 class="home__title">宝宝的故事乐园</h1>
        <p class="home__sub">选一个故事，我们一起读～</p>
      </div>
      <div class="offline-box">
        <div class="offline-panel">
          <div class="offline-panel__label"><span class="btn__emoji">📥</span>离线也能读</div>
          <div class="offline-status" id="cache-status">还没有下载离线内容</div>
          <div class="offline-panel__spacer"></div>
          <button class="btn btn--mint" id="btn-cache">准备离线内容</button>
          <div class="progress" id="cache-progress" hidden><div class="progress__bar" id="cache-bar"></div></div>
        </div>
      </div>
      <div class="home__grid">${cards}</div>
    </div>`),
  )

  app.querySelectorAll('.card').forEach((c) => {
    c.addEventListener('click', () => {
      location.hash = `#/story/${c.dataset.story}`
    })
  })
  app.querySelector('#btn-cache').addEventListener('click', cacheAllStories)
  refreshCacheStatus()
}

/* ============================================================== 故事阅读页 */
function renderReader(story, page) {
  speech.stop()
  const total = story.pages.length
  const item = story.pages[page - 1]

  const dots = story.pages
    .map((_, i) => {
      const n = i + 1
      const cls = n === page ? 'dot dot--active' : n < page ? 'dot dot--done' : 'dot'
      return `<span class="${cls}" aria-hidden="true"></span>`
    })
    .join('')

  const speechBtn = speech.speechSupported
    ? `<button class="btn btn--primary" id="btn-speak"><span class="btn__emoji">🔊</span><span id="speak-label">朗读</span></button>
       <button class="btn btn--ghost" id="btn-respeak" hidden><span class="btn__emoji">🔁</span>再读一次</button>`
    : ''

  const note = speech.speechSupported
    ? ''
    : `<div class="speech-note">这台设备不支持朗读功能，故事文字依然可以正常阅读哦。</div>`

  const isLast = page === total

  app.replaceChildren(
    el(`
    <div class="view reader">
      <div class="topbar">
        <button class="btn btn--ghost btn--icon" id="btn-home" aria-label="回到首页"><span class="btn__emoji">🏠</span></button>
        <h1 class="topbar__title">${escapeHtml(story.title)}</h1>
        <div class="topbar__spacer"></div>
        <div class="offline-status">第 ${page} / ${total} 页</div>
      </div>

      <div class="reader__progress"><div class="dots">${dots}</div></div>

      <div class="reader__stage">
        <figure class="reader__figure">
          <img class="reader__img" id="page-img" src="${asset(item.image)}"
               alt="${escapeHtml(story.title)}第${page}页" decoding="async" />
        </figure>
        <div class="reader__panel">
          <p class="reader__text" id="page-text">${escapeHtml(item.text)}</p>
          ${note}
        </div>
      </div>

      <div class="reader__controls">
        <button class="btn" id="btn-prev" ${page === 1 ? 'disabled' : ''}><span class="btn__emoji">◀</span>上一页</button>
        <div class="reader__spacer"></div>
        ${speechBtn}
        <div class="reader__spacer"></div>
        ${
          isLast
            ? `<button class="btn btn--mint" id="btn-quiz"><span class="btn__emoji">🎯</span>回答问题</button>`
            : `<button class="btn btn--primary" id="btn-next">下一页<span class="btn__emoji">▶</span></button>`
        }
      </div>
    </div>`),
  )

  const img = app.querySelector('#page-img')
  img.addEventListener('load', () => {
    const r = img.getBoundingClientRect()
    // 兜底：如果极端情况下图片被压缩变形，还原为原始比例
    if (img.naturalWidth && r.height && r.width / r.height > img.naturalWidth / img.naturalHeight + 0.05) {
      img.style.objectFit = 'contain'
    }
  })
  img.addEventListener('error', () => {
    img.replaceWith(
      el('<div class="speech-note">这一页的图片暂时找不到了，请检查网络后重试。</div>'),
    )
  })

  app.querySelector('#btn-home').addEventListener('click', () => {
    location.hash = '#/'
  })
  app.querySelector('#btn-prev').addEventListener('click', () => {
    location.hash = `#/story/${story.id}/${page - 1}`
  })
  const nextBtn = app.querySelector('#btn-next')
  if (nextBtn) {
    nextBtn.addEventListener('click', () => {
      location.hash = `#/story/${story.id}/${page + 1}`
    })
  }
  const quizBtn = app.querySelector('#btn-quiz')
  if (quizBtn) {
    quizBtn.addEventListener('click', () => {
      location.hash = `#/story/${story.id}/quiz`
    })
  }

  if (speech.speechSupported) {
    const speakBtn = app.querySelector('#btn-speak')
    const label = app.querySelector('#speak-label')
    const reBtn = app.querySelector('#btn-respeak')
    const text = item.text

    speakBtn.addEventListener('click', () => {
      const st = speech.getState()
      if (st === 'speaking') {
        speech.pause()
      } else if (st === 'paused') {
        speech.resume()
      } else {
        speech.speak(text)
      }
    })
    reBtn.addEventListener('click', () => speech.speak(text))

    const paint = (st) => {
      if (st === 'speaking') {
        label.textContent = '暂停'
        speakBtn.querySelector('.btn__emoji').textContent = '⏸'
        reBtn.hidden = false
      } else if (st === 'paused') {
        label.textContent = '继续'
        speakBtn.querySelector('.btn__emoji').textContent = '▶'
        reBtn.hidden = false
      } else {
        label.textContent = '朗读'
        speakBtn.querySelector('.btn__emoji').textContent = '🔊'
        reBtn.hidden = true
      }
    }
    speech.onStateChange(paint)
    paint('idle')
  }
}

/* ================================================================ 问答页 */
function renderQuiz(story) {
  speech.stop()
  const q = story.quiz
  const options = q.options
    .map(
      (text, i) => `
      <button class="option" data-index="${i}">
        <span class="option__mark">${LETTERS[i]}</span>
        <span>${escapeHtml(text)}</span>
      </button>`,
    )
    .join('')

  app.replaceChildren(
    el(`
    <div class="view quiz">
      <div class="topbar">
        <button class="btn btn--ghost btn--icon" id="btn-home" aria-label="回到首页"><span class="btn__emoji">🏠</span></button>
        <h1 class="topbar__title">一起想一想</h1>
        <div class="topbar__spacer"></div>
        <button class="btn btn--ghost" id="btn-reread"><span class="btn__emoji">📖</span>再读一遍</button>
      </div>

      <div class="quiz__panel">
        <h2 class="quiz__question">${escapeHtml(q.question)}</h2>
        <div class="quiz__options" id="options">${options}</div>
        <div id="feedback"></div>
        <div class="quiz__actions" id="actions" hidden>
          <button class="btn btn--mint" id="btn-again"><span class="btn__emoji">🔁</span>再读故事</button>
          <button class="btn btn--primary" id="btn-back"><span class="btn__emoji">🏠</span>回到首页</button>
        </div>
      </div>
    </div>`),
  )

  app.querySelector('#btn-home').addEventListener('click', () => {
    location.hash = '#/'
  })
  app.querySelector('#btn-reread').addEventListener('click', () => {
    location.hash = `#/story/${story.id}`
  })
  app.querySelector('#btn-again').addEventListener('click', () => {
    location.hash = `#/story/${story.id}`
  })
  app.querySelector('#btn-back').addEventListener('click', () => {
    location.hash = '#/'
  })

  const feedback = app.querySelector('#feedback')
  const actions = app.querySelector('#actions')
  const optionEls = [...app.querySelectorAll('.option')]
  let solved = false

  optionEls.forEach((btn) => {
    btn.addEventListener('click', () => {
      if (solved) return
      const idx = Number(btn.dataset.index)
      if (idx === q.answerIndex) {
        solved = true
        btn.classList.add('option--correct')
        btn.querySelector('.option__mark').textContent = '✅'
        optionEls.forEach((o) => o !== btn && o.classList.add('option--dim'))
        feedback.replaceChildren(
          el(
            `<div class="quiz__feedback quiz__feedback--good">🎉 答对啦！${escapeHtml(q.explanation)}</div>`,
          ),
        )
        actions.hidden = false
      } else {
        btn.classList.add('option--wrong')
        btn.querySelector('.option__mark').textContent = '🙂'
        btn.disabled = true
        feedback.replaceChildren(
          el(`<div class="quiz__feedback quiz__feedback--try">再想一想哦，我们换一个试试～</div>`),
        )
      }
    })
  })
}

/* ================================================================== 路由 */
function render() {
  if (!stories.length) return
  const route = parseHash()
  if (route.view === 'reader') renderReader(route.story, route.page)
  else if (route.view === 'quiz') renderQuiz(route.story)
  else renderHome()
}

window.addEventListener('hashchange', render)

// 离开页面 / 切到后台时停止朗读，避免在后台一直念
window.addEventListener('pagehide', () => speech.stop())
document.addEventListener('visibilitychange', () => {
  if (document.hidden) speech.stop()
})

/* ========================================================== 离线缓存逻辑 */
// 内容缓存的名字由 Service Worker 用自己的 VERSION 决定，
// 这里不要写死版本号，否则两边会对不上。用前缀查找即可。
const CONTENT_CACHE_PREFIX = 'story-content-'

/** 应用运行需要的全部 URL：shell + 故事 JSON + 25 张插画 + 图标 + 已加载的 JS/CSS。 */
function collectAssetUrls() {
  const urls = new Set([APP_BASE.href, asset(storiesUrl), asset('manifest.webmanifest')])
  ;['icons/icon-192.png', 'icons/icon-512.png', 'icons/icon-maskable-512.png'].forEach((p) => urls.add(asset(p)))
  stories.forEach((s) => {
    urls.add(asset(s.cover))
    s.pages.forEach((p) => urls.add(asset(p.image)))
  })
  document.querySelectorAll('script[src], link[rel="stylesheet"][href]').forEach((el) => {
    urls.add(new URL(el.getAttribute('src') || el.getAttribute('href'), APP_BASE).href)
  })
  return [...urls]
}

async function cacheAllStories() {
  const btn = document.getElementById('btn-cache')
  const status = document.getElementById('cache-status')
  const wrap = document.getElementById('cache-progress')
  const bar = document.getElementById('cache-bar')

  const urls = collectAssetUrls()
  btn.disabled = true
  wrap.hidden = false
  bar.className = 'progress__bar'
  bar.style.width = '0%'
  status.textContent = `正在下载 0 / ${urls.length}`

  try {
    if (!('serviceWorker' in navigator)) {
      throw new Error('当前浏览器不支持离线缓存')
    }
    const reg = await navigator.serviceWorker.ready
    const worker = navigator.serviceWorker.controller || reg.active
    if (!worker) throw new Error('离线缓存还没准备好，请稍后再试')

    const done = await new Promise((resolve, reject) => {
      const onMessage = (event) => {
        const d = event.data || {}
        if (d.type === 'cache-progress') {
          bar.style.width = `${Math.round((d.done / d.total) * 100)}%`
          status.textContent = `正在下载 ${d.done} / ${d.total}`
        } else if (d.type === 'cache-done') {
          navigator.serviceWorker.removeEventListener('message', onMessage)
          d.error ? reject(new Error(d.error)) : resolve(d.count)
        } else if (d.type === 'cache-error') {
          navigator.serviceWorker.removeEventListener('message', onMessage)
          reject(new Error(d.error))
        }
      }
      navigator.serviceWorker.addEventListener('message', onMessage)
      worker.postMessage({ type: 'CACHE_URLS', urls })
      setTimeout(() => reject(new Error('下载超时，请检查网络后重试')), 180000)
    })

    bar.className = 'progress__bar progress__bar--done'
    bar.style.width = '100%'
    status.textContent = `离线内容已准备好（${done} 个文件），断网也能读`
    btn.textContent = '已准备完成'
  } catch (err) {
    bar.className = 'progress__bar progress__bar--error'
    status.textContent = `下载失败：${err.message}`
    btn.disabled = false
    btn.textContent = '重试'
  }
}

async function refreshCacheStatus() {
  const status = document.getElementById('cache-status')
  const btn = document.getElementById('btn-cache')
  if (!status) return
  if (!('caches' in window)) {
    status.textContent = '当前浏览器不支持离线缓存'
    btn.disabled = true
    return
  }
  try {
    const contentCaches = (await caches.keys()).filter((name) => name.startsWith(CONTENT_CACHE_PREFIX))
    const counts = await Promise.all(
      contentCaches.map((name) => caches.open(name).then((c) => c.keys()).then((k) => k.length)),
    )
    const total = counts.reduce((a, b) => a + b, 0)
    if (total > 0) {
      status.textContent = `离线内容已缓存 ${total} 个文件`
      btn.textContent = '重新下载'
    }
  } catch {
    /* 查询失败不影响阅读 */
  }
}

async function registerServiceWorker() {
  if (!('serviceWorker' in navigator)) return
  try {
    await navigator.serviceWorker.register(asset('sw.js'), { scope: APP_BASE.href })
  } catch (err) {
    // 离线功能不可用时仍然可以正常在线阅读
    console.warn('Service Worker 注册失败：', err)
  }
}

/* ================================================================== 启动 */
async function boot() {
  app.replaceChildren(el('<div class="center-note">正在打开故事乐园…</div>'))
  try {
    const res = await fetch(storiesUrl)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    stories = await res.json()
  } catch (err) {
    app.replaceChildren(
      el(`<div class="center-note">故事内容加载失败（${escapeHtml(err.message)}）<br />请检查网络，或先点击「准备离线内容」后再试。</div>`),
    )
    return
  }
  render()
  registerServiceWorker()
}

boot()
