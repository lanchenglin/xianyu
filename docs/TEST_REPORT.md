# v0.1.0 开发验收记录

日期：2026-10-14。此文件只记录实际执行的检查，不把待部署步骤写成已验收。

以下“已执行”为首次 Linux 开发环境的历史记录；上传后的 GitHub CI 结果另列于下一节，不混为本地主人电脑验收。未完成功能与续开发步骤见 [开发交接清单](DEVELOPMENT_HANDOFF.md)。

## 2026-10-15 独立审查反馈修复（最新，仍待独立复审）

用户报告精确快照 da3e2ad 独立审查 FAIL，不可上线。问题一（数字 messageId）已于 433a1be 修复并保留原始 opaque ID 回归；该 ID/text 增量不因本地测试通过而视为独立审查通过。

问题二在 433a1be 仍存在：operations_cache 未保留 response_limit/page_redirected/cid_mismatch。新增明确白名单，同时将 HTTP 错误改为相同安全 code + 固定提示，禁止裸 raise 转出任意 Problem.message。未知 code 仍统一 collection_failed，不存储/返回异常原文。

参数化 3 类样本 × 5 类错误（含未知秘密字符串）共 15 项 RED→GREEN，断言 HTTP 失败、旧记录/密文不变、last_sync 准确安全码，以及 HTTP/缓存/同步记录无假 secret/电话/地址。另复跑 opaque ID 原样保留测试。

最终 Python 3.12：**344 passed, 1 warning, 67.05s**；Python 3.11：**344 passed, 1 warning, 67.35s**，启用独立 Chromium、包含 MCP stdio/UI/本地 WS，无跳过；双 pip check/ruff 通过。唯一警告为既有 Starlette/httpx 弃用。证据 safe-code-red/green、review-final311/312.log 在 `/home/lan/.hermes/cache/scratch/xianyu-messages-evidence`，TMPDIR 保持 scratch 根目录。无真实访问、部署或 push；本修复及 433a1be 均需父助手独立复审，未宣称可上线。

## 2026-10-15 编码与草稿增量（历史）

基线 da3e2ad。父助手新增脱敏证据只读读取，未连接真实平台。opaque ID RED：`1234567890123.AbC` 被纯数字拒绝→原样通过；路径/控制/超长拒绝。普通文本/peer RED→GREEN；未知/恶意编码保持 unavailable。选定样本草稿缺 sample_id/路由 RED→GREEN；MCP 缺工具 RED→GREEN；UI 正文不可见 RED→GREEN；失败采集旧缓存草稿 RED→409。未将既有保护首次即通过写成 RED。

- Python 3.12 **329 passed, 1 warning, 64.09s**；3.11 **329 passed, 1 warning, 65.41s**（含追加毫秒 13 位校验 RED/GREEN）。均启用独立 `/snap/bin/chromium`、无跳过；唯一既有 Starlette/httpx 弃用警告。
- 双环境 pip check/ruff、node check、diff check、完整 smoke_ui 通过。真实 MCP stdio 的本地草稿调用与无 actions 副作用通过；Agent UI 可读正文 textContent/XSS、按需生成、账号切换通过。
- 隔离 TLS WebSocket→真实 Chromium→bridge 子进程使用新 opaque ID 与 base64 普通文本 fixture，通过；不发送 IM 协议，真实平台未验收。
- v8 加密草稿表、错误密钥验证、备份恢复不重放回归通过。中途 3.12 全量 2 failed/320 passed：旧 v2 fixture 未删除新增表、UI 并发刷新导致草稿输出被覆盖；修复 fixture 表降级和等待按钮异步完成后双版本全绿。
- TMPDIR 始终 `/home/lan/.hermes/cache/scratch`；日志在其 `xianyu-messages-evidence` 子目录，不入库。无部署/push、无 8099/9235 或真实 .env/data/profile 读取。
- 仅 local_template 本地建议，不调用模型、不创建发送提案；CDP 写仍拒绝。自动监听/FAQ/分页/真实发送、首次聊天、发布改价上下架及 Hermes 实际接入未完成。详细契约见 MESSAGES。

## 2026-10-15 第三批：末条消息元数据样本（历史）

基线 b0e84fe；实现范围和证据需求见 [MESSAGES](MESSAGES.md)。本批只交付 partial_messages 元数据，不把正文未知伪装成可回复；无后台监听/自动回复，无部署/push，无真实账号访问。用户提供前批真实订单/商品 10/20 条与 CI 38744034233 五作业成功，本批未重新连接验证。

- TDD：parser 12 项缺函数 RED→GREEN；collector 6 项缺函数 RED→GREEN；HTTP/capabilities 缺路由/能力 RED→GREEN；CDP propose 201→409 RED/GREEN；真实 MCP stdio 缺两工具→GREEN；UI 缺按钮→GREEN；深度限制及 collector 安全错误码 RED→GREEN；v7 迁移断言 6→7。迁移/恢复额外验收首跑即通过，不冒称全部为新增 RED。
- 全量 Python 3.12：**294 passed, 1 warning, 62.45s**；3.11：**294 passed, 1 warning, 63.67s**，均启用 `XY_TEST_CHROMIUM=/snap/bin/chromium`，无跳过。双环境 pip check/ruff、node --check、git diff --check 通过。唯一警告为既有 Starlette/httpx 弃用。
- 完整 smoke_ui 通过；Agent UI 样本读取/切账号清空/无提案按钮、原 XSS/移动端回归通过。真实 MCP SDK stdio→临时 API 新工具与管理员令牌拒绝通过。
- 实际 Chromium 全新 profile + 随机 CDP + 本地 TLS WebSocket：provider→真实 bridge→Network.webSocketFrameReceived→元数据输出通过；本地 WS 接收列表为空（未发 IM 协议）。已有页/浏览器保留；原超时取消/UID 切换回归通过。fixture 首用 Playwright WS 拦截未产生真实 CDP 网络帧，改成本地 TLS server；Chromium LocalNetworkAccessChecks 拦截 localhost 映射，测试专用禁用该特性后通过，不修改生产参数。
- 中途全量曾因 UI 登录异步结束后覆盖导航导致双环境各 1 failed/293 passed；fixture 改为等待登录按钮恢复 enabled（而非默认可见 overview），后双版本全绿。保留失败日志，不把中途结果抹除。
- v6→v7 一致性备份、密文保留、错误密钥与 0600 权限；离线恢复包含消息缓存但旧任务不重放；多账号 HMAC、重复稳定 ID、失败不清库验证通过。
- 日志绝对目录 `/home/lan/.hermes/cache/scratch/xianyu-messages-evidence`，不入库。实际闲鱼消息、正文编码、收件人、真实模型与 Hermes connector 未验收。首次聊天、发布冻结、改价上下架、分页/后台消息/无人值守 FAQ 仍未完成。

## 2026-10-15 运营第二批：只读单页样本（历史）

基线 465f898，完成 orders/inventory 的受限 CDP 网络监听 → 最小字段 → v6 加密缓存 → API/UI/MCP。契约见 [OPERATIONS_SAMPLES](OPERATIONS_SAMPLES.md)。真实 bought/personal 的结构证据来自已授权父助手；开发测试仅虚构数据，不连接真实平台或 8099/9235，不读取真实 .env/data/profile。未 push/部署，Windows 暂停不变。

- TDD RED/GREEN：parser（17 项缺模块→通过）、listener（8 项缺模块→通过）、cache/API（缺路由/白名单→通过）、surfaces（真实 stdio 缺工具、Chromium 缺页面按钮→通过）、cursor（3 项类型错误未审计→通过）、audit（持久 has_more/reported_total 缺失→通过）。日志在 `/home/lan/.hermes/cache/scratch/xianyu-operations2-evidence/`，不入 Git。
- 缓存首次 GREEN 尝试发现重启测试错误地同时开启两实例，被既有锁正确拒绝；测试改为顺序关闭/重启，未放宽单实例保护。首次全回归 2 failed / 260 passed / 4 skipped：旧 v2 恢复 fixture 未移除新增表、旧 CDP capability 断言只允许 search；修正历史 fixture/契约，生产迁移不使用 IF NOT EXISTS 掩盖错误。
- 实际隔离 Chromium：新 profile、随机 CDP 端口、fixture 假 unb、所有页面请求拦截成本地虚构响应；真实 Network.responseReceived/loadingFinished/getResponseBody 链路通过。Provider→真实 bridge 子进程→CDP 正常输出及超时取消通过；self=false、前后 UID 变化拒绝，原页/浏览器存活，自建任务页关闭。这不是闲鱼真实账号验收。
- 真实 MCP SDK stdio + 随机端口 Uvicorn：新增四工具发现/调用、partial 标记；既有管理员令牌拒绝回归保留。临时 Chromium 新样本页同步、切账号清空、XSS textContent、移动端通过。完整 `scripts/smoke_ui.py` 同时通过原审批/草稿/通知/人工核对回归。
- 最终 Python **3.12.14：271 passed, 1 warning in 58.26s**；Python **3.11.16：271 passed, 1 warning in 58.64s**。两环境 pip check、ruff 全部通过；全量启用 XY_TEST_CHROMIUM，含固定上游契约，无跳过。唯一警告是既有 Starlette/httpx 弃用提示。node --check / git diff --check 通过。
- 单页始终 partial；订单字符串 nextPage 语义未知记录错误，不猜值或执行翻页。商品 false 也不等于全状态库存。空页/失败不清库、账号隔离、重启幂等、错误密钥、v5 迁移与权限测试通过。
- 未完成/未验收：实际平台采集与实际 Hermes connector、分页遍历和全状态集合、消息解析/编码/按需采集/增量监听。消息稳定 ID 结构已有证据，不能再否定其存在；本批没有用 stub 冒充 listener。首次联系、真实发布/改价/上下架和所有交易执行均未新增。

复现环境：`TMPDIR=/home/lan/.hermes/cache/scratch/xianyu-operations2-evidence PLAYWRIGHT_BROWSERS_PATH=/home/lan/projects/xianyu/.test-browsers PLAYWRIGHT_SKIP_BROWSER_GC=1 XY_TEST_CHROMIUM=/snap/bin/chromium`；分别使用 `.venv/bin/python` 和 `/home/lan/.hermes/cache/scratch/xianyu-venv311/bin/python` 执行 `-m pip check`、`-m ruff check .`、`-m pytest -q`。

## 2026-10-15 Linux / WSL 优先收尾（历史）

默认支持 Linux / WSL（Python 3.11/3.12），**Windows 原生支持暂停**。用户提供的 [CI run 38727928186](https://github.com/lanchenglin/xianyu/actions/runs/38727928186) 对应 `53400f82f1ce4f1b1322f184b4b15e2e2c949e97`，整体失败，不能记为全绿：

| 作业 | 结果 |
|---|---|
| tests：ubuntu-latest，Python 3.11 / 3.12 | 两项通过 |
| upstream-contract：Ubuntu，Python 3.11 / 3.12 | 两项通过 |
| browser-smoke：Ubuntu | 通过 |
| tests：windows-latest，Python 3.11 / 3.12 | 两项失败，未继续修复 |

独立分支 `work/windows-support-53400f8` 已由父助手创建并 push 保存上述快照；本轮本地分支及 origin 追踪引用均核对为该 SHA。本机无 `gh` 命令，本轮未重新获取 CI 日志，不推断 Windows 失败原因。此前 run 38708963492 / 38679746659 等失败及更早基线成功记录仍保留在下文。

当前 `feat/local-next` 仅将 CI tests 的 OS 矩阵改为 `ubuntu-latest`，保留 Python 3.11/3.12、双版本 upstream-contract、browser-smoke 和所有原检查步骤；跨平台源码及回归未删除或跳过。Windows 后续工作留在独立分支，**新的 Linux 全绿不代表 Windows 已修复或恢复支持**，也不代表真实平台验收。本轮不 push，新矩阵尚未远端运行。

本轮配置/文档验证：

- YAML 实际解析并与 HEAD 配置深比较：唯一变化为 tests OS 矩阵移除 windows-latest；Ubuntu Python 3.11/3.12 及其他 Linux 门槛、步骤保持不变。
- 本机 Python 3.12：`ruff check .`、`pip check`、`git diff --check` 通过；`TMPDIR="$PWD/scratch" PLAYWRIGHT_BROWSERS_PATH="$PWD/.test-browsers" PLAYWRIGHT_SKIP_BROWSER_GC=1 XY_TEST_CHROMIUM=/snap/bin/chromium .venv/bin/python -m pytest -q`：**232 passed, 1 warning in 41.38s**，唯一警告为既有 Starlette/httpx 弃用提示。
- 本轮未重跑 Python 3.11 或 UI smoke；`53400f8` 双版本 232 passed 及 UI smoke 属此前验证，不冒称本轮结果。没有访问真实平台、修改 .env/data/已有 profile、重启服务或修改 Hermes 配置；scratch 测试临时文件/日志不提交。

## 2026-10-15 运营增量第一批（历史）

起点 121f3c8；实现站内通知状态、管理员显式授权的外部固定摘要通知和 MCP stdio 真协议测试。schema v4/v5 增量迁移；备份恢复关闭外部通知并取消待发任务。完整需求尚未完成，矩阵与下一断点见 [OPERATIONS_NEXT](OPERATIONS_NEXT.md)。

- RED 证据：notices-red（4 个缺路由失败）、notices-ui-red（缺已读按钮）、external-red（缺模块/配置路由）、transport-red（缺 send）、worker-red（重启状态/worker 未接通）、disable-red、external-ui-red、restore-red、mcp-red（缺新工具；既有管理员令牌拒绝首次通过）、dns-red、deadline-red、detached-deadline-red、capabilities-red。
- GREEN 与集成：本批新增 23 项；真实本地 TLS 接收端完成 API 配置→持久通知→真实 HTTPS/证书/SNI/签名→已投递→不重复；仅网络边界将验证地址映射随机 loopback，生产无放宽开关。此集成首次通过，未冒称其单独有 RED。钉钉/真实外部 webhook 未发送、未验收。
- 首次完整回归 221 passed / 1 failed：旧 v2 备份夹具仍携带新增通知表；修夹具以真实重建旧结构，未放宽生产迁移。DNS/连接/响应上限、退避三次、配置取消、恢复关闭、Agent 拒绝配置、凭据隐藏均有测试；HTTP 2xx 不是人已读，超时重试可能重复通知。
- MCP 使用真实 SDK ClientSession + stdio 子进程 + 随机端口临时 Uvicorn，initialize/list_tools/call_tool、通知归档、固定目标参数边界、管理员令牌拒绝通过；不等于实际 Hermes connector 已安装联调。
- 最终 Linux Python 3.12：**231 passed, 1 warning in 41.73s**；Python 3.11：**231 passed, 1 warning in 43.32s**。双版本 pip check / ruff 均通过，固定 live 契约及隔离浏览器测试包含在全量中。
- 系统 Chromium 临时 profile UI smoke 通过，新增关闭状态通知配置（未启用）、密钥输入清空、已读/归档控件；原审批/草稿/移动端回归保持。node --check / git diff --check 通过。警告仍是既有 Starlette/httpx 弃用提示。
- 证据目录 `scratch/xianyu-operations-evidence/`，不入 Git。未读取真实 .env/data/profile、未连接 8099/9235、未执行平台操作/真实通知、未部署/push。Windows 新 CI、真实账号/钉钉/Hermes 均未验收。

### 通知传输自审修复

功能提交 `07fb1a2` 后发现 HTTPConnection 在 Connection: close 响应时可能解除 socket 引用；截止计时已保留传输 socket，但拒绝/超限响应还应显式关闭 HTTPResponse。`response-close-red.log` 实际断言失败（close 未调用），补 finally 关闭后完整双版本重跑：3.12 **232 passed, 1 warning in 42.82s**；3.11 **232 passed, 1 warning in 41.85s**。ruff / node --check / git diff --check 通过。证据 `review-final312.log` / `review-final311.log`。没有新增平台/外部联网验收。

## 2026-10-15 Windows 浏览器测试夹具修复（历史）

基线 `161968e` 已由 Hermes push。[CI run 38708963492](https://github.com/lanchenglin/xianyu/actions/runs/38708963492) 的 Windows Python 3.11/3.12 失败，其余 5 作业通过（用户提供的运行状态）。已核对本地 `scratch/xianyu-browser-ci/311.log`：3.11 为 2 failed、191 passed、3 skipped；两条失败如下，保留失败记录，不宣称原 CI 全绿。

1. 浏览器测试 runtime 只设置 HOME，Windows Path.home 使用 USERPROFILE，测试 profile 落到 runneradmin 目录。核对生产 provider：已经同时将 HOME/USERPROFILE 设置为账号独立 runtime，不存在同一遗漏。本次仅修测试夹具同时设置两者；增加 HOME/USERPROFILE 选择的参数化回归和精确 profile 父目录断言，并在 provider 测试中注入不同的假宿主 home，确认两个子进程变量都被覆盖。
2. Windows 上模拟 POSIX 的测试仅替换 os.name，仍使用宿主 signal，缺少 SIGKILL。生产 Windows 走 taskkill，不访问 SIGKILL。本次使用测试局部 signal 模拟：POSIX 提供独立 SIGKILL 标记并核对 killpg 的精确参数；NT 刻意没有 SIGKILL，验证 taskkill 且不调用 killpg。不修改全局 signal，不删除/跳过 Windows 测试。

RED/GREEN：在 Linux 临时目录模拟 USERPROFILE home 选择和缺少 SIGKILL，修复前实际得到 2 failed、2 passed，分别为错误 profile 父目录与 AttributeError；最小修复后目标测试通过。未访问真实 profile，失败复现中的所有路径也在临时目录内。

最终本地验证（均设置 TMPDIR、独立 Playwright 缓存和 XY_TEST_CHROMIUM=/snap/bin/chromium）：

- Python 3.12：**208 passed, 1 warning in 34.69s**；pip check / ruff 通过。
- Python 3.11：**208 passed, 1 warning in 35.67s**；pip check / ruff 通过。
- 包含固定上游契约、真实隔离 Chromium/about:blank、本地 HTML、随机端口 CDP 和正常 operation timeout 页清理；仅既有 Starlette 弃用警告。
- 本次仅修改测试与本文档，生产浏览器/取消/凭据行为不变。新 Windows CI 尚未运行，必须由 Hermes 验收后 push 验证，不以 Linux 模拟冒充 Windows 实测。
- 未读真实 .env/data/profile、未连接 9235、未访问或重启 8099。用户报告 Hermes 已启用绑定账号 CDP search 并真实成功、worker=false；本轮未独立重复该线上验证，保持线上不动。

## 2026-10-15 独立审查修复（历史）

核对 `19ffe7e` 后确认两条源码问题仍存在，实现修复提交 `4732162`：CDP provider 曾解密并写入导入 Cookie；operation timeout 曾直接强杀，绕过任务页 finally。

- TDD：Cookie 禁止解密、取消通知/有界等待、不把超时当成功、协程清理共 4 项先 RED 后 GREEN；固定上游 Session 回读保护另行 RED/GREEN。
- 真实 Chromium 超时反证：在独立随机端口/假 uid fixture 中临时移除 cancellation_scope，5 秒 operation timeout 后页数为 2（预期 1），测试确实失败；恢复后通过。测试走真实 provider、bridge.main、适配与 Playwright，只将平台业务替换成本地 HTML + 等待，未访问闲鱼。超时后任务页消失，原页标题、浏览器进程和 Cookie 保留。没有连接 9235。
- Linux/Windows 强杀兜底分支有模拟测试：先等 8 秒协作清理，再 SIGKILL 进程组 / taskkill，回收最多 5 秒；超时始终 timeout/uncertain，不重放。Windows 未本机实测，不宣称实测。
- 项目 `.venv` Python 3.12：**207 passed, 1 warning in 32.46s**；独立 Python 3.11：**207 passed, 1 warning in 33.95s**。两者 pip check、ruff 均通过，含 12 项固定上游契约及真实隔离浏览器测试。此前其他审查环境缺包不代表本项目 venv 缺包。
- 隔离演示 UI smoke、node --check、git diff --check 通过。仅既有 Starlette 弃用警告。
- 未读真实 .env/data/profile、不重启现有服务、不连接真实 CDP、不 push。强杀/断线/事件循环阻塞仍不能保证关闭自建页，兜底边界见 [BROWSER.md](BROWSER.md)。未扩展 CDP 功能，仍仅 search。

## 2026-10-15 浏览器适配增量（历史）

基线 HEAD `1fc1a7d`，实现提交 `07c930b`，分支 `feat/local-next`。未读取实际 .env/data/profile，未连接现有 8099 或 9235，未重启服务。仅源码、假数据临时目录和随机端口独立进程。未 push/merge。

- 分组 RED/GREEN：发现 6 项、CDP 初始 22 项、页面适配初始 9 项、配置/provider/doctor 初始 7 项均先观察缺功能失败再实现；后续 WebSocket 重定向、可操作错误提示、no_defaults 均记录 RED 后 GREEN。实测生命周期与契约增补是集成验收，不冒称每条均先 RED。
- 最终 Python 3.12：199 passed, 1 warning in 29.21s；Python 3.11：199 passed, 1 warning in 29.52s。两者均启用 `XY_TEST_CHROMIUM=/snap/bin/chromium`，各 pip check / ruff 通过；包含 11 项固定上游契约及 2 项系统 Chromium 隔离实测。固定 commit 不变、未改 site-packages。
- doctor 在显式干净环境中实际输出 discovered=[chromium]、selected=chromium、mode=isolated、reason=null、connection_checked=false；没有发现 Chrome，不声称 Chrome 实测。
- 系统 Chromium 真实隔离测试：全新临时 HOME/profile，headless about:blank/本地 HTML；随机 CDP 端口，假 uid=12345；任务页正常/异常退出后关闭，Cookie 未被适配替换，原页标题/数量及浏览器进程保持，两次 Playwright 断开后再次连接确认存活。snap HOME 隔离在本机 scratch 路径实际成功。
- 演示 UI smoke 通过：登录、账号、搜索、监控、消息草稿/审批、人工核对、证据 XSS 与 Agent 隔离、图片上传、演示发布、移动端、退出。服务与数据库均临时，未使用现有服务。
- node --check、git diff --check 通过。测试有 1 条既有 Starlette httpx 弃用警告。
- **未实测 Google Chrome、Windows GUI、WSLg 用户窗口、真实闲鱼、真实登录 CDP、真实客户端与新远端 CI**。Windows 安装路径和 Chrome 选择仅模拟单测。CDP 实现只支持 search，item/消息/所有写操作明确拒绝。

复现（Python 3.11 用独立 venv 路径替换）：

```bash
export TMPDIR=/home/lan/.hermes/cache/scratch
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.test-browsers"
export PLAYWRIGHT_SKIP_BROWSER_GC=1
export XY_TEST_CHROMIUM=/snap/bin/chromium
.venv/bin/python -m pip check
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
.venv/bin/python scripts/smoke_ui.py
node --check xianyu_workbench/static/app.js
```

路径为本次测试环境示例，不是生产默认。设计、配置与剩余限制见 [BROWSER.md](BROWSER.md)，由 Hermes 独立审查后负责真实只读验证。

## 已执行

开发测试环境：Linux，独立 Python 3.12.14 虚拟环境。真实闲鱼登录态未提供，测试没有登录闲鱼，没有实际发送消息、发布商品、删除商品或进行交易。

| 检查 | 结果 |
|---|---|
| `ruff check .` | 通过 |
| Python 模块编译检查 | 通过 |
| `pytest -q`（含固定上游依赖） | **69 passed** |
| 前端 JavaScript `node --check` | 通过 |
| 固定上游 Git 提交核验 | c2d5a02ad83b18863514389cedf7afbd993b683d |

69 项测试由 59 项工作台测试与 10 项上游契约测试组成。覆盖：

- 未认证访问、管理员/Agent 权限分离；Agent 不能审批、导入账号或读取模型配置。
- 幂等、内容摘要、重复领取、并发领取、审批过期、拒绝、崩溃恢复。
- 演示消息和发布完整流程；真实执行默认关闭；演示结果不含真实商品链接。
- 超时不重发、暂停后不重放旧任务、收件人与会话核验。
- 商品删除确认文字与归属校验；付款、退款、下单、确认收货等操作不存在。
- 图片类型、任意本地路径拒绝、跨账号素材拒绝、素材修改后停止执行。
- 登录态加密、禁止跨账号覆盖、请求/结果不回显凭据；模型密钥加密与不回读。
- 搜索过滤、无效价格处理、去重、监控最低间隔和通知去重。
- MCP 工具发现和危险工具缺席；不是某款 Hermes Desktop 的实际接入测试。
- 上游函数签名、禁用认证重试的参数、固定提交与 Decimal 金额分单位计算。

测试过程中发现：直接导入上游会修改全局 `subprocess.Popen`，导致 MCP SDK 类型声明异常。工作台实际连接原本就采用独立子进程；契约测试也已改为子进程运行，之后完整测试通过。禁止未来把上游业务模块导入 FastAPI/MCP 主进程。

当前依赖测试过程中出现 1 条 Starlette 关于 httpx TestClient 的弃用警告，不是测试失败；后续可按依赖更新统一处理。

## 上传后 GitHub CI 核对（2026-10-14）

代码基线：`64556d84c7eed63222dd1352daff69293b8b98c0`。实查 [CI #1 / run 38535793804](https://github.com/lanchenglin/xianyu/actions/runs/38535793804)，总结果为 **failure**，不是全绿。分作业如下：

| 作业 | 结果 |
|---|---|
| tests (ubuntu-latest, 3.12) | 安装、ruff 与 pytest 通过 |
| tests (windows-latest, 3.12) | 安装、ruff 与 pytest 通过 |
| upstream-contract（Ubuntu / Python 3.12） | 通过；不是登录闲鱼的业务测试 |
| browser-smoke（Ubuntu / Python 3.12） | 演示页面交互通过；补上本地浏览器下载失败后未执行的这部分 CI 验证 |
| tests (ubuntu-latest, 3.11) | 安装 requirements-dev.lock 失败；后续测试跳过 |
| tests (windows-latest, 3.11) | 安装 requirements-dev.lock 失败；后续测试跳过 |

已读取 [Windows 3.11 作业日志](https://github.com/lanchenglin/xianyu/actions/runs/38535793804/job/115758224434)：`pyee==14.0.0` 需要 Python >=3.12，当前开发锁文件无条件固定该版本。运行锁文件不包含 pyee；不能直接据此推断所有 3.11 基础演示安装失败。完整开发/live 环境先使用 3.12，修复依赖和重跑兼容矩阵列为 [交接清单 P0-ENV](DEVELOPMENT_HANDOFF.md)。本次仅更新文档，不改变源码、锁文件或 CI 配置。

基础测试矩阵不安装 live 可选依赖；其成功不能代替上游契约作业，更不能代替真实平台操作。Windows CI 使用托管 Windows Server 环境，不是主人 Windows 桌面的 Chrome/登录态环境。这里的记录绑定上述历史提交，不表示以后所有提交或文档提交后的 CI 也通过。

## 首次验收状态与仍需本地确认的项目（2026-10-14 历史）

| 项目 | 当前状态 |
|---|---|
| Playwright 页面交互烟雾测试 | 首次本地下载超时未执行；上传后 Ubuntu CI 已通过演示页面测试，主人本地环境仍需验证 |
| Windows 3.11/3.12 | Windows CI 3.12 基础测试通过；3.11 开发依赖安装失败；主人电脑真实部署未验收 |
| Docker 镜像构建与运行 | 配置已提供，未在本次环境构建验收 |
| Hermes / Claude / Codex 客户端联调 | 通用 MCP 配置已提供，未在你的实际客户端运行 |
| 真实商品搜索和消息 | 未提供账号登录态，未测试 |
| 真实发布、删除、送达状态 | 未执行；必须人工审批后逐条验收 |
| 模型服务实际联网生成 | 未提供 API 配置；仅完成配置/错误边界测试 |

## 本次文档交接检查（2026-10-14）

本次只修改 README、AGENTS 和 docs 下的 Markdown，源码、依赖锁、CI 配置与部署配置未改动。

| 检查 | 结果 |
|---|---|
| 6 份变更文档的 UTF-8、代码围栏、64 个本地文档链接 | 通过 |
| `git diff --check` | 通过 |
| Linux / Python 3.12.14，当前工作副本 `ruff check --no-cache .` | 通过 |
| 当前工作副本完整 `pytest -q -p no:cacheprovider` | 69 passed，1 条已有 TestClient 弃用警告 |

此轮没有重新运行真实平台操作或本地浏览器页面测试，也没有修复/重新验收 Python 3.11 依赖。CI 分环境结论仍以绑定具体提交的记录为准。

## P0-ENV 本轮本地修复验收（2026-10-14）

原始 HEAD `2ea8d3b`，分支 `feat/local-next`，WSL/Linux。原始 3.12 基线：`59 passed, 1 skipped, 1 warning`；跳过的是未安装 live 的契约模块。3.11 原锁真实安装退出 1：`No matching distribution found for pyee==14.0.0`。

修复：Playwright 1.64 条件依赖，由明确 3.11 下限的 uv universal 解析生成；3.11 为 pyee 13.0.1，3.12 为 14.0.0。运行锁同步生成（包版本未变）。固定上游提交未变。

实际命令：

```bash
uv pip compile pyproject.toml --extra mcp --extra dev --universal --python-version 3.11 --output-file requirements-dev.lock
uv pip compile pyproject.toml --extra mcp --universal --python-version 3.11 --output-file requirements.lock
# 各独立环境中执行
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
python -m pip check
ruff check .
pytest -q
python -m pip install -e '.[live]'
python -m pip check
pytest -q
```

| 本轮环境 | 实际结果 |
|---|---|
| Python 3.12.14 `.venv` | pip check: No broken requirements found；ruff: All checks passed；含 live：69 passed, 1 warning in 9.48s |
| Python 3.11.16 scratch 独立环境 | pip check/ruff 通过；基础 59 passed, 1 skipped；含 live：69 passed, 1 warning in 9.71s |
| Windows | 未执行新 CI，不声称修复后 Windows 已通过 |

警告为已有 Starlette TestClient 弃用警告。安装 RED/GREEN 日志保存在 `/home/lan/.hermes/cache/scratch/xianyu-next-evidence/`。没有登录或请求闲鱼；契约仅子进程导入与函数检查。

## P2-04 必要迁移基础验收

本轮增加 5 项迁移测试和 1 项错误密钥测试。版本升级、未来版本、WAL 备份、迁移锁、错误密钥各自先运行单个失败测试，再最小实现通过；失败回滚为已实现事务的附加回归，首次即通过，不伪称 RED。日志为 scratch 证据目录中 `migration-*`、`future-*`、`backup-*`、`wrong-key-*`。

`TMPDIR=/home/lan/.hermes/cache/scratch .venv/bin/pytest -q`：**75 passed, 1 warning in 8.97s**。已有 TestClient 警告。完整回归包括领取并发、超时不重试、重启不重放、错误收件人和交易/未知操作拒绝。发现旧初始化发生于服务锁之前，新增 RED 测试后将迁移置于同一个实例锁下。

范围：无恢复 CLI、无自动备份/保留策略；未做真实数据恢复或账号验证。

## P1-02 人工核对与最终回归（2026-10-14）

本节是本轮最终结果；上面的 69 / 75 项及历史 CI 记录为各阶段真实结果，不覆盖、不冒充当前数量。交付分支 `feat/local-next`，起点 `2ea8d3b`；依赖修复提交 `80afd54`，迁移基础提交 `8ab9533`；第三项源码/测试/文档在本节同一提交中（`feat: add admin-only manual reconciliation without replay`）。

### 实际完成与测试范围

- 管理员核对 API 与中文 UI；原操作/账号绑定，仅 `unconfirmed/submitted/blocked` 可核对；原执行状态、结果、错误原样保留。
- 每操作一次不可覆盖记录；同键同内容幂等，修改内容、换键覆盖或跨操作复用键 409；并发相同请求仅落库/审计一次，不同请求仅一方成功。
- 核对与审计同事务；证据正文加密，审计不含正文；Agent 不可核对或审批，仅能读取核对结论/时间等概要，不能读证据。MCP 无新增核对/审批工具。
- schema v2 独立核对表；旧库和 v1 无损升级，备份含 WAL，失败回滚、备份失败停止升级、未来版本拒绝、单实例锁及错误密钥保护。
- 自审发现 SQLite connection context manager 不负责 close；先跑 `migration-close-red.log` 确认失败，再用 `closing` 显式关闭 probe/source/target，`migration-close-green.log`：`1 passed in 0.23s`。这只是本地连接生命周期验证，不是 Windows 实测。
- 完整回归仍覆盖 Agent 不可审批、跨账号拒绝、幂等冲突、并发领取/核对、超时/重启不重放、错误收件人不发送及未知/交易动作拒绝。

### 最终实际输出

| 环境 / 检查 | 结果 |
|---|---|
| WSL/Linux Python 3.12.14：pip check | `No broken requirements found.` |
| Python 3.12.14：ruff check . | `All checks passed!` |
| Python 3.12.14：pytest -q | **107 passed, 1 warning in 12.94s** |
| WSL/Linux Python 3.11.16：pip check | `No broken requirements found.` |
| Python 3.11.16：ruff check . | `All checks passed!` |
| Python 3.11.16：pytest -q | **107 passed, 1 warning in 13.40s** |
| `node --check xianyu_workbench/static/app.js` | 退出 0 |
| `git diff --check` | 退出 0 |
| 系统 Chromium 155.0.8059.39 + Playwright 1.64 | 完整演示 UI 冒烟通过，独立临时 profile |

两个 Python 环境均已安装固定 live `c2d5a02ad83b18863514389cedf7afbd993b683d`，107 项包含 10 项子进程上游契约，没有跳过。唯一警告是已有 Starlette/httpx TestClient 弃用警告。

实际最终命令（在仓库目录）：

```bash
export TMPDIR=/home/lan/.hermes/cache/scratch
.venv/bin/python -m pip check
.venv/bin/ruff check .
.venv/bin/pytest -q
"$TMPDIR/xianyu-venv311/bin/python" -m pip check
"$TMPDIR/xianyu-venv311/bin/ruff" check .
"$TMPDIR/xianyu-venv311/bin/pytest" -q
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.test-browsers"
export PLAYWRIGHT_SKIP_BROWSER_GC=1
export XY_TEST_CHROMIUM=/snap/bin/chromium
export XY_TEST_SCREENSHOT="$TMPDIR/xianyu-next-evidence/ui-agent-mobile.png"
.venv/bin/python scripts/smoke_ui.py
node --check xianyu_workbench/static/app.js
git diff --check
```

UI 实际输出：

```text
UI smoke passed: login, account, search, monitor, chat, approvals, manual reconciliation, evidence XSS safety, agent isolation, image upload, publish, mobile, logout
```

UI 不确定状态由脚本仅在临时演示数据库注入；没有开启 live，没有请求闲鱼。验证原执行结果未变、证据中的 HTML 作为文字展示、移动端不横向溢出、Agent 无证据/核对/审批按钮。系统 Chromium 由 Playwright 创建全新临时 profile，未读取主人 profile。

### RED/GREEN 证据与环境限制

证据目录：`/home/lan/.hermes/cache/scratch/xianyu-next-evidence/`（不提交 Git）。包括 `reconcile-*-red.log`、`reconcile-red.log`、`reconcile-green.log`、`capabilities-red.log`、`migration-close-{red,green}.log`、最终 `final-py312.log` / `final-py311.log` / `ui-final.log` 和 `ui-agent-mobile.png`。单测试 GREEN 曾实际运行；并发/原子回滚等附加回归首次通过，不伪称每个附加测试均有 RED。

官方 Playwright 浏览器包下载缓慢，已停止未完成的安装；直接下载官方包 240 秒超时，退出 28。首次 `ui-red.log` 因缺少浏览器失败，属于环境失败，不算功能 RED。改用系统 Chromium 后 `ui-feature-red.log` 实际因缺少“记录人工核对”按钮失败；实现 UI 后冒烟通过。未删除或清理任何共享浏览器缓存。

**代码完成与真实验收必须分开：** 本轮 P0-ENV 本地兼容修复、P2-04 必要迁移基础、P1-02 人工核对闭环代码与本地自动测试完成。修改后 Windows CI 尚未运行；真实账号、平台送达/已读、Docker、实际 MCP 客户端均未新增验收。无恢复 CLI、自动定时备份或保留策略；无可靠自动平台回执。其余首次联系卖家、全量库存、改价、普通上下架、实时客服、发布完整冻结、订单、外部通知不在本轮实现范围。没有真实发送/发布/删除/交易，没有部署、没有 push。

## 真实账号上线前步骤

由主人先在 Linux / WSL 运行演示，确认界面（Windows 原生支持已暂停）；安装系统 Chrome / Node 与 live 依赖；导入本人登录态；启用真实模式后仅验证一次搜索和一次详情；再验证既有会话；最后审批单条低风险咨询，亲自在闲鱼核实。

发布需真实图片、准确价格与描述，审批后核验商品 ID 和页面。删除不适合作为冒烟测试，避免拿重要商品验证。遇到登录/安全验证/不确定状态立即停止，由主人处理。未支持的改价、重新上架、首次会话或订单功能不能靠假返回代替实现。

## 2026-10-15 续开发状态更新

基线 `4d2aadc` 的 [CI run 38566392741](https://github.com/lanchenglin/xianyu/actions/runs/38566392741) 全部 7 作业成功：Ubuntu/Windows 3.11/3.12、双版本固定 live 契约及 UI。上文“新 CI 待验证”为此前历史状态，现已解决；不代表真实账号验收。本轮新增提交尚未 push，CI 待 Hermes 审查后验证。

固定上游五项核实见 [静态可行性报告](UPSTREAM_FEASIBILITY.md)。真实发布因不能冻结类目/地点暂时禁用（live_publish=false）；本地草稿、演示发布和审批申请保留。禁止用默认值变化后的上游发布代替完整审批。

A 安全保护 TDD：a-red.log 实际失败（此前进入真实处理），a-green.log 全量 108 passed / 1 既有弃用警告；证据目录 `/home/lan/.hermes/cache/scratch/xianyu-next2-evidence`。

### P2-04 本地离线恢复增量（2026-10-15）

已提供管理员离线 `backup` / `restore --offline` CLI：一致性数据库+素材、密钥/manifest/hash 校验、受限解包、活动实例拒绝、异常回滚和中断启动保护。恢复暂停账号/监控，pending/approved 失效、running 转不确定，旧任务不重放。无 HTTP/MCP 恢复能力，Agent 不可操作任意文件。详见 [备份说明](BACKUP.md)。此前“无恢复 CLI”为历史状态；定时/保留策略仍未实现。

B 阶段：15 项备份恢复测试通过；全量 123 passed / 1 既有弃用警告。实际临时数据备份→破坏副本→恢复、错误 key 拒绝、重新打开数据库并运行队列不重放、活动锁/路径穿越/符号链接/大小限制/哈希/未来 schema/回滚注入均覆盖。b1～b6-red.log 记录逐行为失败，b-green.log 为全量回归。

### P2-02 单条草稿管理（2026-10-15）

已实现单条原位编辑、revision 乐观并发保护和归档 UI；显式 v2→v3 迁移增加 revision=1 / archived=0，保留原内容。PUT `/api/drafts/{id}` 接受原 account_id、revision 和完整草稿字段；POST `/api/drafts/{id}/archive` 接受 account_id、revision。账号/旧版本/已归档冲突返回 409，不另建副本；归档非平台删除，修改不会改变已冻结审批。管理员和 Agent 均可操作安全本地草稿，无新增管理员权限或任意文件操作。未增加 MCP 编辑工具（HTTP/UI 可用），既有 MCP 保存工具保持新建语义。没有素材删除接口，所有引用图片保留。批量发布、素材回收、取消归档尚未实现。

C 阶段：全量 127 passed / 1 既有弃用警告；c1/c2-red.log 为编辑和归档缺失 RED，c-ui-red.log 实际浏览器因缺少归档按钮失败，c-ui-green.log 真实系统 Chromium 临时 profile 冒烟通过。覆盖跨账号/素材、旧 revision 并发、加密、审批原文冻结、归档非平台删除与图片保留；v2 旧草稿迁移保留测试通过。

### 安全自审增量

发现并以 RED/GREEN 修复：备份创建允许超过恢复上限的大包；中断后的恢复重试若安装失败会丢失此前启动阻断标记。现创建/恢复限制一致，失败重试保留原标记。review-limit-red.log / review-marker-red.log 实际失败，18 项备份恢复回归通过（含 v2 备份→v3 迁移与服务重新启动不重放）。review-ui.log 通过：额外验证另一窗口更新后的旧 revision 保存被拒绝且用户编辑文本保留。

## 2026-10-15 最终验证

| 检查 | 实际结果 |
|---|---|
| Python 3.12.14 pip check / ruff | 均通过 |
| Python 3.12.14 pytest -q | 131 passed, 1 warning in 17.13s |
| Python 3.11.16 pip check / ruff | 均通过 |
| Python 3.11.16 pytest -q | 131 passed, 1 warning in 17.75s |
| 双版本固定上游契约 | 各 10 项通过，亦包含于全量 |
| node --check / git diff --check | 通过 |
| Playwright 系统 Chromium，独立缓存+临时 profile | 通过；新增草稿编辑/旧 revision 拒绝/归档/冻结审批验证 |

证据目录 `/home/lan/.hermes/cache/scratch/xianyu-next2-evidence`，final-py312.log、final-py311.log、final-contract312.log、final-contract311.log、final-ui.log。使用 `PLAYWRIGHT_BROWSERS_PATH=$PWD/.test-browsers PLAYWRIGHT_SKIP_BROWSER_GC=1 XY_TEST_CHROMIUM=/snap/bin/chromium`，未下载新浏览器或读取已有 profile。警告为既有 Starlette TestClient/httpx 弃用提示。

实际完成 4 个本地功能/修复提交后继续安全审查与最终验证，没有停止在 A。没有真实登录/平台请求，没有启用 live，没有部署/推送/合并。真实账号未验收。基线已有 CI 成功不外推到新增提交；新增 CI 等 Hermes 审查推送。

最终另以 review-start-red.log 复现并修复“Service 已构造但 lifespan 尚未启动时恢复中断”的竞态；Service.start 在锁内再次检查恢复标记。备份恢复专项现 19 项，最终双版本全量已重新运行至 131 passed（上表），UI 亦重新通过。

## 独立审查 FAIL 后的修复验证（2026-10-15）

审查对象 `4d2aadc..ad524eb` 的 FAIL 结论保留；此前自审仅补最终限额检查，仍未解决读取前资源拒绝和外键校验。本轮在 `5c463cd` 上修复，不新增功能，不 push，等待 Hermes 复核。

- 资源 RED：`review2-resource-red.log` 实际 6 failed，触发禁止整文件读取断言。新增 DB/素材/合计/manifest/MAX_FILES 小常量测试；最终测试还禁止超限时复制 SQLite 快照。
- GREEN：创建/恢复共用限制；stat 和 WAL 逻辑页大小预检，manifest 精确大小计入总量，全部早于复制和读取内容；数据库与素材使用有界流式哈希，写包再次核验大小/哈希。成功生成包实际通过 validate_archive。
- 外键 RED：`review2-fk-red.log` 实际 1 failed（DID NOT RAISE）。测试以 foreign_keys=OFF 插入孤立草稿，integrity_check 仍为 ok。补 foreign_key_check 后拒绝且无输出，源库字节与孤立记录保持不变。
- 原中断 marker 失败重试保留测试未删除；备份专项合计 26 项通过，日志 `review2-green.log`。

| 最终检查 | 结果 |
|---|---|
| Python 3.12.14 pip check / ruff / 全量 pytest | 全通过；138 passed, 1 warning in 17.46s |
| Python 3.11.16 pip check / ruff / 全量 pytest | 全通过；138 passed, 1 warning in 17.92s |
| 固定上游契约 | 两版本全量均含 10 项，无跳过 |
| node --check / git diff --check | 通过 |
| 系统 Chromium 全新临时 profile UI 冒烟 | 通过，独立缓存设置不变 |

最终证据：原证据目录下 `review2-final312.log`、`review2-final311.log`、`review2-final-ui.log`。警告仍为既有 Starlette/httpx 弃用提示。全程临时虚构数据，未读取真实配置/账号、未启用 live；真实账号未验收，新提交 CI 未运行。

## Windows CI 重定向输出编码修复（2026-10-15）

基线 `6893442` 已推送 PR #1；[run 38679746659](https://github.com/lanchenglin/xianyu/actions/runs/38679746659) **失败**：Windows 3.11/3.12 的 `test_admin_cli_backup_restore_without_env_file` 在备份子进程返回 1；Ubuntu 基础、双版本契约与 UI 共 5 作业成功（用户提供的 CI 状态）。实际读取的 Windows 3.12 日志为 `/home/lan/.hermes/cache/scratch/xianyu-ci-failure/8_Run pytest -q.txt`，结果 1 failed, 127 passed, 1 skipped, 1 warning。

根因与实验：在 Linux 临时假数据上，只改变子进程 `PYTHONIOENCODING`，UTF-8 返回 0，cp1252 返回 1，但两者生成的包均通过 validate_archive。备份成功后的中文 print 无法编码，被既有 except Exception 当成备份失败；stderr 的转义错误与 CI 日志一致。恢复同样会在数据已安装后因成功提示编码失败而误报。本次未发现需要修改 SQLite URI/路径逻辑的证据。

最小修复：仅 backup/restore CLI 将 stdout/stderr 的 errors 设置为 backslashreplace，保留调用方编码；UTF-8 正常中文，cp1252/ASCII 不支持的字符转义输出。未移除备份异常捕获，错误 key 仍返回 1、仅输出脱敏固定提示，不输出密钥或原始异常。未改 Windows CI 矩阵或用测试环境强制 UTF-8 绕过问题。

TDD：`ci-encoding-red.log` 实际 4 failed / 5 passed：cp1252/ASCII 下 backup 和 restore 预期失败，UTF-8 与失败保密路径通过。新增回归均使用真实子进程，含中文临时数据目录、成功归档完整校验、破坏后恢复与暂停检查，以及错误 key 不修改数据/不泄密。修复后编码+全部备份安全测试 35 passed，见 `ci-encoding-green.log`；原 marker/限额/外键测试均保留。

| 最终本地验证 | 结果 |
|---|---|
| Python 3.12.14 pip check / ruff / pytest | 全通过；147 passed, 1 warning in 19.43s |
| Python 3.11.16 pip check / ruff / pytest | 全通过；147 passed, 1 warning in 20.43s |
| 固定 live 契约 | 两版本全量均含 10 项，无跳过 |
| node --check / git diff --check | 通过 |
| 系统 Chromium 隔离临时 profile UI | 通过 |

证据仍在 `/home/lan/.hermes/cache/scratch/xianyu-next2-evidence`：`ci-encoding-final312.log`、`ci-encoding-final311.log`、`ci-encoding-final-ui.log`。既有 Starlette/httpx 弃用警告各 1 条。浏览器使用项目独立缓存、SKIP_BROWSER_GC=1 与 `/snap/bin/chromium`，未读取已有 profile。

**本地编码复现及修复验证通过，不代表 Windows 新 CI 已绿。** 本轮不 push，待 Hermes 复核推送后核验 Windows 两作业。未访问真实账号、未读取真实 .env、未启用 live、未部署；真实账号仍未验收。
