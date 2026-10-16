# 低频末条采集、人工接管与有限 FAQ 策略

2026-10-16。继承已观察的消息 ID/正文证据，不扩展 CDP 平台写接口。

## 观察不是完整监听

- 每账号默认关闭；管理员配置 300–86400 秒，默认 900 秒。现有 `xianyu-queue` worker 每轮最多处理一个到期账号，复用 Provider 全局操作锁，不新建账号后台。
- SQLite v8→v9 显式迁移增加 `message_observation`；已有账号没有配置即关闭。配置、接管、next_run、失败次数持久化。重启至少延后一间隔，不补跑错过的次数。
- 复用按账号/cid/messageId 的 HMAC 主键和加密缓存，重复观察只更新同一记录。仅会话末条样本，**没有历史游标，可能漏掉两次采集之间的消息**，不以时间戳伪装完整断点，不将样本标 complete。最多显示 500 条缓存，数据库保留既有样本。
- 成功后间隔重置；失败指数退避至最多 24 小时。失败记录仅稳定安全码，不记录异常正文；旧缓存保留，last_sync 失败不能冒称成功。账号暂停跳过调度。
- 不自动生成草稿；自己的消息不会触发草稿或任何操作。观察不授予发送许可。

## 人工接管

账号级接管阻止新采集、草稿、发送提案和队列中尚未执行的消息发送；缓存仍可读取。Agent 可以请求接管（只收紧权限），只有管理员可解除。保存采集配置不会清除接管。解除后延后一间隔；被阻止的动作不自动重放。

接管不是已发出操作的撤回；已经进入 Provider 的在途只读请求可能完成并缓存，已经交平台的写入仍需人工核对。最终 Provider 分发前再次检查接管。没有承诺浏览器或平台已开始动作可被撤销。

## API / UI / MCP

- GET `/api/accounts/{account_id}/message-observation`：两角色可读状态，明确 coverage / send_allowed=false。
- PUT 同路径：仅管理员，enabled / interval_s；禁止额外字段、非法间隔。
- POST 同路径 `/takeover`：管理员或 Agent 安全停止。
- POST 同路径 `/release`：仅管理员解除。
- MCP `message_observation_status` / `message_human_takeover`；没有配置、解除、授权工具。原按需 sync 和草稿同样遵守接管。
- “本人只读部分样本”页面提供管理员配置、接管/解除、退避状态、无发送许可提示。

## 有限 FAQ 授权存储（不是执行器）

GET/PUT `/api/accounts/{account_id}/faq-policy`，POST `/revoke`。PUT/撤销仅管理员，Agent GET 只见 enabled / expires_at / revision 与阻止原因，不能读取模板或范围清单。

策略加密存于 settings，每次修改 revision 递增；默认关闭。必须指定 1–20 个商品 ID **且** 1–20 个会话 ID（交集语义），固定无插值模板最多 500 字，期限最多 30 天，最短间隔 300 秒、每日上限 1–100。模板保守拒绝交易/站外/凭据/指令和承诺关键词；这不是完整内容安全分类器。

当前永远 `effective=false, send_allowed=false`。enabled 仅表示保存管理员意图，不代表生效；未过期且未暂停/接管时 blocked_reason=`send_adapter_unavailable`。**没有匹配消息的自动执行器、频率消耗账本或发送授权绕过**，策略不能创建 actions。`autonomous_reply=false`、`message_sample_propose=false` 不变。未来接通前必须补真实 item/cid 同记录绑定、发送许可不可变快照、逐执行撤销/过期/限额复核、统一持久审批队列与 unknown 不重试测试；不能只删除 blocked_reason 就启用发送。

## 恢复与验收

离线恢复：关闭采集、设置接管、撤销所有 FAQ enabled；恢复账号后也不会自动重启采集或旧授权。既有动作过期/不确定处理保持不变。

开发使用临时数据库/虚构账号、随机端口、本批独立 Chromium；真实采集、实际 Hermes 注册、真实自动回复均未由本批验收。不连接 8099/9235，不读取真实运行数据，不部署/push。用户报告基线 4d5db8e 已部署 43 条/32 文本与 CI 五项绿，这是用户提供的基线，不是本增量上线证明。
