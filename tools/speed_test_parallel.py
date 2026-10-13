"""模拟真实浏览器的并行加载，给出用户实际等待时间。"""

import concurrent.futures as cf
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.110.25:4173"

SHELL = ["/", "/manifest.webmanifest", "/sw.js"]
CARDS = [f"/images/stories/story-0{s}/page-01.webp" for s in range(1, 6)]
# 从构建产物里找实际的 JS/CSS/JSON 文件名
import re, pathlib

DIST = pathlib.Path(__file__).resolve().parents[1] / "dist"
assets = [f"/assets/{p.name}" for p in DIST.glob("assets/*")]
PAGE = [f"/images/stories/story-03/page-{p:02d}.webp" for p in range(1, 6)]


def fetch(path):
    req = urllib.request.Request(BASE + path, headers={"Cache-Control": "no-cache"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=20) as r:
        r.read()
    return time.perf_counter() - t0


def parallel(paths, workers=6):
    """浏览器同源并发上限约 6 条连接。"""
    t0 = time.perf_counter()
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(fetch, paths))
    return (time.perf_counter() - t0) * 1000


print(f"目标: {BASE}")
print("（模拟浏览器 6 条并发连接，统计用户实际等待的墙钟时间）\n")

scenarios = [
    ("首页首次打开（不含插画）", SHELL + assets),
    ("首页 5 张卡片图同时加载", CARDS),
    ("打开一个故事的第 1 页", SHELL + assets + [CARDS[2]]),
    ("翻到第 4 页（单张插画）", [PAGE[3]]),
]

for name, paths in scenarios:
    times = [parallel(paths) for _ in range(3)]
    best = min(times)
    print(f"  {name:<26} {len(paths):>2} 个请求   最快 {best:>6.1f} ms   平均 {sum(times)/3:>6.1f} ms")

# 全量 25 张插画并行
allimg = [f"/images/stories/story-0{s}/page-{p:02d}.webp" for s in range(1, 6) for p in range(1, 6)]
t = min(parallel(allimg) for _ in range(3))
print(f"  {'一次性下载全部 25 张':<24} {len(allimg):>2} 个请求   最快 {t:>6.1f} ms")
