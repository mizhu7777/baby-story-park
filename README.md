# 宝宝的故事乐园

面向 4 岁左右宝宝的中文图文故事学习 PWA。每个故事 5 页，每页一张独立场景插画 + 一小段正文，可朗读，结尾有一道互动问答。断网后依然可以正常阅读。

- 技术栈：Vite + 原生 JavaScript（无 UI 框架、无后端、无数据库）
- 适配：iPad 竖屏 / 横屏优先，同时可在 Windows 桌面浏览器开发调试

---

## 一、快速开始

```bash
cd baby-story-park

# 1) 安装依赖（只有一个开发依赖 vite）
npm install

# 2) 启动开发服务器
npm run dev            # 打开 http://localhost:5173

# 3) 构建生产版本
npm run build          # 产物输出到 dist/

# 4) 本地预览生产版本（Service Worker 只在 https 或 localhost 下生效）
npm run preview        # http://localhost:4173
```

> Service Worker（PWA 离线能力）要求 **HTTPS 或 localhost**。用局域网 IP 在手机上访问
> `http://192.168.x.x:5173` 时离线缓存不会生效，必须走下面的 HTTPS 部署方式。

---

## 二、目录结构

```
baby-story-park/
├── index.html                     应用入口
├── package.json
├── vite.config.js                 base:'./'，可部署到任意子目录
├── src/
│   ├── main.js                    启动、哈希路由、首页/阅读页/问答页、离线缓存逻辑
│   ├── styles.css                 全部样式（iPad 竖屏 + 横屏布局）
│   ├── speech.js                  中文语音朗读封装（Web Speech API）
│   └── data/
│       └── stories.json           10 个故事正文 + 问答（唯一内容源）
├── public/
│   ├── manifest.webmanifest       PWA 清单
│   ├── sw.js                      Service Worker（预缓存 + 离线回退）
│   ├── icons/                     PWA 图标（由 tools/make_icons.py 生成）
│   └── images/stories/
│       ├── story-01/page-01.webp … page-05.webp
│       ├── story-02/ … story-10/
├── tools/
│   ├── agnes_generate.py          用 Agnes AI 生成 50 张插画
│   └── make_icons.py              生成 PWA 图标
└── dist/                          构建产物
```

图片命名规则固定为 `public/images/stories/story-0N/page-0M.webp`，新增故事时按同样规则放置即可，
只需在 `src/data/stories.json` 里补一条记录，首页和阅读页会自动渲染。

---

## 三、内容管理

`src/data/stories.json` 是唯一的内容源，字段如下：

```jsonc
{
  "id": "story-01",
  "title": "小兔子第一次交朋友",
  "theme": "勇敢问候、友好相处",
  "cover": "images/stories/story-01/page-01.webp",   // 首页卡片用第 1 页，不额外占图片
  "pages": [
    { "image": "images/stories/story-01/page-01.webp", "text": "正文…" }
  ],
  "quiz": {
    "question": "…",
    "options": ["…", "…", "…"],
    "answerIndex": 1,          // 从 0 开始
    "explanation": "答对后的鼓励语"
  }
}
```

正文与问答逐字取自素材包 `宝宝故事屋_五个故事内容.json`，未做任何改写。

安全教育内容已按 4 岁孩子的理解能力处理：
- **小猫咪找回红气球**：明确写出「小猫咪很着急，但它没有爬树」「去找熟悉的大人帮忙」「遇到困难可以找信任的大人帮忙，不要冒险」。
- **小鸭子学游泳**：明确写出「我会一直在你身边，我们只在安全的浅水处练习」「玩水一定要有大人陪伴，不能自己跑到池塘边」。

---

## 四、插画生成（Agnes AI）

50 张插画由已安装的 **Agnes AI** Skill 生成，脚本在 `tools/agnes_generate.py`。

### 使用的参考图

| 用途 | 文件 |
| --- | --- |
| 整体画风与配色 | `reference-materials/配图/五个故事总览.png` |
| 角色外观 | `reference-materials/配图/0N_<故事>_封面配图.png` |
| 故事顺序与场景构图 | `reference-materials/配图/0N_<故事>_完整分镜.png` |

story-01 ~ story-05 有专属封面与分镜，三张图通过 `extra_body.image`（Data URI Base64 数组）
一起传入，作为**风格 / 角色 / 分镜参考**。

**story-06 ~ story-10 是后加的新故事，素材包里没有对应的封面/分镜**，
因此只用 `五个故事总览.png` 作为画风参考（脚本会自动判断，日志会打印「参考图 1 张」），
角色特征改由提示词中的 `CHARACTERS` 文字描述锁定。

提示词中明确要求「不要复制参考图的拼版排布」「忽略并不得复现参考图里的任何文字」。
最终图片是逐张重新生成的独立场景原画，**没有**裁剪总览海报，也没有把带文字的拼图当作单页插画。

### 接口要点（实测）

- 端点：`POST https://api.agnes-ai.cn/v1/images/generations`
- 模型：`agnes-image-2.1-flash`
- 图生图必须把 `image` 放进 `extra_body`，放顶层会 400
- `size` 必须是 16 的倍数 → 使用 `1024x768`（4:3 横向，适配故事阅读页）
- Base64 输出用 `extra_body.response_format: "b64_json"`
- **当前 Key 只对国内节点有效**，`apihub.agnes-ai.com` 会返回 `401 Invalid token`
- `agnes-image-2.0-flash` 返回「无可用渠道」，不可用

### 图生图通道不稳定，脚本有回退机制

实测中**图生图通道会整段不可用**：任何带 `extra_body.image` 的请求都会在
**0.5 秒内**返回 `503 生图队列已满`（与参考图数量、体积无关，43KB 和 175KB 载荷结果一样），
而同一时刻的**文生图请求 8.6 秒就能成功**。该通道也会自行恢复。

所以脚本默认用 `--mode auto`：

1. 先试 4 次图生图（每次间隔 20 秒）；
2. 图生图通道不可用时，**自动回退到 Agnes 文生图**——提示词里已经用文字完整描述了
   从参考图提取的画风与角色特征（见脚本里的 `STYLE` 与 `CHARACTERS`）；
3. 每张图实际用了哪种方式，记录在 `tools/.cache/provenance.json`。

两种方式都走 Agnes 官方接口，没有换用其他生图服务。

想强制只用参考图，或想把 t2i 生成的图升级成图生图版本：

```powershell
python tools/agnes_generate.py --mode img2img --force   # 只用参考图重做
```

### 重新生成

```powershell
# API Key 只从环境变量读取，不写进任何源码或前端配置
$env:AGNES_API_KEY = "sk-..."

python tools/agnes_generate.py                 # 生成全部 10 个故事
python tools/agnes_generate.py --story 3       # 只重做第 3 个故事
python tools/agnes_generate.py --story 3 --force   # 已存在也强制重做
python tools/agnes_generate.py --mode t2i      # 只用文生图
```

原始 PNG 落在 `tools/.cache/raw/`（已 gitignore），WebP 成品写入 `public/images/stories/`。

---

## 五、语音朗读

第一版使用浏览器内置的 **Web Speech API**（`zh-CN`），没有接入任何在线付费语音服务，前端不含任何密钥。

- 点「朗读」读当前页 → 再点变成「暂停」→ 再点「继续」
- 另设「🔁 再读一次」按钮，可从头重读
- 切换页面 / 切换故事 / 返回首页 / 切到后台时，自动 `cancel()` 上一页未播完的朗读
- 针对 iOS Safari 长句朗读会在约 15 秒后静默暂停的问题，加了定时 `pause()+resume()` 保活

**已知限制（重要）：**

1. **离线朗读无法保证。** 能否离线发音取决于设备本地是否装好了中文语音包。
   iPad / Windows 一般自带中文语音，但只要系统语音包还没下载完，断网时就可能没有声音。
   **第一版把「图片 + 故事文字的离线可用」作为确定目标，语音不作为离线承诺。**
2. **语音不支持时会明确提示。** 检测不到 `speechSynthesis` 时，朗读按钮整个不渲染，
   页面显示「这台设备不支持朗读功能」，不会出现「按钮看着正常但点了没反应」。
3. 实际能否朗读，取决于设备装了哪些中文语音包。请在目标 iPad 上实测一次。

---

## 六、PWA 与离线

- `public/manifest.webmanifest`：应用名、图标（192/512/maskable）、`standalone` 显示模式
- `public/sw.js`：安装时预缓存最小外壳；运行时「缓存优先 + 后台回填」
- 首页有明显的 **「📥 准备离线内容」** 按钮，点击后下载并缓存全部资源，并显示真实进度条与结果

缓存内容包含：应用外壳、故事 JSON、**10 个故事的 50 张插画**、CSS / JS、PWA 图标。

> 实现说明：Vite 会给构建产物加内容哈希，SW 无法在编写时知道最终文件名。
> 因此主线程在运行时收集「当前页面 + 故事 JSON 地址 + 50 张插画地址 + 页面已加载的 JS/CSS 地址」，
> 通过 `postMessage` 交给 SW 逐个写入缓存。这样无论哈希怎么变都不会漏缓存。

### 验证离线的方法

1. `npm run build && npm run preview`，打开 `http://localhost:4173`
2. 点「准备离线内容」，等进度条走完（应为 **33 个文件**）
3. **把服务器关掉**（`Ctrl+C`），再刷新页面：首页、故事文字、插画仍应正常显示

> 如果「已缓存 N 个文件」里的 N 大于 33，说明上一版带哈希的 JS/CSS 还留在缓存里。
> 把 `public/sw.js` 里的 `VERSION` 改成 `v2` 重新构建即可清理。
> 这是刻意的取舍：不清空缓存是为了避免下载中途失败导致孩子彻底读不了离线内容。

---

## 七、部署

最简单的方案是 **GitHub Pages**（无需服务器、无需备案）。

```bash
npm run build
```

然后把 `dist/` 里的内容推到仓库的 `gh-pages` 分支，或直接在仓库设置里把
Pages 的 Source 指向 `main` 分支的 `/docs`，把 `dist/` 内容复制进 `docs/`。

因为 `vite.config.js` 里设了 `base: './'`，产物全部使用相对路径，
**部署到 `https://<用户名>.github.io/<仓库名>/` 这样的子目录也能正常工作**，不需要额外改配置。

其他任选其一：

- **Cloudflare Pages**：Build command `npm run build`，Output directory `dist`
- **Vercel**：Framework preset `Vite`，Output directory `dist`
- **Netlify**：Build `npm run build`，Publish directory `dist`

> Service Worker 需要 HTTPS，上面几个平台默认都提供 HTTPS。
> 本仓库**不会**自动登录或发布到任何账号，部署动作请自行执行。

---

## 八、在 iPad 上添加到主屏幕

1. iPad 用 **Safari** 打开部署好的 HTTPS 网址（必须是 Safari，Chrome 版无法添加到主屏）
2. 点顶部工具栏中间的 **分享** 按钮 <kbd>􀈂</kbd>
3. 在菜单里向下滑，选 **「添加到主屏幕」**
4. 名称保持「宝宝的故事乐园」，右上角点 **添加**
5. 回到主屏幕，点新图标即可全屏打开（无 Safari 地址栏）

**第一次打开后，务必点一次首页的「📥 准备离线内容」**，等进度条走完。
之后断网、飞机模式下，10 个故事的文字和插画都能正常打开。

---

## 九、测试结果

见 `TEST-REPORT.md`。

---

## 十、维护备忘

- **加一个故事**：在 `src/data/stories.json` 追加一条记录 → 用 `agnes_generate.py` 生成
  `story-0N/page-01..05.webp` → 构建。首页和阅读页无需改代码。
- **改文案**：只改 `src/data/stories.json`，插画不用重新生成。
- **只重做某一张图**：`python tools/agnes_generate.py --story 2 --page 4 --force`
- **发布新版本**：把 `public/sw.js` 里的 `VERSION` 改成 `v2`（会清掉旧的缓存）。
  不改的话老用户下次点「重新下载」时，界面显示的文件数会大于 33。
- **重新生成图标**：`python tools/make_icons.py`
- **测速**：`python tools/speed_test_parallel.py http://<ip>:4173`
  （模拟浏览器 6 条并发连接，给出用户实际等待的墙钟时间；
  `speed_test.py` 是逐个资源的明细版，用来定位某个特别慢的文件）

### 局域网访问（平板 / 手机同 Wi-Fi）

```bash
npm run dev       # 或 npm run preview，会自动监听 0.0.0.0
ipconfig           # 找 WLAN 的 IPv4，例如 192.168.110.25
```

平板用 Safari 打开 `http://<那台电脑的IP>:5173/`。

⚠️ 局域网是 **HTTP**，Service Worker 不会注册，因此**没有离线功能**，
「准备离线内容」按钮不生效。要离线必须部署到 HTTPS（见第七节）。
「添加到主屏幕」仍然可用（`apple-mobile-web-app-capable` 已在 index.html 里）。

### 每张图实际是怎么生成的

`tools/.cache/provenance.json` 记录了每张图用的是图生图（带参考图）还是文生图（回退）。
本版 25 张里 **19 张图生图 + 6 张文生图**，原因是图生图通道会整段不可用。
如果想让 25 张全部走图生图，在通道空闲时执行：

```powershell
python tools/agnes_generate.py --mode img2img --force
```
