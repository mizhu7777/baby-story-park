/* 宝宝的故事乐园 — Service Worker
 *
 * 职责：
 *  1. 安装时先缓存最小外壳（页面 / 清单 / 图标），保证最基本的可打开。
 *  2. 用户在首页点击「准备离线内容」后，接收主线程发来的完整 URL 列表
 *     （故事 JSON + 25 张插画 + JS/CSS），逐个写入内容缓存并回报进度。
 *  3. 运行时采用「缓存优先 + 后台回填」，断网时直接命中缓存。
 *
 * 注意：本文件位于构建产物的根目录，所以 `./` 就是应用根路径，
 * 部署到任意子目录（如 GitHub Pages 项目站）都能正常工作。
 */

const VERSION = 'v2'
const SHELL_CACHE = `story-park-shell-${VERSION}`
const CONTENT_CACHE = `story-content-${VERSION}`

const SHELL_ASSETS = ['./', './manifest.webmanifest', './icons/icon-192.png', './icons/icon-512.png']

/* ------------------------------------------------------------------ 安装 */
self.addEventListener('install', (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE)
      // 逐个添加：某一个 404 不应该让整个安装失败
      await Promise.all(
        SHELL_ASSETS.map(async (url) => {
          try {
            const res = await fetch(new Request(url, { cache: 'reload' }))
            if (res.ok) await cache.put(url, res)
          } catch {
            /* 忽略单个资源失败 */
          }
        }),
      )
      await self.skipWaiting()
    })(),
  )
})

/* ------------------------------------------------------------------ 激活 */
self.addEventListener('activate', (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys()
      const keep = new Set([SHELL_CACHE, CONTENT_CACHE])
      // 旧版本缓存全部清掉。内容缓存里存着带哈希的 JS/CSS，
      // 不清理的话每次重新部署都会把上一版留在缓存里，越攒越多。
      await Promise.all(keys.filter((k) => k.startsWith('story-') && !keep.has(k)).map((k) => caches.delete(k)))
      await self.clients.claim()
    })(),
  )
})

/* ------------------------------------------------------- 缓存全部故事资源 */
async function cacheUrls(urls, cacheName) {
  const cache = await caches.open(cacheName)
  let done = 0
  const errors = []

  for (const url of urls) {
    try {
      // hits 命中说明之前已经缓存，跳过下载但仍然计入进度
      const hit = await cache.match(url, { ignoreSearch: false })
      if (!hit) {
        const res = await fetch(new Request(url, { cache: 'reload' }))
        if (canCache(url, res)) {
          await cache.put(url, res.clone())
        } else {
          errors.push(`${url}（${isHtml(res) ? '返回 HTML，文件可能不存在' : `HTTP ${res.status}`}）`)
        }
      }
    } catch (e) {
      errors.push(`${url}（${e.message}）`)
    }
    done += 1
    const client = (await self.clients.matchAll())[0]
    client?.postMessage({ type: 'cache-progress', done, total: urls.length })
  }

  const keys = await cache.keys()
  return { count: keys.length, errors }
}

/**
 * 静态资源不应该返回 HTML。
 * 很多静态托管（含 vite preview、GitHub Pages 的 SPA 回退）在文件缺失时
 * 会回退到 index.html 并返回 200 text/html，如果直接 put 进缓存，
 * 就会把一段 HTML 当成图片缓存下来——界面显示「离线已准备好」，
 * 实际离线打开时图片全是坏的。这里显式排除，宁可报失败也不要假装成功。
 *
 * 唯一例外是应用外壳本身（页面入口），它本来就应该是 HTML。
 */
function isHtml(res) {
  return /text\/html/i.test(res.headers.get('content-type') || '')
}

function isAppShell(url) {
  const p = new URL(url).pathname
  return p.endsWith('/') || p.endsWith('/index.html')
}

function canCache(url, res) {
  return res.ok && (!isHtml(res) || isAppShell(url))
}

self.addEventListener('message', (event) => {
  const data = event.data || {}
  if (data.type !== 'CACHE_URLS') return
  const reply = (msg) => event.ports[0]?.postMessage(msg) || event.source?.postMessage(msg)

  event.waitUntil(
    (async () => {
      try {
        const { count, errors } = await cacheUrls(data.urls || [], data.cacheName || CONTENT_CACHE)
        reply({ type: 'cache-done', count, error: errors.length ? errors[0] : null })
      } catch (err) {
        reply({ type: 'cache-error', error: err.message })
      }
    })(),
  )
})

/* ------------------------------------------------------------------ 请求 */
self.addEventListener('fetch', (event) => {
  const req = event.request
  if (req.method !== 'GET') return

  const url = new URL(req.url)
  if (url.origin !== self.location.origin) return

  // 页面导航：在线时优先网络并顺手刷新缓存里的 index.html；
  // 断网时回退到内容缓存（最新）→ 外壳缓存 → 占位页。
  if (req.mode === 'navigate') {
    event.respondWith(
      (async () => {
        try {
          const res = await fetch(req)
          // 必须在每次在线访问时更新 index.html。否则重新部署后，
          // 缓存里还留着指向旧哈希 JS/CSS 的 index.html，
          // 断网打开就是白屏。
          if (res.ok) (await caches.open(SHELL_CACHE)).put('./', res.clone())
          return res
        } catch {
          const content = await caches.open(CONTENT_CACHE)
          const shell = await caches.open(SHELL_CACHE)
          return (
            (await content.match('./')) ||
            (await content.match('index.html')) ||
            (await shell.match('./')) ||
            (await shell.match('index.html')) ||
            new Response('<h1>离线中</h1><p>请先联网打开一次并点击「准备离线内容」。</p>', {
              headers: { 'Content-Type': 'text/html; charset=utf-8' },
              status: 200,
            })
          )
        }
      })(),
    )
    return
  }

  // 静态资源：缓存优先，但命中结果要先验一下再返回。
  // 不能无条件相信缓存 —— 早期版本的缺陷曾把 HTML 当成图片写进缓存，
  // 而纯缓存优先会把这批坏数据永久喂给用户，只能靠手动清除站点数据才能恢复。
  // 这里做自愈：缓存里存的是 HTML 而请求的是图片/脚本等资源，就丢弃它走网络。
  event.respondWith(
    (async () => {
      const cached =
        (await caches.match(req)) ||
        (await (await caches.open(CONTENT_CACHE)).match(req)) ||
        (await (await caches.open(SHELL_CACHE)).match(req))

      const poisoned = cached && isHtml(cached) && !isAppShell(req.url)
      if (cached && !poisoned) return cached

      try {
        // 自愈时用 cache:'reload' 绕开浏览器自身的 HTTP 缓存，
        // 否则 HTTP 缓存里那份坏响应会被原样再取一次，白救一场。
        const res = await fetch(poisoned ? new Request(req, { cache: 'reload' }) : req)
        // 顺带把运行时新用到的资源补进缓存（例如哈希后的 JS/CSS）
        if (res.ok && res.type === 'basic' && canCache(req.url, res)) {
          const cache = await caches.open(CONTENT_CACHE)
          cache.put(req, res.clone())
        }
        // 即便网络也返回了 HTML，也不要把它当图片交出去，
        // 直接报 404，让页面走自己的「图片加载失败」提示。
        if (isHtml(res) && !isAppShell(req.url)) {
          return new Response('', { status: 404, statusText: 'not an asset' })
        }
        return res
      } catch (err) {
        return new Response('', { status: 504, statusText: 'offline' })
      }
    })(),
  )
})
