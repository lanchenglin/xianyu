# 运营能力续开发矩阵与执行断点

日期：2026-10-15；起点 feat/local-next / 121f3c8。本轮不接触 .env/data、8099、9235 或真实平台；不升级固定上游，不部署、不 push。500 轮为工作上限而非验收指标；批次完成不等于全部需求完成。

## 消息编码与本地草稿增量（最新）

基线 da3e2ad。父助手新增证据已纠正 messageId 纯数字假设：按有界 opaque 字符串原样保存；普通 101/custom1→base64 JSON1/text.text 解码，type14/tip 不作正文。pair 当前 UID/sender 双成员校验，私有正文加密，不记录 raw custom。用户选择 incoming 可读样本后 HTTP/UI/MCP 生成 local_template 草稿，v8 加密表；不调模型、不提案、不发送，CDP 写入仍拒绝。旧缓存/失败采集/过期/自己消息拒绝草稿。见 [MESSAGES](MESSAGES.md)。

实际平台验收交父助手；本批测试全为临时假数据。分页、实时监听、FAQ 管理员授权、发送支持、首次联系、发布/改价上下架和 Hermes 实际接入仍未完成。

## 第三批：消息元数据样本（历史）

基线 b0e84fe；已实现真实 CDP 被动 WS 采集器、严格末条元数据归一化、账号 HMAC 加密缓存、HTTP/UI/MCP 与 v7 索引迁移，见 [MESSAGES](MESSAGES.md)。正文不可用，收件人未验证，禁止样本回复提案；没有将编码未知当作元数据采集阻塞。只读结构证据来自父助手，本批不接真实账号，不部署/push。实际消息采集未验收；需要父助手补充的具体编码/收件人字段见消息契约。

下一断点：验证 custom 编码与单聊双方对应后，按需选择可读消息→建议→原人工审批；当前无可读消息，本批不伪造草稿链路。分页、后台监听、无人值守授权策略、首次聊天、发布冻结、改价/上下架及实际 Hermes 接入仍未完成。

## 第二批状态（历史，优先于更早矩阵）

基线 465f898；父助手已授权取得 bought/personal/im/publish 结构证据，不再以旧上游缺接口结束。订单及本人商品单页纵向实现见 [OPERATIONS_SAMPLES](OPERATIONS_SAMPLES.md)：受限 CDP 网络监听、UID 前后与 head.self、最小字段、v6 加密缓存、按账号 API/UI/MCP；partial_orders/partial_inventory 可用，完整同步仍 false。订单字符串 nextPage 没有值语义，保留可验证样本并记录分页错误，不猜游标。

userConvs 已证明 messageId/createAt/content/sender.uid/cid 与会话 cid 同记录；旧文档“稳定 ID 待取证”仅为历史断点，不能否定新证据。正文编码尚未证明，本批未实现消息解析器/采集/增量 listener。下一独立单元从虚构结构 fixture 的纯解析器开始，再取得编码证据后接只读样本。首次联系、发布冻结、改价/上下架、交易仍未开放；自动回复及外部通知默认关闭。

真实平台验收留给父助手；开发只用临时数据、随机本地端口和隔离 Chromium。日志位于绝对 `/home/lan/.hermes/cache/scratch/xianyu-operations2-evidence`，不写 repo scratch；无 push/部署/运行配置变更。

## 任务矩阵与依赖（第一批历史）

| 能力 | 当前/可实现性 | 下一验收门槛 |
|---|---|---|
| 既有搜索、审批、草稿、人工核对、浏览器隔离 | 已实现；本轮保留回归 | CDP 仍仅 search，账号 uid/所有权/取消保护不变 |
| 真实发布冻结 | 可用底层 builder 构造，但需真实页面/响应核实 | category.recommend 需要先上传图片；预览不得暗中上传。管理员地区快照加密、模型仅地区摘要；执行前默认地点比较；图片 hash/配送/类目绑定 digest；可靠发布结果与本人详情核对前 live_publish=false |
| 首次联系 | create_chat 有请求入口；响应契约待核实 | 用请求 mid 关联真实响应 cid，校验商品卖家；未知结果不发送、不重发 |
| 全量本人库存 | 需真实页面核实分页及状态 | 本人 uid、item_id、状态、next cursor、明确末页；部分结果不能清空历史 |
| 改价/上下架 | 依赖本人库存/详情和真实操作语义 | Decimal、旧值并发检查、同一商品 ID 状态转移、统一审批与事后只读核对；delete/recreate 禁止替代 |
| 消息低频采集 | 底层 listUserMessages 已有分页；稳定 ID 字段待取证 | 有界分页、sender/cid/item/id/time 同记录关联、持久游标去重、忽略自己；不可正文 hash 伪装平台 ID |
| 无人值守 FAQ | 未实现、默认关闭 | 独立管理员授权设计：商品白名单、确定话术、期限、速率、接管、撤销；仍用统一队列；投诉/退款/交易/站外付款/预算人工 |
| 本人订单只读 | 需真实页面核实 | 只保存订单 ID/状态/商品/更新时间，分页部分结果、失败保留旧值；不采电话地址，无交易写路径 |
| 站内通知已读/归档 | 可直接实现 | HTTP/schema/UI/MCP，幂等、不删除原通知、独立测试 |
| 外部通知 | 可直接实现 | 默认关闭、管理员配置、固定摘要、HTTPS 公网 IP 固定连接/禁止重定向、签名、超时、有限重试与投递日志；隔离接收端验证 |
| Hermes MCP | 现有 stdio 代理；需真协议测试 | 临时随机端口演示 API + MCP 子进程 initialize/list/call、Agent 正常/Admin 拒绝、固定目标，无真实 connector 配置修改 |

## 本批实现方案与 TDD 执行顺序

1. `tests/test_notifications.py`：先测已读/归档路由不存在的 RED；db 显式 v4 迁移保存 archived，HTTP 本地状态更新，UI/MCP 联动后 GREEN。旧通知保留，归档不涉及平台。
2. `xianyu_workbench/notifications.py`：独立配置/传输/投递服务；`tests/test_external_notifications.py` 分组先 RED，再实现 URL 拒绝、IP 固定、签名、配置加密与管理员权限、唯一 outbox、退避重试和重启恢复。集成现有单 worker，不增加抢账号后台。
3. 配置修改使未发送旧配置任务取消，不把历史通知全量补发到新目的地。仅新通知入队。一次调用只处理一个任务，最多三次；未知投递可能重复，接收方用稳定 delivery ID 去重。业务操作绝不重试。
4. `tests/test_mcp_stdio.py` 使用真实 SDK stdio 客户端与临时 Uvicorn。新增工具发现/调用与角色拒绝，禁止任意 URL/脚本/凭据工具。适用新增行为必须记录 RED；既有能力首次即通过如实记集成验收。
5. 每个可验收提交明确文件列表，更新 TEST_REPORT / DEVELOPMENT_HANDOFF 的短增量与相应文档；双 Python、ruff、pip check、独立 Chromium UI。证据写 scratch/xianyu-operations-evidence，不提交运行日志。

## Hermes 只读取证清单（需要主人单独授权，开发者本轮不执行）

- 本人发布编辑页：类目 ID/名称/channelCatId/tbCatId、地区字段来源与默认地点变更、运费选项；只读取，不上传、不提交。完整地址不回传模型。
- 本人商品管理页：在售/下架/已售分页及末页标志、本人 uid、商品 ID、价格状态与更新时间；上下架按钮文案及确认对话框语义，不点击确认。
- 已有本人聊天页：一条脱敏历史消息的稳定 ID、cid、sender uid、item_id、timestamp、分页 cursor；创建会话响应需另行写授权，不用只读许可暗中创建。
- 本人订单列表：分页标志、订单 ID、商品 ID、状态、更新时间；不要提供姓名电话详细地址或任何支付凭据。

推荐项目内白名单 adapter，而非第二运营后台。暂不需要 fork/升级固定依赖；若取证证实必须升级，再单独提出具体 commit、license 与迁移验收供 Hermes 决策。
