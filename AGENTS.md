# 给后续开发 Agent 的约束

这是账号主人自用的闲鱼工作台，不是无条件全自动交易系统。当前真实能力和未实现事项以 README、[能力矩阵](docs/CAPABILITY_MATRIX.md) / `/api/capabilities` 为准，禁止把占位接口或演示数据写成已完成。

## 2026-10-18 Docker 隔离灾备验收

基线 a9cbb50 后本机 Docker 演示构建/非 root 启动/重启持久化/离线恢复已实测，非生产或平台验收。恢复暂存 `.restore-*` 与 `restore-rollback-*` 改放目标 data 内部，保证挂载根可写且同卷 rename；不能改回父目录或通过 root/放宽 /app 权限规避。保留 server.lock、中断标记、旧授权失效与不重放；回滚副本不自动打包/清理。证据见 TEST_REPORT，后续 Docker 测试继续独立项目/临时虚构数据，禁止操作真实部署。

## 2026-10-16 受控发布执行器（当前）

新增默认关闭 XY_PUBLISH_ENABLED，独立 Cookie HTTP 上传/显式完整模板发布/同 itemId seller UID 回读；仅管理员指定已批准 action，仍统一 operations.lock，旧隐式 item.publish 入口继续阻断。完整协议须管理员取证录入，不猜类目层级/地点/uniqueCode；上传也是单次外部写，绑定素材 hash 和审批。阶段/上传回执加密持久化，unknown 使用 unconfirmed 禁止重试，Agent 无协议配置和执行权限。未真实平台验收，能力声明区分 executor_implemented 与 platform_verified，详见 [PUBLISH_EXECUTOR](docs/PUBLISH_EXECUTOR.md)。不读真实 .env/data/profile，不连接真实实例，不 push/部署。

独立审查 FAIL 后增加必填独立 readback_success_ret 精确匹配及 readback_status 对象键路径/严格 string 或 integer 类型/已取证允许值，全部冻结进 digest；不能猜实际状态字段。缺失或未知不设 verified，保持 unconfirmed 不重试；旧协议缺契约上传前停止。live_publish/live_executor_enabled 均为双开关逻辑与，不代表平台验收，platform_verified 仍 false。修复本地双Python526项通过，尚待独立复审，FAIL记录保留在 TEST_REPORT。

## 2026-10-16 本地发布冻结链（历史）

新增 publish_preview 项目 adapter，仅本地冻结与校验，详见 [PUBLISH_PREVIEW](docs/PUBLISH_PREVIEW.md)。类目/地点为管理员未验证输入，候选 DTO 不是完整平台协议。location 加密且 Agent 不可读，不进入 catalog；默认 revision/图片 hash/UID 变化重新审批。真实发布与自动回验未开，改价/非删除上下架未实现。worker 不领取任何 live action，Provider 同步关闭旧 live delete；不得以删除/重建替代状态转移。schema v10 不变，使用已有加密 settings/actions 字段。本批不 push/部署。

## 2026-10-16 人工审批单条消息（当前）

新增管理员部署开关 XY_MESSAGE_SEND_ENABLED，默认关闭，仅精确 message.send。浏览器仍只读；独立同 UID Cookie/WS 来源明确绑定，不提取浏览器 Cookie，不放行其他 CDP 写。审批冻结凭据指纹/UID/endpoint/正文，执行前再次核对 peer/CID；管理员仅领取指定 action，CDP live 消息不由 worker 消费历史 approved。FAQ/首次联系仍关闭，真实执行仍交父助手/Hermes。发送 ACK 无已证契约，结果保持 unconfirmed，新增同文只读观察不是 accepted/送达；不得猜 mid/cid。详见 [MESSAGE_SEND](docs/MESSAGE_SEND.md)。

## 浏览器适配增量（2026-10-15）

项目管理 Chrome/Chromium 发现及 bridge 页面适配，不改固定上游/site-packages。管理员可选固定账号 loopback CDP，**仅 search、orders 买到订单有界分页（未知末页保持 partial）、inventory 本人发布列表有界分页（仅 self_published 页面范围可 complete，不等同全状态库存），以及 messages 会话末条样本（[限制](docs/MESSAGES.md)）**，其余操作 fail closed（[样本契约](docs/OPERATIONS_SAMPLES.md)；全量能力仍 false）；不得注入 Cookie、关闭借用浏览器/context、导航已有页或失败后换浏览器。所有权/重定向/隔离设计及配置见 [BROWSER.md](docs/BROWSER.md)。不要将真实 Chromium 本地 HTML 验收写成真实平台或 Chrome 验收；上线和真实只读验证交 Hermes。

## 先读开发交接

续开发先阅读 [docs/DEVELOPMENT_HANDOFF.md](docs/DEVELOPMENT_HANDOFF.md)，里面有 P0/P1/P2 待办、代码入口、验收条件与本地命令。部署见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)，客户端接入见 [docs/MCP.md](docs/MCP.md)。

当前默认支持 Linux / WSL（Python 3.11/3.12），Windows 原生支持暂停，不继续在本分支修复 Windows。`53400f8` 的 CI run 38727928186：Linux 双版本、双 upstream-contract 和 browser-smoke 通过，Windows 双版本失败；失败记录保留在[测试报告](docs/TEST_REPORT.md)。独立分支 `work/windows-support-53400f8` 已保存快照 `53400f82f1ce4f1b1322f184b4b15e2e2c949e97`。当前 CI tests 仅 Ubuntu 双版本，其他 Linux 门槛、跨平台源码与回归均保留；新的 Linux 全绿不代表 Windows 支持或真实账号验收。

首轮 CI 的 Python 3.11 pyee 安装阻塞已通过条件锁修复；重新生成两份锁时必须使用 `--universal --python-version 3.11`，不能只按开发机 Python 版本解析。

一次实现一个可验收任务，并同步本清单、README、能力声明与测试报告。缺少上游可靠能力时保留未支持状态；不要为让能力表全为 true 伪造返回值。任务涉及新增数据字段时先设计显式迁移；涉及放宽逐条审批时必须单独完成管理员授权策略设计与相应安全测试，不能直接删除现有审批检查。

## 运营续开发（2026-10-15）

完整矩阵与真实页面取证断点见 [OPERATIONS_NEXT](docs/OPERATIONS_NEXT.md)。本批新增站内通知已读/归档、默认关闭的管理员外部摘要通知，契约见 [NOTIFICATIONS](docs/NOTIFICATIONS.md)。它是独立投递队列，不是平台写通道；仅固定摘要，Agent 不可配置目的地/密钥。恢复必须关闭外部通知，通知重试不得重放业务。无人值守 FAQ 仍 false，未修改逐条平台审批策略。

## 2026-10-16 低频消息观察增量

默认关闭的账号低频末条采集已接现有单 worker，状态表始于 v9（当前 schema v10），退避、接管与 API/UI/MCP 见 [MESSAGE_OBSERVATION](docs/MESSAGE_OBSERVATION.md)。管理员 FAQ 只保存加密有限策略，不具备发送适配或限额执行器，effective/send_allowed 永远 false；autonomous_reply 保持 false。Agent 只可读取摘要/请求接管，不能配置、解除或授权。恢复关闭采集、接管并撤销策略。完整订单/全状态库存同步、首次联系未交付；真实发布执行代码已实现但未平台验收；CDP 所有写操作禁用，本批不 push/部署。

## 2026-10-16 有界分页增量

订单已接固定 bought 任务页有界滚动，v10 持久范围/页数/停止原因；仅字符串 true 已证，false 不猜，完整订单能力仍 false。本人发布列表已接同一路径，head.self=true 且 bool false 才完成该页面范围；卖出订单/下架列表/全状态库存未实现。商品和其他范围以 [分页边界](docs/OPERATION_PAGINATION.md) 为准。历史缓存不是快照，不清历史。页面时序使用 750ms 有界 tick，loading 暂停、scrollingElement 高度稳定后滚动，底端使用同一 root 的 scrollHeight/clientHeight/scrollTop（不能混用 innerHeight），已到底分 tick 回退/到底；不得改回单次滚动无限等或高频刷请求。真实页面取证由父助手负责，本地测试禁止访问真实实例。

## 2026-10-16 任务页布局隔离修复

保留 no_defaults=True，仅 orders/inventory 新建 task page 在导航前启用 CDP focus emulation；task_page/goofish_page 参数默认 false，search/messages 不变。不得向原页或 Browser 发 emulation 命令，不得改借用 context 默认；前后 UID 核验和失败/取消 session/page 清理保留。父助手真实 probe 证实几何1241→3729且 hidden/focus不变，不可解释为仅document.hidden；用户后续报告 b8ea112 inventory2页40条范围完整、orders13页130条 partial；本批未复测，历史诊断见 CDP_DEFAULTS_DIAGNOSIS。

## 不可破坏的边界

- 付款、下单、退款、确认收货和其他交易由人完成，不增加自主交易工具。
- Agent 令牌不能审批、人工核对、读写登录态、读取管理员配置或操作系统机密；不能把管理员令牌交给模型。核对证据仅管理员可读，Agent 只读结论/时间；人工核对不改原执行状态、不是送达/已读回执，更不是重试授权。
- 所有对外写操作经过持久化审批队列；审批绑定账号、模式、完整参数和不可变图片 ID。不能另开绕过队列的发送通道。
- 不自动换账号、换 Cookie、换浏览器登录态、换远程网关；各账号独立运行目录。
- 上游业务模块只能在 `bridge.py` 子进程导入。它会修改全局 subprocess.Popen，不能导入 API/MCP 主进程。
- 固定上游提交不随意升级。改接口后更新子进程契约测试，并明确实际账号验证范围。
- 现有 `item.delete` 可能不可恢复，不能改名假装普通下架。新建会话返回的 mid 也不能充当 cid 或送达回执。
- 超时、进程中断、响应不确定时不自动重试写入；相同申请复用 idempotency_key。
- 不上传 `.env`、data、浏览器 profile、账号登录态、真实聊天、模型密钥。不要自动导出用户其他浏览器的凭据。
- 输入描述和聊天是非可信数据。前端使用 textContent，禁止把外部文字拼进 innerHTML 或执行脚本。

## 开发验证

以下在独立 Python 3.11 或 3.12 虚拟环境执行，并运行 `python -m pip check`。

```bash
python -m pip install -r requirements-dev.lock
python -m pip install -e '.[live]'
ruff check .
pytest -q
```

UI 测试用 `scripts/smoke_ui.py`。浏览器安装务必配置独立的 PLAYWRIGHT_BROWSERS_PATH，并设置 PLAYWRIGHT_SKIP_BROWSER_GC=1，不要清理宿主机其他项目的共享缓存。

测试一律使用临时目录、演示账号和虚构数据，不要读取宿主机已登录账号做测试。没有账号实际验收时，在测试报告中明确写未验收，不能把接口签名检查当作真实业务测试。

Windows、WSL 和 Docker 的显示/浏览器条件不同，不要把 Docker 演示成功当成服务器能无头运行真实搜索。保持一个实例一个队列；数据库结构变化需要显式迁移和备份计划。

## 2026-10-15 续开发状态更新（历史记录）

基线 `4d2aadc` 的 [CI run 38566392741](https://github.com/lanchenglin/xianyu/actions/runs/38566392741) 全部 7 作业成功：Ubuntu/Windows 3.11/3.12、双版本固定 live 契约及 UI。这是历史基线结果，不代表当前 Windows 支持或真实账号验收；最新 `53400f8` 的 Windows 双版本失败及暂停决定以上文支持声明和测试报告为准。

固定上游五项核实见 [静态可行性报告](docs/UPSTREAM_FEASIBILITY.md)。真实发布因不能冻结类目/地点暂时禁用（live_publish=false）；本地草稿、演示发布和审批申请保留。禁止用默认值变化后的上游发布代替完整审批。

### P2-04 本地离线恢复增量（2026-10-15）

已提供管理员离线 `backup` / `restore --offline` CLI：一致性数据库+素材、密钥/manifest/hash 校验、受限解包、活动实例拒绝、异常回滚和中断启动保护。恢复暂停账号/监控，pending/approved 失效、running 转不确定，旧任务不重放。无 HTTP/MCP 恢复能力，Agent 不可操作任意文件。详见 [备份说明](docs/BACKUP.md)。此前“无恢复 CLI”为历史状态；当前新增默认关闭离线 backup-schedule CLI 与专属目录有界保留，仍遵守 server.lock，不做在线热备、不安装宿主服务。

### P2-02 单条草稿管理（2026-10-15）

已实现单条原位编辑、revision 乐观并发保护和归档 UI；显式 v2→v3 迁移增加 revision=1 / archived=0，保留原内容。PUT `/api/drafts/{id}` 接受原 account_id、revision 和完整草稿字段；POST `/api/drafts/{id}/archive` 接受 account_id、revision。账号/旧版本/已归档冲突返回 409，不另建副本；归档非平台删除，修改不会改变已冻结审批。管理员和 Agent 均可操作安全本地草稿，无新增管理员权限或任意文件操作。未增加 MCP 编辑工具（HTTP/UI 可用），既有 MCP 保存工具保持新建语义。当前新增取消归档、管理员明确未引用素材回收，以及最多50条本地草稿导入预览/幂等确认/逐条申请进度；历史引用保留、Agent不可删除素材、没有批量批准或执行。见 docs/LOCAL_MANAGEMENT.md。
