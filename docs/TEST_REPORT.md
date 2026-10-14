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

## 真实账号上线前步骤

由主人先在 Windows 本机运行演示，确认界面；安装系统 Chrome / Node 与 live 依赖；导入本人登录态；启用真实模式后仅验证一次搜索和一次详情；再验证既有会话；最后审批单条低风险咨询，亲自在闲鱼核实。

发布需真实图片、准确价格与描述，审批后核验商品 ID 和页面。删除不适合作为冒烟测试，避免拿重要商品验证。遇到登录/安全验证/不确定状态立即停止，由主人处理。未支持的改价、重新上架、首次会话或订单功能不能靠假返回代替实现。
