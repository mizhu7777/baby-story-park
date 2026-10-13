"""实测局域网访问速度：逐个资源计时 + 首屏/全量汇总。"""

import statistics
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://192.168.110.25:4173"
ROUNDS = 3

# 首屏真正要等的东西
SHELL = ["/", "/assets/index-DIHxPVdR.js", "/assets/index-CN76Pv1X.css", "/assets/stories-CANlO36-.json"]
CARDS = [f"/images/stories/story-0{s}/page-01.webp" for s in range(1, 6)]
ALL_IMAGES = [f"/images/stories/story-0{s}/page-{p:02d}.webp" for s in range(1, 6) for p in range(1, 6)]


def timed(url, use_cache):
    """use_cache=False 模拟首次访问（绕过本机 HTTP 缓存）。"""
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache" if not use_cache else "max-age=0"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=20) as r:
        data = r.read()
    return (time.perf_counter() - t0) * 1000, len(data), r.status


def run(label, paths, warm):
    times, size = [], 0
    for p in paths:
        ms, n, st = timed(BASE + p, use_cache=not warm)
        if st != 200:
            print(f"  !! {p} -> HTTP {st}")
        times.append(ms)
        size += n
    return {
        "label": label,
        "files": len(paths),
        "kb": size / 1024,
        "total_ms": sum(times),
        "max_ms": max(times),
        "avg_ms": statistics.mean(times),
        "p95_ms": sorted(times)[int(len(times) * 0.95) - 1],
    }


def show(r):
    print(
        f"  {r['label']:<22} {r['files']:>3} 个  "
        f"{r['kb']:>8.1f} KB  总 {r['total_ms']:>7.1f} ms  "
        f"平均 {r['avg_ms']:>6.1f} ms  最慢 {r['max_ms']:>6.1f} ms"
    )


print(f"目标: {BASE}\n")

for warm, name in ((False, "首次访问（无缓存）"), (True, "二次访问（有缓存）")):
    print(f"── {name} " + "─" * 46)
    show(run("首屏（HTML+JS+CSS+JSON）", SHELL, warm))
    show(run("首页 5 张卡片图", CARDS, warm))
    show(run("全部 25 张插画", ALL_IMAGES, warm))
    print()

print("── 单张插画（翻一页时加载）" + "─" * 36)
single = [timed(f"{BASE}/images/stories/story-03/page-{p:02d}.webp", use_cache=False) for p in range(1, 6)]
for (ms, n, _), p in zip(single, range(1, 6)):
    print(f"  story-03/page-{p:02d}       {ms:>6.1f} ms   {n/1024:>6.1f} KB")
print(f"  {'平均':<24} {statistics.mean(s for s, _, _ in single):>6.1f} ms")
