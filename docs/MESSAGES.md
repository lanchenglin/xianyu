# 会话末条消息只读样本

## 2026-10-16 人工发送增量（优先于历史提案禁用描述）

已核验 peer/CID 可在管理员显式默认关闭开关下提交普通文本审批；CDP 仍只读核验，实际发送用独立同 UID Cookie/WS，非浏览器唯一来源。管理员指定单条执行，FAQ 不执行。只读核对不是 ACK/送达，当前无可靠 accepted 判定，保持 unconfirmed。完整安全链与最小取证见 [MESSAGE_SEND](MESSAGE_SEND.md)。

## 2026-10-16 低频采集与人工接管

新增默认关闭的账号低频调度（最短 5 分钟），仍只采会话末条，不是完整历史游标。持久去重、失败退避、暂停/接管、管理员有限 FAQ 策略存储与 API/UI/MCP 详见 [MESSAGE_OBSERVATION](MESSAGE_OBSERVATION.md)。发送策略不可执行，autonomous_reply=false。本节优先于下方历史“后台采集未实现”描述。用户报告基线 4d5db8e 已部署采集 43 条/32 文本、CI 五项绿；本增量未部署、未真实验收，历史审查记录保留。

## 审查状态与安全失败码

精确快照 da3e2ad 独立审查 FAIL，不能上线；433a1be 的 ID/text 增量及后续修复仍待独立复审。本地测试不代替上线审批。

同步失败仅允许明确列出的稳定错误码持久化与返回。response_limit、page_redirected、cid_mismatch 保留原码；未知码统一 collection_failed。HTTP 使用固定失败提示，不传播异常 message，旧密文记录和 fetched_at 保持不变；last_sync 标 failed，不以旧缓存冒充成功。

## 编码证据增量（2026-10-15，优先于下方历史契约）

父助手新增 message-id-observation / message-encoding-observation 脱敏证据：messageId 为 17 字符 `DDDDDDDDDDDDD.AAA`，旧纯数字约束不兼容，已修复。ID 原样保留，不拆点、不剥后缀；允许 ASCII 字母/数字/点，首字符字母或数字，最多 128，拒绝控制/空白/路径字符。该白名单只是已观察字符集，不声称所有平台格式已知。

普通文本唯一解码路径：外层整数 contentType=101、custom.type=1；严格 base64→UTF-8→JSON，内层整数 contentType=1，text.text 非空字符串最多 4000 字符。编码最多 24000 字符、解码最多 18000 bytes、深度 12、节点 2000；拒重复 JSON 键、控制字符、类型不一致。未知或无效正文保留元数据但 body unavailable。type14/tip、summary/degrade/reminder 绝不当正文，不解压，不持久化原始 custom。可读正文仍在 Fernet 私有 payload，不写日志/审计。

createAt 仅接受已观察的 13 位整数毫秒，秒值不猜单位转换。同记录 cid 校验不变；pairFirst/pairSecond 必须为两个不同成员，当前 UID 和 sender 都在其中才能 recipient_verified=true，peer_uid 为另一方。缺失或不匹配不认证收件人。该结论不是发送授权。

### 按需本地回复草稿（不是自动客服）

用户从缓存明确选择 sample_id（账号 HMAC）后，POST `/api/accounts/{account_id}/messages/{sample_id}/reply-draft` 或 MCP `message_reply_draft(account_id,sample_id)`。仅 incoming、可读普通文本、已核验 peer=sender、账号未暂停、最近成功样本且一小时内；失败采集/旧缓存拒绝。

本版生成 **local_template** 保守确认草稿，不调用外部模型，不外传聊天，既不复制聊天指令也不承诺商品事实。交易/投诉/隐私/指令关键词与长数字等保守拦截交人工（不是完备分类器）。API/UI 明示 draft、requires_approval=true、sent=false；同账号同样本幂等保存，v7→v8 新建加密 message_reply_drafts 表。恢复只恢复本地草稿，不创建/重放 actions。UI 用 textContent 显示正文与建议；自己的消息和不可读正文无生成按钮。

**CDP 写操作与发送提案仍拒绝，草稿未进入发送队列，不声称已审批或发送。** message_bodies/message_reply_drafts=true 仅代表该受限实现；message_sample_propose=false，自动监听/FAQ 未启用。真实账号验证仍由父助手执行，本轮仅隔离假数据。下方“正文全部不可用”为旧批次状态，现由本增量替代。

## 首批历史契约

2026-10-15，基线 b0e84fe。`partial_messages=true`，不是历史消息同步、分页或实时监听。

## 采集契约

管理员绑定的 CDP 账号，复用端点校验、独立任务页、账号 UID 前后检查、取消清理。仅导航自己的任务页到固定 `https://www.goofish.com/im`；不选择会话，不点击新建/发送/已读，不发 IM 协议、ACK 或心跳。页面自身自动读取及遥测不等于工作台主动平台写入。已有页和浏览器不关闭、不导航、不注入 Cookie。

仅接收固定 `wss://wss-goofish.dingtalk.com/`（可显式 443）的 server text frames。导航后观察 8 秒，最多 64 帧排队、256 帧处理、每帧 1 MB、JSON 深度 20/节点 20000、100 条归一化消息。只解析 `code=200` 的 `body.userConvs[*].singleChatUserConversation.lastMessage.message`。无 lastMessage 的会话跳过；无任何 userConvs 响应超时报错；收到合法空样本可以返回空，但不清旧缓存。页面实际自动返回多段会话样本不被称为完整分页。

验证 messageId、createAt（毫秒整数）、sender.uid、message.cid 与同记录会话 cid 相等。数字字符串 ID 可带平台 `@goofish` 后缀（messageId 本身要求数字字符串），未知格式 fail closed；缺失不造 ID。按账号/cid/messageId HMAC 去重，冲突拒绝。自己消息标 outgoing，不自动处理。

## 正文与客服限制

本批只交付元数据：`body=null`、`body_status=unavailable`、`recipient_verified=false`。不保存 custom、summary、reminder、原始帧、姓名/头像、token/cookie 或会话扩展。固定上游 core/ws.py 证明某些路径使用 base64 JSON，但现有父助手证据没有展开此处 custom；本实现不试探解压或猜正文。无解压资源风险，无上游模块导入 API 进程。

末条样本 UI 无回复/提案按钮；CDP 真实账号 message.send propose 返回 `recipient_unverified`。原非 CDP 既有会话/人工审批链路保留；本功能不生成未知 cid，不扩展发送权限。自动客服、后台采集、FAQ 均未开放。

父助手下一次只读取证需求（开发者不得自行接入）：同记录 content.contentType/custom.type/custom.data 的字段类型与编码测试结论；若 base64(JSON) 成立，提供虚构替换后的 payload 结构和 contentType/text.text 路径，不提供真实正文。还需 pairFirst/pairSecond 与当前 UID、sender.uid 的规范形式、单聊双方匹配断言（只回传脱敏结构/布尔结论），及 messageId 字符格式/时间单位。没有这些证据不开放样本草稿提案。

## HTTP / MCP / UI

- GET `/api/accounts/{account_id}/messages`：缓存、最后采集状态与 fetched_at；最多 500 条。
- POST `/api/accounts/{account_id}/messages/sync`：按需采集，无 URL/脚本/分页参数。
- MCP `sync_message_sample(account_id)`、`cached_messages(account_id)`；仅 Agent 令牌。
- “本人只读部分样本”页显示末条元数据、方向、正文不可用。不是实时聊天页。

失败状态与旧缓存分离：失败请求返回错误，不以旧记录冒充本次成功。历史缓存仅作样本，不证明消息仍可回复或送达。不存在新交易/审批/管理员配置工具。

## 存储与恢复

v6→v7 显式迁移为已有加密 operation_records 增加按账号/类型/时间索引；不另存明文私有字段。升级前自动一致性备份，错误密钥拒绝。message_id/cid/sender/time 全在 Fernet payload，数据库键为账号隔离 HMAC。恢复沿用离线安全暂停、旧授权失效及不重放；缓存恢复不会调度回复。

## 验收区分

纯解析器、HTTP/缓存、真实 MCP stdio、隔离本地 HTML/TLS WebSocket/Chromium 和 UI 为开发验收。测试专用浏览器允许本地 TLS fixture，相关参数不进入生产适配器。真实闲鱼消息采集、真实正文、实际 Hermes connector **未验收**。父助手此前 orders/inventory 真实 10/20 条及 CI 38744034233 五作业成功为用户提供的基线信息，不是本批消息验收。
