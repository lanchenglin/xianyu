# 站内通知与外部摘要通知

默认仅站内通知。管理员可在设置页配置钉钉机器人或受限通用 HTTPS webhook；不需要修改环境或 Hermes 配置。不读取其他项目密钥。运行 worker 才会投递；worker=false 可配置和查询但不发送。配置启用即授权向所填目的地发送**之后产生的新通知**，包括演示监控提醒；不补发历史。

## 接口与权限

- GET `/api/notifications?include_archived=true`：最多 100 条；默认隐藏归档。
- POST `/api/notifications/{id}/state`：完整 `{read: true, archived: false}`，管理员/Agent 可用，本地幂等更新，无平台操作。
- GET/PUT `/api/notifications/config`：仅管理员。PUT 完整填写 `kind`（webhook/dingtalk）、`url`、`secret`（32～256 字符）、`enabled`（默认 false）。GET 仅返回 configured/enabled/kind，不回显 URL 或密钥。配置加密保存。
- POST `/api/notifications/disable`：仅管理员，无需重新提供密钥；取消 pending/retry，不能撤回在途请求。
- GET `/api/notifications/deliveries`：管理员/Agent 可读最近 100 条编号、状态、次数、时间和固定错误码，无目的地和内容。

设置页提供完整配置、关闭按钮和投递记录。站内 UI 支持已读/归档，恢复归档可通过 HTTP/MCP。MCP 仅新增 `notification_state` / `notification_deliveries`；`notifications` 可读归档，不提供配置或任意发送工具。

## 目的地和数据

只接受 HTTPS 443、ASCII DNS 域名；拒绝 URL 用户凭据、fragment、IP 字面量、私有/loopback/link-local/multicast DNS 结果。通用 webhook 不允许查询参数；钉钉只允许 `https://oapi.dingtalk.com/robot/send?access_token=...`。每次投递重新解析，所有答案必须公网，连接固定验证后的数字 IP，TLS SNI/证书仍验证原域名。系统 DNS 最多等待 5 秒，最多一个未完成解析线程；不使用环境代理、不跟随重定向。连接/读超时 5 秒，传输另有 15 秒期限，响应最多 64 KiB。管理员仍须确认域名归属；公网目标可看到本机出口 IP。

导出内容只有固定文字“闲鱼工作台有新通知，请在工作台查看。”、事件类型和本地通知编号；不导出搜索词/结果、账号标签/uid、聊天、价格或地址。

通用 webhook 为 canonical UTF-8 JSON，头 `X-Delivery-ID` 稳定，`X-Timestamp` 为毫秒，`X-Signature-SHA256` 为十六进制 HMAC-SHA256(secret, timestamp + LF + 原始 body)。接收方应验证签名/时间窗，并以 delivery ID 去重。接受 HTTP 2xx 为接收成功，不代表人已读。钉钉按 timestamp + LF + secret 签名，URL 编码 Base64 sign；仅 errcode=0 判为成功。钉钉通知编号可辅助人工去重，不承诺钉钉端 exactly-once。

## 持久化和故障

schema v4 为旧通知加 archived=0；v5 新增 notification_deliveries，notification_id 唯一。不修改旧通知正文/已读状态。现有迁移备份/事务保护继续适用。

同一 worker 串行处理，每轮最多一条；最多三次，失败后 60/120 秒退避。错误只记录 delivery_failed，不保存原异常/响应/URL。超时可能已被接收，重试可能重复通知，不能宣称 exactly-once。进程中断 sending 变 unknown，不自动重放。配置变更/关闭取消未发项并跳过历史；备份恢复关闭通知并取消旧任务，sending 变 unknown。

通知队列与平台审批队列分开，**只重试通知，绝不重试业务操作**；它不是绕过审批的聊天通道。全部平台写仍逐条人工审批，无人值守 FAQ 未开放。

## 搜索样本价格历史与降价提醒

schema v11 新增 price_samples，仅现有监控成功搜索后观察，不额外抓取平台。按账号+监控+item_id 隔离；严格正数十进制、最多两位小数，不解析带货币符号/范围/NaN/布尔值。fetched_at 必须在当前时间前300秒内，同监控重复/倒序时间不录入。两次相邻有效观察间隔须不超过 `min(86400, interval_s*2)` 才可判断下降；缺失、重复冲突或非法价格写空观察、打断连续性，不把缺失当0或售罄。每监控最多1000条，查询最多200条，不是全平台历史。

GET `/api/accounts/{account_id}/price-history?monitor_id=...`；UI 监控卡“价格样本历史”、MCP `search_price_history`。降价只写站内通知，外部仍只发送固定摘要；不创建 action，不改价，不联系卖家。没有补发历史通知或业务重试。

## 验证范围

真实临时 TLS 服务接收端验证连接、主机名证书、签名、摘要和持久状态；仅测试边界将已验证公网地址路由到随机 loopback 端口并信任临时证书。生产无放宽开关。没有向外部服务发送，本轮钉钉及真实 webhook 未验收。测试见 tests/test_notification_transport.py、test_external_notifications.py、test_notifications.py 和 test_mcp_stdio.py。
