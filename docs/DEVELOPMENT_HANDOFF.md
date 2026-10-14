# 本地开发交接与未完成功能清单

更新日期：2026-10-14。代码核对基线：[`64556d8`](https://github.com/lanchenglin/xianyu/commit/64556d84c7eed63222dd1352daff69293b8b98c0)，版本 v0.1.0。

本文件交给在本地继续开发的人、Codex、Claude Code 或 Hermes。**下列任务是待办与设计建议，不代表功能已经实现。** 本次交接只更新文档，不新增平台操作、不调整权限、不修复依赖锁文件。

## 1. 从哪里开始

| 文档 | 用途 |
|---|---|
| [仓库首页](../README.md) | 功能边界、演示安装、目录结构 |
| [部署说明](DEPLOYMENT.md) | Windows / WSL / Docker、真实连接、配置、备份 |
| [接入说明](MCP.md) | Hermes / Claude / Codex 的 MCP、HTTP API、Agent 令牌 |
| [本文件](DEVELOPMENT_HANDOFF.md) | 未完成工作、优先级、代码入口、验收条件、本地开发命令 |
| [测试报告](TEST_REPORT.md) | 本地测试与 GitHub CI 的真实记录、尚未验收事项 |
| [开发 Agent 约束](../AGENTS.md) | 后续 AI 改代码必须保留的边界 |
| [安全说明](SECURITY.md) | 凭据、审批、数据存储与隔离限制 |
| [操作 Skill](../skills/xianyu-workbench/SKILL.md) | AI 使用工作台的操作规范，不是开发完成证明 |

**先读本文件第 2～4 节，再从第 6 节搭建本地开发环境。不要根据早期聊天里的项目能力描述推断当前仓库已完成哪些接口。**

## 2. 当前状态：三类必须分开

### 2.1 已有代码，可继续复用

FastAPI + SQLite 单实例工作台；中文响应式页面；管理员/Agent 令牌分离；账号隔离与凭据加密；演示模式；搜索样本价格/地区过滤与去重；按需读取商品详情、会话和历史消息；AI 草稿；本地图片与草稿；发布/发消息/删除的持久化审批队列；幂等与超时保护；搜索监控和站内通知；MCP 代理。

这里的“已接入”不等于“在主人账号实际成功”。真实接口仍需本人授权、登录及逐条验证。

### 2.2 尚未实现或未开放

首次联系陌生卖家；可靠消息送达核验；不确定操作的核对闭环；平台修改价格/描述；普通下架/重新上架；全量本人商品同步；实时消息监听与无人值守客服；订单只读同步；外部通知推送；批量运营和更完整的草稿管理；数据库版本迁移及自动备份恢复。

`GET /api/capabilities` 中的 `false` 必须保留到相应能力真正接入。该接口是粗粒度能力声明，不是账号授权或端到端验收证明。某些增强事项没有独立 capability 字段，不能因为字段不存在就认为已实现。

### 2.3 明确保留人工，不属于待开发自动功能

付款、下单/购买、退款、确认收货、提现、成交承诺等交易动作，由主人在闲鱼完成。可以读取订单、起草建议或提醒，**不增加代提交交易的接口，不因人工点击工作台审批就默认获得付款权限**。

当前版本所有已开放对外写操作仍需逐条人工审批。用户的最终目标是更充分的运营自动化；后续低风险自动客服属于独立授权策略任务，不能直接删除现有审批检查来实现。

## 3. 已知阻塞与验收状态

### P0-ENV：Python 3.11 开发依赖（本地修复完成，Windows 新 CI 待验证）

2026-10-14 续开发：保留 3.11；显式以 `--python-version 3.11 --universal` 解析两个锁文件，Playwright 1.64 条件选择 pyee 13.0.1/14.0.0。Linux 3.11.16 与 3.12.14 干净安装、pip check、ruff 以及含固定 live 的基线均通过（各 69 passed）。CI 保留 Windows/Ubuntu 3.11/3.12，增加 pip check，并将 live 契约扩展为两版本。以下 CI 失败是历史记录，不代表当前锁；新 Windows CI 尚未运行。

首轮 [GitHub CI #1](https://github.com/lanchenglin/xianyu/actions/runs/38535793804) 对应上述代码基线：

| 作业 | 结果 | 能证明什么 |
|---|---|---|
| tests：Ubuntu + Python 3.12 | 通过 | 基础自动化测试，不包含真实账号验收 |
| tests：Windows + Python 3.12 | 通过 | Windows CI 环境的基础测试，不是主人电脑实际部署 |
| upstream-contract：Ubuntu + Python 3.12 | 通过 | 固定上游签名契约及完整测试，不实际登录闲鱼 |
| browser-smoke：Ubuntu + Python 3.12 | 通过 | 演示模式页面交互；不是闲鱼真实浏览器操作 |
| tests：Ubuntu + Python 3.11 | 安装依赖失败，测试未运行 | 不可写成测试通过或业务逻辑测试失败 |
| tests：Windows + Python 3.11 | 安装依赖失败，测试未运行 | 同上 |

Windows 3.11 作业日志明确显示 `pyee==14.0.0` 要求 `Python >=3.12`，而 `requirements-dev.lock` 将其无条件固定。`requirements.lock` 不包含 pyee；不要由此断言所有 Python 3.11 基础演示安装都会失败，也不要声称完整 3.11 开发/live 组合已通过。

**本地续开发先用独立 Python 3.12 虚拟环境。** `pyproject.toml` 仍声明 `>=3.11`，这与完整开发依赖的已验证范围存在差异。

待办与验收：

- [x] 保留 3.11，重新解析兼容的 Playwright / pyee 条件依赖，并真实安装验证。
- [x] 同步 `pyproject.toml`、运行/开发锁文件、CI 矩阵与文档，未删除失败矩阵。
- [ ] 在干净 Ubuntu/Windows 虚拟环境验证安装、`pip check`、基础测试及适用的 live 契约测试；记录每个版本的结果。

代码入口：[pyproject.toml](../pyproject.toml)、[开发锁文件](../requirements-dev.lock)、[运行锁文件](../requirements.lock)、[CI](../.github/workflows/ci.yml)、[上游契约测试](../tests/test_upstream_contract.py)。

### P0-LIVE：本地真实链路与实际部署未验收

- [ ] 主人 Windows 本机：工作台 + Python 3.12 + 系统 Chrome + Node.js + 固定 live 依赖。
- [ ] 本人完成登录和登录态导入后，依次验证一次搜索、详情、已有会话、历史消息；先只读，不批量发起请求。
- [ ] 人工审批一条无交易承诺的咨询，并在闲鱼核对实际收件人/正文；真实发消息仍应显示“结果待核实”。
- [ ] 使用主人明确允许发布的真实商品，核对图片/价格/文案/配送信息后审批单条发布，记录商品 ID 与平台状态。不拿重要商品测试删除。
- [ ] 联调主人实际 Hermes / Claude / Codex 客户端，验证 MCP 工具发现、Agent 角色、固定工作台地址和审批拒绝；远程 Gateway 不串目标。
- [ ] 使用主人自行配置的模型，验证联网草稿生成、错误提示和无密钥泄露。没有配置 API Key 就记为未验收。
- [ ] Docker 演示镜像构建、启动、重启、卷持久化及恢复；WSL 图形环境和手机访问分别实测。Docker 演示可用不代表真实搜索可用。

验收记录必须包含代码提交、操作系统/Python、演示或真实模式、实际步骤、结果和遗留问题。只提交脱敏证据；不提交账号登录态、真实聊天、密钥或个人收货信息。不得让开发 Agent 自行寻找主人其他浏览器中的登录态。

## 4. 功能开发清单

优先级：P0 为先解决的基础阻塞与真实验收；P1 为核心运营闭环；P2 为后续增强。以下接口/状态名称凡标为“新增/建议”均未实现，最终以代码与 `GET /api/schema` 为准。

### P1-01 首次联系陌生卖家

**现状：** `MessageIn` 只接受已有 `cid`、`toid` 和 `text`；执行前还要在会话列表中核验收件人。搜索到一个陌生卖家后，当前需要主人先在闲鱼建立会话。

**代码入口：** [models.py](../xianyu_workbench/models.py) 的 `MessageIn` / `ActionIn` / `ACTION_MODELS`；[service.py](../xianyu_workbench/service.py) 的 `propose` / `run_once`；[provider.py](../xianyu_workbench/provider.py) 的 `Provider.call`；[bridge.py](../xianyu_workbench/bridge.py)；[mcp_server.py](../xianyu_workbench/mcp_server.py)。

**待开发：** 审批冻结商品 ID、卖家 ID、账号和首条文字；在白名单桥中建立会话并解析真实会话 ID；复用已有会话；校验商品卖家与聊天对象一致。已有会话列表不足 50 条或部分缺失时，不能以编造 `cid` 兜底。

**验收：**

- [ ] 返回的必须是实际 `cid`，不能把请求 `mid` 当作会话 ID。
- [ ] 商品/卖家不匹配、拒绝建会话、验证码和超时均停止，不发送给猜测的对象。
- [ ] 同一审批和幂等键不会重复建会话或重复首条咨询；账号之间不串线。
- [ ] 保留已有会话发送路径及回归测试；没有可靠结果时继续显示不支持或待核实。

### P1-02 消息回执与不确定操作的核对闭环

**现状：** 真实 `message.send` 即使返回 `mid`，也保存为 `unconfirmed`；发布有有效商品 ID 时为 `submitted`，不是“上架已展示”。没有独立的操作核对页面/API 来附证据并结案。

**代码入口：** [service.py](../xianyu_workbench/service.py) 的 `run_once` / `recover` / `action_view`；[db.py](../xianyu_workbench/db.py) 的 `actions` / `audit`；[app.py](../xianyu_workbench/app.py) 的 actions 路由；[前端](../xianyu_workbench/static/app.js)。

**待开发：** 在上游确有可靠回执时做请求与响应关联；或者通过只读消息历史、本人商品状态辅助核对。为人工核对增加结果、时间、证据摘要与审计记录。新增状态前先设计迁移与兼容。

**验收：**

- [ ] 区分“本地发出”“上游接受”“平台记录可见”“对方已读”；无证据不得混为一谈。
- [ ] 核对记录绑定原账号与原操作；不会通过新的幂等键自动重发不确定写入。
- [ ] 重启、重复核对、并发核对不导致写操作再次执行。
- [ ] 交易仍只能在闲鱼人工完成；核对接口不含任何付款、退款或成交提交。

### P1-03 全量本人商品同步

**现状：** `catalog` 是本地跟踪/发布台账。不是平台全量在售、下架、已售商品；列表为空不意味着账号没有商品。

**代码入口：** [service.py](../xianyu_workbench/service.py) 的 `save_catalog`；[app.py](../xianyu_workbench/app.py) 的 item / catalog 路由；[db.py](../xianyu_workbench/db.py) 的 `catalog`；provider / bridge 的只读白名单。

**待开发：** 验证可用的本人商品分页来源；增量同步、明确状态字段、同步游标与最后成功时间；区分查看过的他人商品和确认属于自己的库存。

**验收：**

- [ ] 仅同步授权账号；分页去重，明确完整/部分结果，不把单页称为全量。
- [ ] 短暂空结果、登录失败、分页中断不能清空已有商品或误标售罄。
- [ ] 不覆盖本地未提交草稿；价格、状态和归属变动有来源与时间。
- [ ] 多账号相同商品 ID 的数据不互相覆盖；不含任意他人订单或隐私数据。

### P1-04 平台商品改价与内容编辑

**现状：** 只有本地草稿保存与发布新商品，没有更新现有闲鱼商品的操作。不能把本地台账更新显示成平台改价成功。

**代码入口：** models / provider / bridge 的操作白名单；[service.py](../xianyu_workbench/service.py) 的审批摘要与归属核验；[app.py](../xianyu_workbench/app.py) 的 capabilities；[前端](../xianyu_workbench/static/app.js)。

**待开发：** 在确认真实上游接口后新增独立的商品编辑类型；审批展示旧值、新值、账号、商品 ID、价格和运费。执行前重新校验归属及状态，完成后只读核验。

**验收：**

- [ ] 使用 Decimal 保持金额到分；禁止金额非法、越界、非本人商品与已失效审批。
- [ ] 外部价格/状态在审批后变化时要求重新审核，不直接覆盖。
- [ ] 操作超时保持不确定，不自动改价重试；不以新发布替代编辑。
- [ ] 编辑商品标价不等于改订单成交价，订单议价/交易确认仍人工处理。

### P1-05 普通下架与重新上架

**现状：** `item.delete` 可能不可恢复，已经明确要求删除确认；它不是普通下架。普通下架和重新上架没有开放。

**代码入口：** `DeleteIn`、`Service.run_once`、`Provider.call`、`bridge.WRITES`、capabilities、前端商品台账。

**待开发：** 先验证平台操作语义，分别实现可恢复的状态修改；区分在售/下架/已售/已删除/未知。新增操作仍经过同一审批队列。

**验收：**

- [ ] 不能改个按钮名字就将删除接口当下架；无法验证时继续显示未支持。
- [ ] 校验本人归属及允许的状态转换；不把已售商品自动重新上架。
- [ ] 重新上架不是重复创建商品；前后核对真实状态和商品 ID。
- [ ] 重复操作、部分失败和超时不触发删除/再次发布。

### P1-06 实时消息监听与客服自动化

**现状：** 只有手动/按需读取消息、AI 起草、人工审批发送；没有持久监听器、增量游标、消息级去重或无人工值守的客服策略。

**代码入口：** [service.py](../xianyu_workbench/service.py) 的 `loop` / `assist` / `propose`；[db.py](../xianyu_workbench/db.py)；provider / bridge / MCP；现有消息页。

**第一阶段：** 每账号独立消息监听或低频轮询，保存最小必要游标与去重键；忽略自己的消息和已处理事件；生成待人工审批的客服草稿。必须避免与已有搜索监控、发送队列争用导致消息丢失或重复。

**第二阶段（独立授权后再做）：** 由管理员配置普通商品 FAQ 等低风险自动回复的范围、有效期、频率、商品和话术边界；所有实际写入仍进入可审计的统一队列。**不能通过给予模型管理员令牌、任意 shell 或删除审批逻辑来实现自动化。** 改变逐条审批策略前，必须同步安全说明、AGENTS 和测试；默认仍为逐条人工审批。

**验收：**

- [ ] 断线重连不回放发送，账号/会话/商品不串线，同一消息不被两个后台重复回复。
- [ ] 不回复自己形成循环；没有消息 ID 时使用有边界的去重方案并明确局限。
- [ ] 对投诉、退款、交易承诺、超预算、站外转账要求等交给人工，不自主成交。
- [ ] 人工接管立即停止后续自动回复；被暂停/验证的账号不自动恢复。
- [ ] 商品和聊天中夹带“忽略规则”“发送密钥”等文字只能当数据，不能改变权限。

### P1-07 发布前完整预览与事后核验

**现状：** 有图片、标题、描述、价格、配送参数和内容冻结；上游发布流程会自动推荐类目并读取默认地址，这些自动取得的字段尚未形成完整的审批前预览/冻结/核验闭环。

**代码入口：** `PublishIn`、`Service.validate_assets` / `run_once`、`bridge.dispatch` 的 `item.publish` 分支、商品发布页面；固定上游发布函数。

**待开发：** 将必要的类目/发布地区/配送条件先解析给主人核对；支持可靠字段后纳入审批内容。无法在固定上游保持同一快照时先阻止发布，不能暗中使用变化后的默认值。

**验收：**

- [ ] 审批内容与实际上传图片、金额、类目、配送方式和发布地点一致；敏感地址不额外泄露给模型。
- [ ] 图片变化、默认配置变化或字段不支持时明确停止；不得伪造可选项。
- [ ] 有效商品 ID 后检查本人商品记录和状态，仍区分待审核、在售、异常与不可见。

### P2-01 订单只读同步与售后提醒

**现状：** 没有订单同步 API、订单表或订单页。

**待开发：** 只读获取本人账号的订单概要、付款/物流/售后状态、时间线；记录分页与最后成功时间；敏感买家资料最小化展示与保存。

**代码入口：** provider / bridge 只读白名单、db 显式迁移、app 只读 API、前端订单页、MCP 只读工具。

**验收：**

- [ ] 同一订单不重复入库，部分拉取失败不清空旧数据；账号权限不串。
- [ ] 不在日志、模型输入、通知或公开接口暴露完整地址/电话。
- [ ] 不增加付款、订单改价、退款、确认收货或自动发货等交易执行路径。

### P2-02 批量发布与本地管理完善

**现状：** 有单条草稿保存、图片和发布申请，没有完整批量导入/批量预览/逐条执行进度，也没有完整草稿原位编辑、归档与素材回收工作流。

**待开发：** 单条功能稳定后增加批次、每条独立幂等键与审批摘要；支持草稿编辑版本与归档；为图片引用设计可核验关系，不让整理素材破坏已审批任务。

**代码入口：** app 的 draft / upload 路由、db 的 drafts / assets / actions、Service.propose / run_once、前端发布页。

**验收：**

- [ ] 一批中部分失败不会重新发送全部；可暂停尚未开始的条目，保留准确进度。
- [ ] 批量功能不跳过逐条内容校验或绕开账号限流；不提供批量骚扰询价。
- [ ] 同一草稿编辑不产生难以追踪的重复条目；归档不是删除平台商品。
- [ ] 仍被草稿或审批引用的图片不得删除；不可恢复删除必须由人工明确选择。

### P2-03 外部通知与搜索监控增强

**现状：** 有定时搜索、样本过滤和站内新结果通知；没有微信/邮件等外部推送，没有可靠价格历史和降价告警；监控并不扫描全平台。

**待开发：** 外部通知适配、账号异常/待审批提示、发送重试与去重；按商品 ID 保存价格快照与触发条件；完善通知已读/归档与监控编辑。

**代码入口：** `Service.monitor_once`、db 的 monitors / notifications、app 的 monitor / notifications 路由、Settings、前端监控页。

**验收：**

- [ ] 通知失败只重试通知，不重发询价/发布操作；通知不携带令牌、登录态或完整聊天。
- [ ] 快照过期、价格未知、样本未命中不误判为涨跌或售罄；明确抓取时间与覆盖范围。
- [ ] 验证/限流时退避并提示人工；不提供代理轮换、验证码绕过或高频抓取兜底。

### P2-04 数据迁移、备份恢复与长期运行

**现状：** SQLite 建表使用 `CREATE TABLE IF NOT EXISTS`；有人工停机备份说明，无数据库版本迁移、自动备份/恢复演练、数据保留与清理策略。只支持单实例。

**代码入口：** [db.py](../xianyu_workbench/db.py)、[config.py](../xianyu_workbench/config.py)、[cli.py](../xianyu_workbench/cli.py)、[Dockerfile](../Dockerfile)、[compose.yaml](../compose.yaml)。

**待开发：** 在新增订单/会话/核对字段前先增加显式迁移；升级备份、失败回退、恢复校验；分别保护密钥与数据；为审计/通知/素材制定有界保留策略。

**验收：**

- [ ] 旧版数据库可无损升级，迁移失败不留半套结构；错误密钥恢复应报错而不是清空数据。
- [ ] 备份覆盖必要 WAL 状态或停机后一致快照；恢复后不能重放已执行或不确定写操作。
- [ ] `XY_VAULT_KEY` 不丢失、不公开；真实素材和登录态不进入 Git。
- [ ] 多实例仍被拒绝；需要多进程/多机器时单独设计队列、租约和凭据隔离，不能只增加 workers。

### P2-05 其他后台、独立浏览器服务与运维接入

**现状：** 当前只接一个固定上游；没有接入 `xianyu-auto-reply`、Goofish-Z 等第二套运营后台，也没有 Windows 浏览器远程服务。

**原则：** 这不是必须同时部署多个开源项目的清单。先修通现有功能；只有确认新组件提供所需、可验证的能力时，才作为适配器接入。其当前版本、许可和接口需重新核实，不能照早期选型描述硬接。

**验收：**

- [ ] 复用唯一审批和写队列，不启动两套抢同一账号消息的自动回复程序。
- [ ] 明确每个账号、浏览器和远程 Gateway 的对应关系；失效即停，不自动切换另一登录态。
- [ ] 服务间认证、最小权限、健康检查、固定地址；远程浏览器端口不裸露公网。
- [ ] 实际版本与部署机测试留档，不能把 Windows 成功当 WSL / 无头 Docker 成功。

## 5. 改代码的统一路径与完成定义

新增平台能力不要只补一个 HTTP 路由。依次检查：

`models.py 参数校验 → app.py 鉴权/能力声明 → service.py 审批/执行/核对 → provider.py 白名单及账号隔离 → bridge.py 子进程适配 → db.py 显式迁移 → static/ 页面 → mcp_server.py 和 Skill → 测试及文档`。

上游固定提交为 `c2d5a02ad83b18863514389cedf7afbd993b683d`，入口在 [pyproject.toml](../pyproject.toml)。**上游模块只能在 bridge 子进程导入**：其全局 `subprocess.Popen` 修改曾导致 MCP 导入异常，不要导入 API/MCP 主进程。参考 [上游契约测试](../tests/test_upstream_contract.py)。

每个任务完成时至少满足：

- [ ] 参数、未知操作、跨账号、审批摘要、重复执行、超时/重启、验证暂停均有适用回归测试。
- [ ] 演示数据明确标记；操作失败/未核实不返回虚假成功；不可绕过永久人工交易边界。
- [ ] 同步 README 能力表、`/api/capabilities`、MCP/Skill、部署说明和本任务状态。
- [ ] 记录实现提交与测试证据；将“代码完成”和“真实账号已验收”分别勾选。

现有关键测试入口：[tests/test_workbench.py](../tests/test_workbench.py)。优先保留 `test_agent_proposes_but_cannot_approve`、`test_idempotency_and_content_conflict`、`test_atomic_concurrent_claim`、`test_wrong_recipient_is_never_sent`、`test_recovery_never_replays_running_action`、`test_timeout_never_retries_a_write`、`test_transactions_and_unknown_actions_not_exposed`。

## 6. 本地开发命令

### 6.1 拉取与建立开发分支

已有本地副本时，先检查并妥善提交或暂存**自己的源码改动**；不要暂存 `.env` / data / 登录态。不要用 `reset --hard` 或 `git clean` 清场。

```bash
git status
git switch main
git pull --ff-only origin main
git switch -c feat/local-next
```

如果尚未克隆，先 `git clone https://github.com/lanchenglin/xianyu.git` 并进入 `xianyu`。已有同名开发分支时直接切换到它，不重复创建。`git pull` 遇到冲突/非快进先处理，不强推覆盖他人更改。

### 6.2 Windows PowerShell（推荐 Python 3.12）

以下按新工作副本、尚无 `.venv` 编写。旧 `.venv` 若来自 3.11，请另建干净的 3.12 环境并相应替换路径；不要删除 `.env` 或 data 来“修复”环境。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m pytest -q

# 仅首次初始化本地配置；已有 .env 会拒绝覆盖，这是保护机制
.\.venv\Scripts\python.exe -m xianyu_workbench.cli init
.\.venv\Scripts\python.exe -m xianyu_workbench.cli serve
```

打开 `http://127.0.0.1:8099`，先用演示账号。保持 `XY_LIVE_ENABLED=false`。管理员自己读取本地管理员令牌，AI 只获得专用 Agent 令牌。

### 6.3 Linux / WSL（Python 3.12）

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m pip check
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q

# 仅首次初始化
.venv/bin/python -m xianyu_workbench.cli init
.venv/bin/python -m xianyu_workbench.cli serve
```

系统须已有可用的 `python3.12` 和 venv。基础服务与测试无需图形桌面；真实搜索另需同一环境中的系统 Chrome / 显示会话，详见部署说明。

### 6.4 固定上游契约测试（不访问闲鱼）

```powershell
# Windows，与上面同一个 Python 3.12 环境
.\.venv\Scripts\python.exe -m pip install -e ".[live,mcp]"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m xianyu_workbench.cli doctor
```

Linux/WSL 把可执行文件换为 `.venv/bin/python`。未安装 live 依赖时上游契约模块会跳过；当前基线本地 Linux 完整记录为 69 passed，不应为了凑数量更改测试。以实际收集数量、跳过原因和结果为准。`doctor` 只做依赖检查，不证明账号可用。

### 6.5 演示页面交互测试

测试浏览器与系统真实 Chrome 是两回事。以下安装使用项目独立缓存，不清理其他项目的共享浏览器。

```powershell
# Windows PowerShell
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) ".test-browsers"
$env:PLAYWRIGHT_SKIP_BROWSER_GC = "1"
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe scripts/smoke_ui.py
```

```bash
# Linux / WSL
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.test-browsers"
export PLAYWRIGHT_SKIP_BROWSER_GC=1
.venv/bin/python -m playwright install chromium
.venv/bin/python scripts/smoke_ui.py
```

Linux 可能还需要 Playwright 提示的系统依赖，由本机管理员安装。浏览器下载失败记为环境阻塞，不算页面验收通过。此脚本启动临时演示服务和数据，禁止改为自动使用主人的真实账号。

## 7. 可直接交给本地开发 AI 的指令

```text
你在 lanchenglin/xianyu 仓库续开发，不是从零重建。
先阅读 AGENTS.md、README.md、docs/DEVELOPMENT_HANDOFF.md、
docs/DEPLOYMENT.md、docs/MCP.md、docs/SECURITY.md、docs/TEST_REPORT.md。

先核对当前代码和 Git 状态，不覆盖我的未提交改动。
本地使用独立 Python 3.11/3.12；P0-ENV 已本地修复，Windows 新 CI 待验证。
按 P0-ENV / P0-LIVE → P1-01～P1-07 → P2 的优先级逐项完成，
库存同步、迁移和消息回执等依赖应先于相应写操作闭环。
先跑演示及测试，真实登录和写操作仅在我明确授权并人工审批后验证。

保留单实例、唯一写队列、账号隔离、幂等、不确定写入不重试和风控暂停。
不得把 mid 当 cid 或送达回执，不得把 delete 当普通下架。
交易由我在闲鱼完成；不要增加自动付款、退款、确认收货或成交提交。
不要读取/提交 .env、登录态、真实聊天或把管理员令牌交给模型。
不能把占位接口或演示结果写成已实现；缺少可靠接口时明确记录阻塞。

每完成一项，提交对应代码与测试，更新交接清单、能力表和测试报告。
分别说明“代码已完成”“自动测试结果”“真实账号验收结果”，
并列出剩余事项和本地启动命令。
```

## 8. 后续维护记录模板

```text
任务编号：
状态：未开始 / 开发中 / 代码完成待实测 / 已验收 / 阻塞
代码提交：
变更文件与数据库迁移：
操作系统 / Python / 上游版本：
演示测试结果：
真实账号验证范围（未验证就明确写未验证）：
异常与重试处理：
剩余问题：
```

本文件的基线和 CI 记录是历史事实。后续开发新增记录并更新勾选状态，不要删掉失败结果伪装成全程通过。
