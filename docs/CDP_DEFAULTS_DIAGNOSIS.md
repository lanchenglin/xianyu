# CDP no_defaults 分页差异诊断（2026-10-16）

## 状态与结论边界

父助手报告：3bb8734 已部署但 API 仍一页/time_limit。同已登录 Chromium 的 /personal，自建任务页 no_defaults=True 在加载后 3 秒 body/root height=1241、20 卡，inner=913×931、clientHeight=916，反复真实到底仍 1 响应/20 条；前后设置 viewport=1280×720 无改善。普通连接同页 height=3729、相同 inner 尺寸，滚动 2 响应/40 条。这是父助手观测，本轮未连接真实服务复核。

**更新：父助手已完成真实单变量任务页实验，并批准最小 task-target focus 修复；工作台分页 API 仍待验收。** 保留 no_defaults=True、3bb8734 root geometry、UID 前后校验、不注入 cookie、不关闭借用 context/browser/原窗。500 轮/60 分钟为调查上限，不以重复无信息实验凑轮数。

### 真实控制实验与本次修复

本轮读取父助手提供的 `/home/lan/.hermes/cache/scratch/xianyu-layout-probe.json`（仅几何/CSS/类型汇总），没有连接真实浏览器。父助手说明同一个 no_defaults=True `/personal` 任务页：

| 阶段 | 等待 | root/body height | hidden / hasFocus | 图片 count/decoded |
|---|---|---|---|---|
| baseline | 3 秒 | 1241 | false / true | 93 / 93 |
| baseline | 再 4 秒 | 1241 | false / true | 93 / 93 |
| bring_to_front | 2500ms | 1241 | false / true | 93 / 93 |
| 仅任务 target focus emulation=true | 3 秒 | 3729 | false / true | 93 / 93 |

各阶段媒体布尔值均 false，inner=913×931、root.clientHeight=916 不变。列表父容器 maxHeight 从 480px 变为 3060px、rect.height 从 490 变为 2922；卡片仍20张，单卡尺寸未变。资源 timing img 数量36→49，不能声称所有资源状态完全不变。**这是实际 CSS/几何变化，不是仅 document.hidden 改变，也不证明具体站点 JS 内部机制或应用分页成功。** 等待时长来自父助手描述，JSON 本身没有时间戳。

实现：`task_page(..., focus_emulation=False)` 默认关闭；`goofish_page` 透传，只有 orders/inventory collector 显式打开。前置 UID 校验后新建 page，在 yield/navigation 前只用 `context.new_cdp_session(page)` 发送 `Emulation.setFocusEmulationEnabled(enabled=True)`，session 保持到任务结束，finally detach 并关闭自己的 page。attach/send/任务失败或取消亦清理；成功返回前再次 UID 校验。无 Browser 级 emulation 命令、无原页激活/导航、无媒体/viewport/context 默认修改、无普通连接回退；search/messages 默认不变。既有滚动节流、loading、root 几何及预算不改。

## Playwright 1.64.0 静态证据

本机 `.venv/lib/python3.12/site-packages/playwright/driver/package/lib/coreBundle.js`（打包文件行号仅对应此版本）：

| 位置 | 普通 connect_over_cdp | no_defaults=True（借用 default context） |
|---|---|---|
| 44547–44550 | noDefaultViewport=true | 同样 true；另设 acceptDownloads=internal-browser-default |
| 39994–40003 | Browser.setDownloadBehavior | 不覆盖下载设置 |
| 39020–39024 | 主 frame Emulation.setFocusEmulationEnabled(true) | 跳过 |
| 39045–39046、39432–39445 | Emulation.setEmulatedMedia | 跳过 |
| 23883–23890 | 默认 light/no-preference/none/no-preference | 不发上面的默认媒体覆盖 |

`_updateViewport` 两侧都会调用，但 39378–39380 在无 emulatedSize 时返回。显式 set_viewport_size 走另一路，与 focus/media 分支独立。39034 仅 options.javaScriptEnabled===false 时禁 JS，no_defaults 不设置此项；service worker 的 allow/block 也不是 no_defaults 分支（39704）。39017 的 bypass SW 是 storage-state 专用页条件，不是普通任务页。字体设置依赖 headful，不依赖 no_defaults。两侧仍启用 Runtime/Network/Page 和自动 attach；no_defaults 不是“零 CDP 干预”。

因此，不能将该选项解释为 viewport 开关、禁 JS、禁 SW 或禁 CSS。也不能直接删掉它：普通连接会对**已有页面**应用默认覆盖，不只影响新建任务页。

## 离线可证明的机制（不等于站点根因）

`tests/test_page_state_probe.py::test_cdp_focus_characterization`：每个参数启动全新 headless Chromium、随机 loopback CDP 端口、临时 profile，不读取用户 profile，不连 9235/8099。用显式监听 visibilitychange 的虚构页面，再将原 fixture 页置前：

- no_defaults=True：任务页 hidden=true，虚构布局高度 1241。
- 普通连接：任务页 hidden=false，高度 3729。
- 只给任务页 CDP session 设置 focus emulation=true：hidden=false、高度 3729，innerWidth 不变。

高度由 fixture 故意构造，**并非复刻闲鱼实现**。这只证明 focus/visibility 能在相同 viewport 下造成布局差异，且默认连接确实影响它。真实站点是否用可见性门控渲染、懒加载或测量仍待证。headless 结果也不能直接代表父助手的有头 Chromium。初轮没有据此实现 focus 修复；后续实现依据上方父助手真实控制实验及明确授权，未部署。

## 父助手采集脚本（只观察已拥有任务页）

`scripts/page_state_probe.js` 是 `page.evaluate` 函数，不负责 CDP 连接、不导航、不滚动、不改样式、不注入事件、不读 cookie/storage。仅返回资源汇总、可见性、媒体布尔值、几何及有限 computed CSS；不输出 DOM 文本、outerHTML、属性、类名、URL、请求头/正文、响应正文、JS 源码或错误消息。跨域 CSSOM 访问失败记 ruleCount=null，不绕过。

父助手在已有身份校验和 task_page 生命周期内调用（不要另起普通默认连接污染对照）：

```python
from pathlib import Path
import json

probe = Path('scripts/page_state_probe.js').read_text()
# 由父助手填入已知稳定且非秘密的列表、卡片、加载 sentinel 选择器；最多 8 个。
selectors = [LIST_SELECTOR, CARD_SELECTOR, SENTINEL_SELECTOR]
snapshot = await page.evaluate(probe, selectors)
print(json.dumps(snapshot, ensure_ascii=False))
```

每组必须用同一个版本、同一身份、同一入口、独立任务页，在 navigation 前挂监听；原窗不导航、不关闭。分别在 DOMContentLoaded 后、+3 秒、每次真实滚动前后、+10 秒取样。先采集 no_defaults 对照。普通连接可能改写已存在 target，**不得与 no_defaults 实验同时运行**；不要把“普通连接之后的新结果”当未受污染的基线。若父助手继续普通连接对照，应记录此前连接顺序及是否重建 target，并在明确授权的环境进行。

### 必需差异清单

1. `hidden/visibilityState/hasFocus` 的时间序列；任务页是否前台，原窗是否被另一连接激活，窗口最小化/遮挡状态（人工只记布尔值）。不要仅记录 innerWidth。
2. viewport/visualViewport/devicePixelRatio；root 的 scrollTop、scrollHeight、clientHeight、横向宽度；body 和卡片前 3 项的 rect、CSS，首卡到 body 最多 6 层父容器。groups 下标与本地选择器对应，不输出选择器。
3. 卡片 count、display/gridTemplateColumns/flexWrap、宽高、overflow、contentVisibility、字体/行高、间距；确认 20 卡是否图片未解码/卡片高度不同/列数不同，而非假定根容器错误。
4. stylesheets 数量、disabled/external/ruleCount/ownerConnected；scriptCount；图片 count/complete/decoded；fontsLoaded。资源聚合按 css/script/img/fetch 等比较数量/大小/耗时。跨域 transferSize=0 不等于加载失败，complete=true 也不等于图片成功，应结合 decoded。
5. media 的 print、色系、reduced-motion、forced-colors、contrast；serviceWorkerControlled。仅 controller 布尔值不能证明有无 SW 截获。
6. navigation 前注册以下**聚合**监听，以 resource_type + HTTP 状态、failure 布尔值、from_service_worker 布尔值为键统计；不打印 event、URL、headers、post_data、failure 原文。API 响应页数/条数仍沿用已有 allowlist/脱敏逻辑，不能扩成任意响应采集。

```python
from collections import Counter
network = Counter()

def response_seen(response):
    network[(response.request.resource_type, response.status,
             response.from_service_worker)] += 1

def failed(request):
    network[(request.resource_type, 'failed', False)] += 1

page.on('response', response_seen)
page.on('requestfailed', failed)
try:
    # 这里由现有父助手流程导航自己的任务页、等待并取 snapshot。
    # 输出列表避免 tuple 作为 JSON key；不输出请求或响应对象。
    summary = [{'type': k[0], 'status': k[1], 'sw': k[2], 'count': n}
               for k, n in network.items()]
finally:
    page.remove_listener('response', response_seen)
    page.remove_listener('requestfailed', failed)
```

若要逐资源比较，用父助手进程内的临时映射把完整 URL 映射为 `resource_1` 等不透明编号，只输出编号/类型/状态/大小，不输出原 URL 或稳定 hash。相同编号映射只在一次配对实验内存存在，不持久化。不要采集 HAR/trace/截图/console 原文，它们可能带秘密。

### 下一步判断门槛

- 可见性不同且资源/卡片样式随可见性恢复：候选是 visibility/focus 门控；再由父助手明确授权在**自建任务页**做单变量 focus emulation 或激活实验，比较同一页前后、第二页请求、卡片数、原窗状态。这属于干预实验，不是上面的只读 probe，本轮没有执行真实干预。
- 可见性相同但媒体不同：分别测媒体特征，不能同时改 focus、viewport 和 media。
- 状态均相同但 CSS/图片资源不同：继续查资源失败、缓存、SW、跨域 CSS 与解码时序；不做滚动补丁。
- 只有首次连接次序决定结果：先消除多连接/target 初始化污染，不将成功归因到最后一个设置。

上述为初轮诊断建议。后续真实单变量对照已证明几何恢复，用户据此批准最小 task-target 修复及隔离回归，不再以“必须先恢复分页”为实现阻塞；**真实应用分页仍需父助手单独验收**。离线 visibility fixture 仍不能代替真实证据。

## 复现

```bash
env -u PYTHONPATH TMPDIR="$PWD/scratch" \
  XY_TEST_CHROMIUM=/home/lan/.hermes/cache/scratch/xianyu-completion-evidence/browsers/chromium-1248/chrome-linux64/chrome \
  .venv/bin/python -m pytest tests/test_page_state_probe.py -q
```

probe 先红（缺失脚本），实现后 3 项绿；fixture 不注入 cookie，测试结束仅关闭自身 page、断开 Playwright，最后终止自己启动的 Chromium。未修改 site-packages、未部署、未 push，已有 scratch 内容保留。
