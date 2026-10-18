# 当前能力 / 实现 / 验收矩阵

2026-10-18，源码核对 `a9cbb50` 及本批工作树；以 `xianyu_workbench/app.py` 的 `/api/capabilities` 为字段来源。true 是适配/本地能力存在，不保证任意模式可用；运行开关、账号授权和平台验收是三件事。历史测试数量与 FAIL 见 [TEST_REPORT](TEST_REPORT.md)，本批结果只记在该报告对应日期。

| 能力与 capability | 当前实现/入口 | 隔离测试证据（不是平台证据） | 真实平台验收 | 剩余阻塞/限制 |
|---|---|---|---|---|
| search/item_detail/existing_chats/message_history=true | provider/bridge 固定适配；CDP 仅 search/orders/inventory/messages | test_workbench、test_upstream_contract、test_browser_* | 本批未验收；此前用户报告 CDP search 成功 | 模式不同，CDP 不提供 item/chats/history |
| local_drafts/local_draft_edit/local_draft_archive=true | 本地原位编辑、revision、归档 | test_drafts、smoke_ui | 本地能力不需平台 | 新增 local_draft_unarchive/local_asset_recycle/local_draft_import=true，管理员明确回收、历史引用保护、单条审批；test_local_management/test_draft_import |
| send_with_approval/message_sample_propose=true | 唯一审批，管理员指定单条；独立 Cookie/WS；默认关闭 | test_message_send*、MCP stdio、隔离 UI | 未验收真实发送 | 无可靠 ACK；unconfirmed 不重试；FAQ 不发送 |
| message_bodies/message_reply_drafts/partial_messages=true | 严格文本解码、末条缓存/本地模板草稿 | test_message_text/messages/message_reply、隔离 WS | 用户报告旧基线43条/32文本，本批未复测 | 非完整历史；未知编码不猜 |
| message_observation=true | 默认关闭，最短300秒，同 worker、去重/退避/接管 | test_message_observation、test_faq_policy、smoke_ui | 本批未验收 | 可能漏中间消息；send_allowed=false |
| autonomous_reply=false | 有限 FAQ 仅加密策略存储 | FAQ 权限/撤销/恢复回归 | 未验收、未开放执行 | item/cid 证据、限额账本及单独授权决策 |
| local_publish_preview/publish_with_approval=true | 本地 hash/类目/配送/私密地点冻结，预览不上传 | test_publish_preview、test_publish_preview_ui、MCP stdio | 本地输入不是平台核验 | candidate 不是完整协议 |
| publish_policy.executor_implemented=true | publish_executor：上传→显式提交→精确 ret/同 ID UID/类型状态回读 | test_publish_executor/review/transport/backup | **未验收**，platform_verified=false | 完整 schema/uniqueCode/图片/配送/状态语义需真实证据 |
| live_publish=live_enabled AND publish_enabled | 双开关默认 false，管理员指定 action；旧隐式 publish 关闭 | 四种开关组合回归 | 开启也不表示验收 | publish_complete_snapshot=false；verified 不保证内容价格等价或在售 |
| delete_with_explicit_approval=true | 演示删除申请/确认/归属链；旧 live delete 阻断 | test_workbench、test_publish_safety | 无真实删除验收 | 此粗粒度 true **不代表 live 删除开放**，不等于普通下架 |
| partial_orders/partial_inventory=true | bought_orders/self_published 有界滚动、缓存/进度 | test_operation_pagination、test_operations_*、隔离 Chromium | 用户报告 b8ea112：库存2页40条范围完整；订单13页130条时限 partial | 本批未复测；orders_terminal_verified=false；缓存历史并集非快照 |
| order_sync/full_inventory_sync=false | 没有全范围同步 | 范围/partial/失败不清库回归 | 无完整验收 | 卖出/下架/全状态未实现；sample_policy.platform_verified=false |
| first_contact/platform_edit_price/platform_relist=false | 未开放 | 未知操作/交易拒绝回归 | 无 | 真实协议及同 ID 状态语义缺证；不猜接口 |
| search_monitors/notification_state=true | 最短5分钟、去重、已读/归档 | test_notifications、smoke_ui | 本批未验收真实监控 | search_price_history/search_price_drop_notifications=true；test_price_history；仅新鲜连续搜索样本，非全平台扫描 |
| external_notifications=true | 默认关闭、admin 配置，钉钉/webhook 固定摘要，独立 outbox | test_external_notifications/notification_transport；本地 TLS | 未投递真实钉钉/webhook | 超时可能重复通知；最多3次仅重试通知、不重试业务 |
| manual_reconciliation=true | admin 一次不可覆盖结论/加密证据；Agent 只看概要 | test_workbench、隔离 UI | 本批无真实人工证据验收 | automatic_receipt_verification=false；观察非送达，不重放 |
| offline_backup_restore_cli=true | backup.py/cli.py；v12、数据库+素材、密钥/关系校验、恢复暂停 | test_backup*、test_cli_encoding、test_publish_backup | 仅虚构数据恢复演练 | offline_backup_schedule_cli=true；默认关闭离线调度/专属目录保留，test_backup_schedule；无在线/云备份、HTTP/MCP 文件入口 |
| mcp=true | 固定目标 Agent-only stdio | test_mcp_stdio 实际 SDK→临时 API | 实际 Hermes/其他客户端未验收 | 不能把 SDK 测试当客户端已配置 |
| payment/refund/confirm_receipt=false | 永久人工，无交易执行工具 | 白名单/权限回归 | 不安排自动执行验收 | 下单/提现/成交承诺同样人工 |

## 环境矩阵

- Linux/WSL Python 3.11/3.12：当前支持；本批实际仅项目 `.venv` Python 3.12.14，历史双版本结果不冒充本批运行。
- Windows 原生：暂停。`53400f8` 的 Windows 双 CI 失败保留；当前 Linux 五作业门槛不表示 Windows 恢复。
- Chromium：隔离临时 profile/本地页面/随机端口测试，非真实账号。Google Chrome、实际桌面/WSLg 仍需各环境验收。
- Docker：2026-10-18 本机隔离演示构建/非 root 启动/API/重启持久化/离线备份恢复及不重放已实际通过；发现并修复挂载根恢复暂存/回滚位置问题。专属资源已清理；不是生产部署、真实浏览器或平台验收，详见 TEST_REPORT。
- 无人值守权限、宿主文件权限与实际客户端联调不会由 capability=true 自动获得。
