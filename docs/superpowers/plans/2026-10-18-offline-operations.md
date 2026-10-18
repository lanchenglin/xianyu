# 离线运营增量实施计划

**Goal:** 完成取消归档/安全素材回收、离线备份调度、有界价格观察、批量本地草稿导入。
**Architecture:** 复用 SQLite、唯一审批队列和离线锁；不新增平台接口。各功能独立回归后集成 API/UI/MCP（灾备保持 CLI-only）。
**Tech Stack:** Python/FastAPI/SQLite/Pydantic、原生 JavaScript、pytest。
**Spec:** 本轮用户授权、AGENTS.md、BACKUP.md、NOTIFICATIONS.md、PUBLISH_PREVIEW.md。

## 约束与分类

- 纯本地：以下四项；不读取真实配置数据、不连接真实服务、不提交推送。
- 平台证据：发布协议与状态、消息 ACK/历史游标、卖出订单/全状态库存、改价/上下架/首次联系。具体字段清单随 OPERATIONS_NEXT 更新。
- 独立授权：FAQ 自动发送、实际通知目标、部署/客户端、云备份与新通知渠道。永久人工交易不列入开发。
- 所有测试使用隔离虚构数据、项目 .venv、env -u PYTHONPATH、指定 TMPDIR/Chromium/独立浏览器缓存。

## 1 本地草稿与素材
- [x] tests/test_local_management.py：先测取消归档 revision/账号冲突；管理员确认回收、引用保护（归档草稿/历史 action）、Agent 拒绝。
- [x] app.py/local_management.py/models.py：实现取消归档和候选查询/管理员删除；引用检查与引用创建串行，未知引用结构 fail closed。
- [x] static/app.js、MCP：恢复按钮与素材候选/明确确认；MCP 仅候选和恢复，不给删除权限。
- [x] 运行新增与原草稿/发布回归，更新契约。

## 2 离线调度
- [x] tests/test_backup_schedule.py：默认关闭、到期/未到期、活动锁跳过、失败不清理、保留边界和恢复保护。
- [x] backup_schedule.py/cli.py：单次 tick 和有界间隔运行，管理员显式启用；专属目录、先成功校验再保留，复用 server.lock，禁止读取 .env。
- [x] BACKUP.md：使用方法、不自动安装宿主定时器、不提供 API/MCP 文件能力。

## 3 搜索价格观察
- [x] tests/test_price_history.py：新鲜有效下降通知、缺失/非法/过期不判、账号/监控隔离、幂等/有界。
- [x] db.py 显式迁移；price_history.py 接 monitor_once 成功搜索，仅本地表和 notifications，无业务 action。
- [x] API/UI/MCP 历史查询，能力与通知契约。

## 4 批量本地草稿
- [x] tests/test_draft_import.py：有界预览、跨账号拒绝、确认幂等/摘要变化、无 action、逐条进度。
- [x] local_management.py/app.py/models.py/db.py：预览规范化和摘要确认，事务创建；使用既有逐条发布预览与申请。
- [x] UI/MCP 导入及进度；不提供批量批准、执行或发送。

## 5 集成验证与交接
- [x] 全量 pytest 等待 summary；pip check、ruff、node --check、UI 冒烟、git diff --check。
- [x] 更新 README/AGENTS/能力矩阵/交接/OPERATIONS_NEXT/TEST_REPORT，记录实际 skip 与失败。
- [x] 保留所有修改，父助手统一审查 commit/push；scratch 不动。
