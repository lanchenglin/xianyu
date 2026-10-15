# 本人订单与商品单页样本

2026-10-15：代码提供受限只读 CDP → 加密缓存 → API/UI/MCP 纵向链路。真实平台尚未验收，由父助手独立完成；本地虚构 fixture 和 Chromium 网络事件测试不等于真实平台成功。

## 范围

- `partial_orders=true`：本人 `/bought` 买到订单的一页概要，不涵盖卖出订单。
- `partial_inventory=true`：本人 `/personal` 商品卡片的一页样本，不证明全状态库存。
- `order_sync=false` 保留为旧的完整订单同步能力；`full_inventory_sync=false`。消费者应查独立 partial capability。
- 无翻页、后台定时采集、交易、改价、上下架、首次联系或发布执行能力；通知/自动回复不启用。

## API / schema

管理员和 Agent 可调用（沿用工作台全账号令牌权限，不是按账号签发的令牌）：

| 方法 | 路径 | 内容 |
|---|---|---|
| POST | `/api/accounts/{account_id}/orders/sync` | 按需采集买到订单一页 |
| GET | `/api/accounts/{account_id}/orders` | 本账号私有缓存及 last_sync |
| POST | `/api/accounts/{account_id}/inventory/sync` | 按需采集本人商品一页 |
| GET | `/api/accounts/{account_id}/inventory` | 本账号商品样本缓存及 last_sync |

无需请求体；不接受可执行 URL/JS/分页参数。`/api/schema` 展示四条路由。真实采集须 live 开关开启、账号未暂停、管理员 CDP 固定绑定匹配，并通过现有限流/操作锁。演示账号返回明确 demo 样例，不连接平台。

POST 返回 `items/source/fetched_at/demo/partial/completion/has_more/cursor_error/reported_total`。`partial` 永远 true，`completion=single_page`，不能读成完整。

- 订单 `nextPage` 仅有字符串类型证据，无实际合法值语义；字符串记 `pagination_semantics_unknown`，错误类型记 `pagination_type_invalid`，`has_more=null`。不保存 lastEndRow 的原始值；校验其字符串类型。保留可验证单页字段，但不翻页、不宣称结束。
- 商品仅 bool `nextPage` 可得到 `has_more`；未知类型记 `pagination_type_invalid`。false 也不证明全状态库存。无效 totalCount 也记录分页类型错误。
- GET 为 `completion=cached_samples`，最多显示最近更新 500 条；记录来源与各自 fetched_at。`last_sync` 是最后尝试，包括失败；缓存不代表本次成功。没有记录不证明平台没有商品/订单。

白名单订单字段：`order_id/item_id/status/created_at/status_text`，均保留来源文本，不猜时间格式或枚举语义。商品字段：`item_id/status/price/title`，状态数字不猜在售/已售含义，price 是平台显示文本，不作为可执行金额。无买家/卖家昵称、地址、电话、peer uid、图片或原始嵌套数据。

## 浏览器边界

bridge 对 orders/inventory 直接使用项目 adapter，不导入上游模块。只导航新建任务页到固定 bought/personal 页面，不导航原页、不执行 evaluate/任意 JS、不重放签名请求。通过 CDP Network 观察固定 HTTPS host/path 对应响应；不存 headers 或原始响应。

严格 MTOP SUCCESS ret、字段类型、最多 100 条、响应体最多 1,000,000 bytes；浏览器资源缓存同样有界，最多 16 个待处理/队列事件。采集导航和响应总窗口 25 秒，外围仍受 Provider operation timeout 及协作取消控制。首个失败 ret/非 200/不可解析响应不会伪成功；只等待页面自身后续响应，不自动发送重试请求。合法空列表可返回部分空样本，不能删除旧数据。

UID 前后校验沿用 task_page；inventory 额外要求成功 head 响应 `data.baseInfo.self is True`。身份不符立即失败。只关闭自建任务页/连接，不关闭借用 context/browser；异常、取消仍清理。浏览器用户并发切换账号不是事务隔离，验收时不要手动并发操作。

## SQLite v6

显式 v5→v6 迁移（升级前既有一致性备份/锁/失败回滚不变）：

- `operation_records`：account_id + kind + HMAC record_key 复合主键；整个白名单概要 Fernet 加密（含订单/商品 ID），source/fetched_at 可审计。HMAC 使用 vault key 及账号/kind/ID 作输入，防止明文订单 ID 索引泄漏。
- `operation_syncs`：账号、kind、source、fetched_at、state、partial、completion、cursor_error、error、item_count、has_more、reported_total。失败只记受限错误码，不记异常正文。
- 同一页原子 upsert + 审计，不清空旧记录；稳定 ID 重复幂等，跨账号同 ID 独立。错误密钥启动校验包括新表。
- 无原始游标持久化、自动增量或自动清理。旧样本可长期保留，备份包含加密表；密钥须由管理员保管。

## MCP / UI

工具：`sync_order_sample`、`cached_orders`、`sync_inventory_sample`、`cached_inventory`，仅 account_id 参数。MCP 真实 stdio 经 Agent 角色校验，不接受管理员令牌。

UI「订单与商品样本」只在手动点击时采集；进入页面/切换账号只读缓存。状态展示部分样本、时间、分页错误/失败；跨账号异步结果不渲染到新账号，文本以 textContent 展示。无付款/退款/确认收货按钮。

## 后续取证

订单 nextPage 实际合法值与翻页触发、商品各状态集合和分页需父助手继续只读核实。userConvs 结构已证明稳定 ID 与内容容器同记录，消息编码仍未知；本批未实现消息采集或 listener，不以旧 history 的裁剪结构否定新的证据。发布类目/地点冻结仍需进一步证据。
