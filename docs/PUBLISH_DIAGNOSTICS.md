# 发布失败安全诊断（2026-10-19）

本增量最初基于用户提供的 f6c9fa0 独立源码副本完成诊断修复，现移植到 `133fb97` 的独立 archive 目录 `xianyu-diagnostic-current`。仅修复已进入发布执行器后的故障可见性，不恢复产品运行、不改变审批或状态机。不代表真实平台验收。下述原修复测试记录保留；本次移植验证单独记录。

## 根因与改动

- `publish_executor` 原先捕获所有异常后仅保留通用 notice；`Service.run_once` 随后无条件清空 error，丢失 Provider 已识别的故障类型。
- 现在加密 result 中新增 `failure: {code, stage}`，两个值均为闭合白名单字符串。Problem 仅保留已识别 code，未知 code 为 `upstream_error`；非 Problem 的 TimeoutError 为 `timeout`，其余为 `local_exception`。不读取或记录异常 message、动态类型名、traceback、raw ret、请求响应体。
- 仅在实际返回后的契约校验区间设置 `upload_contract_failed` / `ack_contract_failed` / `readback_contract_failed`；传输异常不冒充 ACK 或回读契约失败。既有上传回执仍按原设计加密保存、非管理员不可读，本增量 failure 不添加 URL。
- 稳定码依据 Provider、bridge、发布 guard/preflight 和每日授权 guard 的现有代码。Provider 对写超时、过大/不可解析输出统一给 `uncertain`，不能倒推出具体 timeout；回读 timeout、bridge timeout 则可保留 `timeout`。
- service 的该发布分支失败 error 使用固定中文映射，成功才 NULL；`publish.executed` audit 仅含 `state` 和 `failure_code`（成功为 null）。原有审批审计不变。

## 独立审查修复：诊断码来源隔离

独立审查发现首版 `failure_summary` 以完整中文消息表作 Problem 白名单，导致新执行传入 `Problem('unknown_historical', ...)` 或本地契约码时被错误保留。此次仅修复诊断分类：

- 显式 `PROBLEM_CODES` 仅包含现有 Provider/bridge 与发布 guard 链的稳定来源码，不再从消息表推导。
- `CONTRACT_CODES` 仅包含三个实际本地校验分类；Problem 传入这些码或 `local_exception`、`unknown_historical` 一律降为 `upstream_error`。
- 本地 contract 参数也不能冒充来源码或历史码；非法值为 `local_exception`。实际上传/ACK/回读契约校验分类不变。
- service 新执行持久化改用 `execution_failure`，仅接受来源码与本地执行码，缺失/历史码兜底为 `upstream_error`；不再调用历史只读投影函数。
- 只有 `public_failure` 可对历史缺码生成 `unknown_historical`，GET 仍不回写。unknown 不重试与每日阻断逻辑不变。

复审 RED（先补测试、未改实现）：`tests/test_publish_diagnostics.py` → **14 failed、25 passed**。涵盖五种专用码经 Problem 传入的单元与完整新 action 流程、contract 来源隔离、service 新结果持久化兜底；既有未知 marker 兜底测试直接通过。完整流程检查加密 result 解封内容、执行响应、管理员/Agent GET、audit 无敏感 marker/无历史码，且 action 不可重试；历史 GET 原记录不变测试保留。

复审验证命令环境（每条命令级设置，不全局 export）：

```bash
PYTHONPATH=/home/lan/.hermes/cache/scratch/xianyu-publish-diagnostic-fix \
TMPDIR=/home/lan/.hermes/cache/scratch \
XY_TEST_CHROMIUM=/snap/bin/chromium \
PLAYWRIGHT_BROWSERS_PATH=/home/lan/.hermes/cache/scratch/xianyu-publish-diagnostic-fix/.test-browsers \
PLAYWRIGHT_SKIP_BROWSER_GC=1 \
/home/lan/projects/xianyu/.venv/bin/python -m pytest -q --tb=short
```

定向在上述 pytest 参数后指定 `tests/test_publish_diagnostics.py tests/test_publish_executor.py tests/test_daily_publish.py tests/test_publish_content.py tests/test_publish_safety.py tests/test_publish_review.py tests/test_publish_preview_ui.py`：**114 passed、1 warning（51.26 秒）**，发布预览 Chromium UI 实际执行、未跳过。日志为副本内 `review-red.log` / `review-targeted.log` / `review-full.log`，不打入补丁。ruff 全副本通过。警告仍为既有 Starlette/httpx 弃用警告。

Chromium 全量首轮：**781 passed、1 failed、1 warning（292.59 秒）**。失败为 `test_local_publish_preview_ui` 点击 `#daily-publish-status` 时元素不可见，等待 30 秒超时；同一用例在上述定向运行通过。保留 `review-full.log`，没有修改无关 UI 代码，不把此轮描述为全绿。

Chromium 全量串行重跑：**781 passed、1 failed、1 warning（288.45 秒）**，零 skip。此次发布预览 UI 通过，失败移至 `test_admin_edit_ui_local_only` 的 `#edit-protocol-form textarea` 不可见超时（30 秒）。日志 `review-full-rerun.log` 保留。随后同一 Chromium 环境定向运行 `tests/test_item_edit_ui.py tests/test_publish_preview_ui.py` → **3 passed、1 warning（8.21 秒）**，日志 `review-ui-recheck.log`。两次全量均有 UI 可见性失败，不能宣称全量全绿；未为本次诊断修复修改 UI 或测试等待逻辑。

## 本地只读查看

复用 `GET /api/actions/{id}`（以及列表）的 `result.failure`，无需新端点，不调用上传、提交或上游回读。

管理员与非管理员均重新构造 failure，只允许已知 code/stage 标量，任意额外字段、嵌套字典、数组、未知字符串不会透传。非管理员原有 uploads / executor 协议投影限制保留。

历史 `unconfirmed` 缺少可识别 failure 时，仅在响应中添加 `unknown_historical`；stage 只使用已有已知阶段，否则 `unknown`。数据库原 result、error、state 不回填或改写。该码不表示过去发生了风控、超时、ACK 错误或发布未发生。

## 保持的安全边界

- 发生外部尝试后的错误仍为 unconfirmed，不重试、不释放 action。
- Provider 风控/登录失效暂停逻辑不变；其他故障不擅自暂停账号。
- 每日策略遇未确定结果仍禁用、日期账本永久保留、后续日期与重新授权仍被阻断。
- 没有历史 unknown 解锁、日期账本清理、action 重放或新的恢复授权。
- 上传前拒绝和其他 action 类型的既有异常处理不在本次修改范围。

## 验证

仅临时虚构账号、素材、协议；替换 transport 或子进程边界，不访问真实 .env/data/profile、私有快照、8099/9235 或平台。执行器 ACK、回读测试数据不是生产协议证据。

统一命令前缀：

```bash
PYTHONPATH=/home/lan/.hermes/cache/scratch/xianyu-publish-diagnostic-fix \
TMPDIR=/home/lan/.hermes/cache/scratch \
/home/lan/projects/xianyu/.venv/bin/python
```

- RED：`-m pytest tests/test_publish_diagnostics.py -q --tb=short` → 24 failed，预期缺少 failure/未限制敏感字段。
- GREEN 定向：`-m pytest tests/test_publish_diagnostics.py tests/test_publish_executor.py tests/test_daily_publish.py tests/test_publish_content.py tests/test_publish_safety.py tests/test_publish_review.py -q --tb=short` → 98 passed，1 个既有 Starlette/httpx 弃用警告。
- `-m ruff check .` → All checks passed（首轮发现新增模块 import 空行格式问题，修正后通过）。
- 重启旧测试更新为检查只读新增摘要，同时证明数据库原结果不变。

- 全量：在上述前缀前增加 `env -u XY_TEST_CHROMIUM`，运行 `-m pytest -q --tb=short` → 750 passed、17 skipped、1 warning，166.62 秒，exit 0。未启用 opt-in 浏览器测试，不代表浏览器或平台验收；警告为同一 Starlette/httpx 弃用警告。
- 补丁在保存的原始源码基线目录通过 `git apply --check`，在修改副本通过 `git apply --reverse --check`。首次误在已修改副本做正向检查失败，改用原始基线后通过；没有修改主仓库。

不安装依赖、不改主仓库/systemd/daily 配置、不部署、不 commit/push。补丁由父助手审查后合入。

## 133fb97 独立目录移植验证（2026-10-19）

修改前逐字节核对 archive 的 161 个文件一致。非 service 实现和测试直接移植已修复来源；service 只人工合并 action_view 的发布 failure 投影及发布执行分支的固定中文 error / audit failure_code。现版 item.edit 的 public_edit_result typed 安全摘要、bounded/projection 与其余业务保留；daily_publish.py、item_edit.py、edit_result.py、provider.py 未修改。历史 unknown 仅只读投影，不改变 unknown/daily 永久阻断，不重试。

本次统一命令级环境（没有全局 export）：

```bash
PYTHONPATH=/home/lan/.hermes/cache/scratch/xianyu-diagnostic-current \
TMPDIR=/home/lan/.hermes/cache/scratch \
XY_TEST_CHROMIUM=/snap/bin/chromium \
PLAYWRIGHT_BROWSERS_PATH=/home/lan/.hermes/cache/scratch/xianyu-diagnostic-current/.test-browsers \
PLAYWRIGHT_SKIP_BROWSER_GC=1 \
/home/lan/projects/xianyu/.venv/bin/python -m pytest -q --tb=short
```

- 全量首轮：**933 passed、2 failed、1 warning，364.67 秒**，零 skip。失败为编辑 UI `[True]` 的 `#edit-protocol-form textarea` 与发布预览 UI 的 `#daily-publish-status` 不可见超时。
- 定向 UI 复核：`tests/test_item_edit_ui.py tests/test_publish_preview_ui.py` → **5 passed、1 failed、1 warning，47.42 秒**。失败为编辑 UI `[transforms]` 的同一 textarea；发布预览通过。
- 全量串行重跑：**934 passed、1 failed、1 warning，430.68 秒**，零 skip。失败仅编辑 UI `[True]` 的同一 textarea。不能声明全量全绿。登录处理在显示 shell 后还会 await loadAccounts 并切回 overview，而这两个 UI 测试立即点击 listings，存在页面切换竞争；本次不扩范围修改 UI 或测试等待逻辑。
- 诊断/执行器/每日授权/内容/安全/审查六文件定向：**113 passed、1 warning，53.79 秒**。
- 相同环境运行 `scripts/smoke_ui.py`：**UI smoke passed**，exit 0，使用独立临时 profile 与虚构账号。
- `python -m ruff check .`：All checks passed；`python -m pip check`：No broken requirements found；`node --check xianyu_workbench/static/app.js`：exit 0。
- 警告均为既有 Starlette/httpx 弃用警告。全量计数较来源不同，因为当前 133fb97 已含后续编辑测试。

上述诊断移植阶段日志仅保存在 scratch 下 `xianyu-diagnostics-current-{full,full-rerun,ui,ui-recheck,targeted}.log`，不包含在可移植补丁中。当时仅六个代码/测试/本文路径；后续获准的 UI 修复见下节。不读取生产 .env/data/profile，不访问真实实例，不部署或提交推送。

## 后续授权：登录初始化导航竞争修复

该 UI 修复独立于发布诊断：不改 service、诊断码、daily 或平台业务。用户批准在同一独立目录定位持续 hidden，不能归为随机重跑。

### 确定性根因与 RED

先把编辑和发布预览专项桌面 viewport 显式统一为 **1440×1000**；手机独立验证 **390×844**。测试通过 asyncio.Event 门闩拦截本地 `/api/accounts`，不靠 sleep：

1. `/api/me` 已返回 admin，shell 提前显示，登录事件仍等待账号响应。
2. 用户正常点击 listings，导航 handler 已绑定，编辑 textarea 可见。
3. 释放账号响应后，登录流程继续执行 `showPage("overview")`，把 `#page-listings` 父级设为 hidden，textarea/form 自身 hidden 属性均未设置。

因此不是分辨率、权限加载错误或 onclick 未绑定，而是真实异步初始化覆盖已发生的用户导航。父级永久 hidden 也解释了为何等待 30 秒无效。

RED 日志 `scratch/xianyu-ui-init-red.log`：**12 failed、4 passed，135.30 秒**。其中一个 scratch 专用探针确定性复现导航覆盖；随补丁保留的 15 个回归为 **11 failed、4 passed**。回归在 `/me`、`/accounts`、`/dashboard` 三阶段分别阻塞响应，覆盖 admin/agent × desktop/mobile；另覆盖三阶段初始化失败后重试。探针不打入补丁。

### 最小生产修复

`static/app.js` 仅调整登录处理：先完成 role、权限投影、账号加载与初始 overview，再清空输入并显示 shell；shell 可见即登录初始化完成。失败时保留登录表单、清空 token/role、重置管理员可见性；下一次尝试清空旧错误。导航绑定与业务处理不变。没有 force click、JS 强制显示、删除断言或增大 sleep，也没有生产测试钩子。

`tests/test_login_ui.py` 用受控网络响应事件验证就绪前不可导航、就绪后 listings 与 admin 控件可见、Agent 控件隐藏，以及初始化失败后可用 Agent 重试。原编辑和发布预览用例保留全部业务断言，只显式指定桌面 viewport。

### GREEN 与最终验收

使用上节同一命令级环境（本目录 PYTHONPATH、scratch TMPDIR、独立 Chromium profile）：

- `pytest tests/test_login_ui.py tests/test_item_edit_ui.py tests/test_publish_preview_ui.py -q --tb=short` 连续 **5 轮，每轮 21 passed、1 warning**，耗时分别 75.03、77.17、77.00、81.41、76.14 秒。
- 完整全量 `pytest -q --tb=short`：**950 passed、1 warning，437.93 秒，零 failed/skip**。
- `scripts/smoke_ui.py`：**UI smoke passed**，包含桌面及 390×844 手机、Agent 隔离、退出/重登。
- ruff、pip check、Node 语法检查通过。唯一 warning 仍为既有 Starlette/httpx 弃用警告。

日志在 scratch：`xianyu-ui-init-red.log`、`xianyu-ui-init-green-{1..5}.log`、`xianyu-ui-init-full.log`、`xianyu-ui-init-smoke.log`，均不打入补丁。最终补丁相对 `133fb97` 共十个路径：原诊断六个路径，加 app.js、两份原 UI 测试和新增登录回归。原诊断实现与测试没有再次改动；历史失败结果保留，不以新全绿覆盖历史证据。
