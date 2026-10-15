# v0.1.0 开发验收记录

日期：2026-10-14。此文件只记录实际执行的检查，不把待部署步骤写成已验收。

以下“已执行”为首次 Linux 开发环境的历史记录；上传后的 GitHub CI 结果另列于下一节，不混为本地主人电脑验收。未完成功能与续开发步骤见 [开发交接清单](DEVELOPMENT_HANDOFF.md)。

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

## 当前验收状态与仍需本地确认的项目

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

由主人先在 Windows 本机运行演示，确认界面；安装系统 Chrome / Node 与 live 依赖；导入本人登录态；启用真实模式后仅验证一次搜索和一次详情；再验证既有会话；最后审批单条低风险咨询，亲自在闲鱼核实。

发布需真实图片、准确价格与描述，审批后核验商品 ID 和页面。删除不适合作为冒烟测试，避免拿重要商品验证。遇到登录/安全验证/不确定状态立即停止，由主人处理。未支持的改价、重新上架、首次会话或订单功能不能靠假返回代替实现。

## 2026-10-15 续开发状态更新

基线 `4d2aadc` 的 [CI run 38566392741](https://github.com/lanchenglin/xianyu/actions/runs/38566392741) 全部 7 作业成功：Ubuntu/Windows 3.11/3.12、双版本固定 live 契约及 UI。上文“新 CI 待验证”为此前历史状态，现已解决；不代表真实账号验收。本轮新增提交尚未 push，CI 待 Hermes 审查后验证。

固定上游五项核实见 [静态可行性报告](UPSTREAM_FEASIBILITY.md)。真实发布因不能冻结类目/地点暂时禁用（live_publish=false）；本地草稿、演示发布和审批申请保留。禁止用默认值变化后的上游发布代替完整审批。

A 安全保护 TDD：a-red.log 实际失败（此前进入真实处理），a-green.log 全量 108 passed / 1 既有弃用警告；证据目录 `/home/lan/.hermes/cache/scratch/xianyu-next2-evidence`。

### P2-04 本地离线恢复增量（2026-10-15）

已提供管理员离线 `backup` / `restore --offline` CLI：一致性数据库+素材、密钥/manifest/hash 校验、受限解包、活动实例拒绝、异常回滚和中断启动保护。恢复暂停账号/监控，pending/approved 失效、running 转不确定，旧任务不重放。无 HTTP/MCP 恢复能力，Agent 不可操作任意文件。详见 [备份说明](BACKUP.md)。此前“无恢复 CLI”为历史状态；定时/保留策略仍未实现。

B 阶段：15 项备份恢复测试通过；全量 123 passed / 1 既有弃用警告。实际临时数据备份→破坏副本→恢复、错误 key 拒绝、重新打开数据库并运行队列不重放、活动锁/路径穿越/符号链接/大小限制/哈希/未来 schema/回滚注入均覆盖。b1～b6-red.log 记录逐行为失败，b-green.log 为全量回归。
