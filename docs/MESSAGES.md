# 会话末条消息只读样本

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
