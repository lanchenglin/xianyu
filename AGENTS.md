# 给后续开发 Agent 的约束

这是账号主人自用的闲鱼工作台，不是无条件全自动交易系统。当前真实能力和未实现事项以 README / `/api/capabilities` 为准，禁止把占位接口或演示数据写成已完成。

## 浏览器适配增量（2026-10-15）

项目管理 Chrome/Chromium 发现及 bridge 页面适配，不改固定上游/site-packages。管理员可选固定账号 loopback CDP，**仅 search**，其余操作 fail closed；不得注入 Cookie、关闭借用浏览器/context、导航已有页或失败后换浏览器。所有权/重定向/隔离设计及配置见 [BROWSER.md](docs/BROWSER.md)。不要将真实 Chromium 本地 HTML 验收写成真实平台或 Chrome 验收；上线和真实只读验证交 Hermes。

## 先读开发交接

续开发先阅读 [docs/DEVELOPMENT_HANDOFF.md](docs/DEVELOPMENT_HANDOFF.md)，里面有 P0/P1/P2 待办、代码入口、验收条件与本地命令。部署见 [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)，客户端接入见 [docs/MCP.md](docs/MCP.md)。

当前默认支持 Linux / WSL（Python 3.11/3.12），Windows 原生支持暂停，不继续在本分支修复 Windows。`53400f8` 的 CI run 38727928186：Linux 双版本、双 upstream-contract 和 browser-smoke 通过，Windows 双版本失败；失败记录保留在[测试报告](docs/TEST_REPORT.md)。独立分支 `work/windows-support-53400f8` 已保存快照 `53400f82f1ce4f1b1322f184b4b15e2e2c949e97`。当前 CI tests 仅 Ubuntu 双版本，其他 Linux 门槛、跨平台源码与回归均保留；新的 Linux 全绿不代表 Windows 支持或真实账号验收。

首轮 CI 的 Python 3.11 pyee 安装阻塞已通过条件锁修复；重新生成两份锁时必须使用 `--universal --python-version 3.11`，不能只按开发机 Python 版本解析。

一次实现一个可验收任务，并同步本清单、README、能力声明与测试报告。缺少上游可靠能力时保留未支持状态；不要为让能力表全为 true 伪造返回值。任务涉及新增数据字段时先设计显式迁移；涉及放宽逐条审批时必须单独完成管理员授权策略设计与相应安全测试，不能直接删除现有审批检查。

## 运营续开发（2026-10-15）

完整矩阵与真实页面取证断点见 [OPERATIONS_NEXT](docs/OPERATIONS_NEXT.md)。本批新增站内通知已读/归档、默认关闭的管理员外部摘要通知，契约见 [NOTIFICATIONS](docs/NOTIFICATIONS.md)。它是独立投递队列，不是平台写通道；仅固定摘要，Agent 不可配置目的地/密钥。恢复必须关闭外部通知，通知重试不得重放业务。无人值守 FAQ 仍 false，未修改逐条平台审批策略。

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

## 2026-10-15 续开发状态更新

基线 `4d2aadc` 的 [CI run 38566392741](https://github.com/lanchenglin/xianyu/actions/runs/38566392741) 全部 7 作业成功：Ubuntu/Windows 3.11/3.12、双版本固定 live 契约及 UI。这是历史基线结果，不代表当前 Windows 支持或真实账号验收；最新 `53400f8` 的 Windows 双版本失败及暂停决定以上文支持声明和测试报告为准。

固定上游五项核实见 [静态可行性报告](docs/UPSTREAM_FEASIBILITY.md)。真实发布因不能冻结类目/地点暂时禁用（live_publish=false）；本地草稿、演示发布和审批申请保留。禁止用默认值变化后的上游发布代替完整审批。

### P2-04 本地离线恢复增量（2026-10-15）

已提供管理员离线 `backup` / `restore --offline` CLI：一致性数据库+素材、密钥/manifest/hash 校验、受限解包、活动实例拒绝、异常回滚和中断启动保护。恢复暂停账号/监控，pending/approved 失效、running 转不确定，旧任务不重放。无 HTTP/MCP 恢复能力，Agent 不可操作任意文件。详见 [备份说明](docs/BACKUP.md)。此前“无恢复 CLI”为历史状态；定时/保留策略仍未实现。

### P2-02 单条草稿管理（2026-10-15）

已实现单条原位编辑、revision 乐观并发保护和归档 UI；显式 v2→v3 迁移增加 revision=1 / archived=0，保留原内容。PUT `/api/drafts/{id}` 接受原 account_id、revision 和完整草稿字段；POST `/api/drafts/{id}/archive` 接受 account_id、revision。账号/旧版本/已归档冲突返回 409，不另建副本；归档非平台删除，修改不会改变已冻结审批。管理员和 Agent 均可操作安全本地草稿，无新增管理员权限或任意文件操作。未增加 MCP 编辑工具（HTTP/UI 可用），既有 MCP 保存工具保持新建语义。没有素材删除接口，所有引用图片保留。批量发布、素材回收、取消归档尚未实现。
