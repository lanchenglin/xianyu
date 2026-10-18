# 管理员单条同 ID 编辑：设计与验证边界

## 已批准范围

默认关闭；仅管理员对已有在线本人商品提出并指定执行一条标题/正文/价格编辑。不能发布替代、不能改图片/配送/库存/SKU/状态，支付退款等永久人工。公开前端已证 editDetail/edit 入口；父助手同 ID 正文编辑成功，完整请求未采集、改价未验收。此实现不得作为平台契约证据。

## 协议设计

不内置完整 payload 或猜字段。管理员为一个 UID/itemId 录入完整原值模板、证据说明、显式接口版本、精确成功 ret、请求文字/价格字段路径及只读响应语义映射。仅对象键路径，不执行表达式。原值快照包含同 ID、UID、版本、状态、标题、正文、价格以及完整不变量（图片/配送/类目/SKU等由管理员完整取证）；缺字段拒绝。价格单位显式声明为元字符串或分整数字符串，不做模糊比较。仅支持分离标题/正文语义，网页组合文字等未覆盖结构拒绝而非猜测。

审查 FAIL 后协议升级为 v2：必填 `original_request`（取证原始完整请求），与 `template` 递归类型/值全等；每个非文字/价格叶子须由 `invariant_mappings` 明确列出 `request_path/before_path/evidence`，映射只能来自冻结身份、版本、状态或不变量。数组按完整对象递归精确比较，不做索引转换；空对象/空数组也不能漏覆盖。所有请求路径必须不重叠，`itemId` 必须映射 `before.item_id`；没有映射的额外字段拒绝，重复原始模板或 `complete_semantics_confirmed` 不构成通过依据。固定元数据免映射白名单当前为空（没有取证支持的例外），不接受未知常量、命令或状态字段。执行前真实回读必须精确等于整个 before；实际提交构造后再还原三个批准叶子，与原始请求递归比较，确保其余内容没有变化。管理员证据仍需真实取证，不是平台验收。协议摘要、凭据指纹、UID、同 ID、新旧值、版本全部进入已有 actions 加密 payload/digest。协议变化必须重新申请。Agent 不可配置/申请/执行，不可读取原始协议或回读数据。

## 执行与持久化

复用 actions、settings、operations.lock，无第二队列；settings 中协议使用 schema_version=2（v1 缺完整映射，拒绝执行，不自动迁移授权），不新增 SQL 列，不提升数据库 v13。恢复删除编辑协议并沿用旧 actions 撤销机制，需重新取证配置审批。worker 不领取 item.edit（含 demo）。管理员批准与指定 execute 沿用已有权限校验。

独立同 UID Cookie HTTP 子进程，只固定 editDetail/edit，无 URL/方法注入，无上传、无浏览器、无发布兜底。执行前只读 editDetail 精确比较所有冻结语义及版本；暂停/接管/开关/凭据/协议/摘要/期限再次核验。写前持久化阶段；仅一次 edit；精确 ACK 同 ID 后 editDetail 回读内容、金额、状态、归属及不变量。版本必须存在但可改变。任一写后异常或回读不符为 unconfirmed，禁止自动重试。

这是先读后写比较，不是平台原子 CAS：读写间外部并发窗口仍存在；若需要平台级版本条件写必须进一步采证，不能把本地比较称为平台并发保护。

## 严格 JSON 边界（第二轮复审修复）

所有 API 原始 JSON body（含 application/*+json 和无 Content-Type 的框架 JSON 路径）在解析为对象前拒绝 NaN、Infinity、-Infinity、浮点溢出及任何层级重复键，固定脱敏400；实际流式读取最多12MB。multipart/form、静态资源和无body GET保持原契约。复用已有消息严格解析规则；嵌套 cookies_json、CLI JSON文件、备份manifest、子进程、外部样本及持久化JSON读取使用共用strict_json。canonical设置allow_nan=False，加密持久化兜底；历史坏数据报错，不静默重写。规范字符串里的普通“NaN”不是数值，不禁止正文文字。UI JSON编辑器本地解析后的对象仍由服务器复验；原始HTTP重复键不能靠对象复验发现。

## 接口和授权

管理员 PUT /api/accounts/{id}/edit-protocol，POST /api/item-edit（标准 ActionIn，kind=item.edit）。之后使用既有逐条批准、指定 execute。Agent 只读脱敏动作结论/能力声明；MCP 不新增配置或执行工具。

## 验证

确定成功的动作加密持久化完整 `after` 和 `verified_at`，Agent 不可读取 after。后续正常编辑必须新协议 revision、新 before 版本、全新逐条审批；before 必须精确等于最近 verified after，并再次与执行前平台回读全等。旧 action/旧 revision/旧 before 不可复用。协议保存和新提案创建均在各自 `BEGIN IMMEDIATE` 写事务内重新检查同账号同商品历史；running/unknown 拒绝，settings revision 和 pending 数量不变。提案还在插入事务内重新核对当前协议，防止准备后协议被并发替换。相同幂等键读取已有动作不是新增申请；执行层历史检查继续保留。历史提交记录仅当 state=submitted、stage=verified、三项验证全 true 且 after/时间完整才视为确定成功；任何超时/崩溃/ACK或回读失败/旧记录缺证明继续锁止，新键、重录协议、人工核对和恢复均不解除。明确提交前失败没有写入阶段，不妨碍重新申请。并发操作在共享锁内检查历史，两个同版本审批最多一次写入；若版本回读未变化，该次可 verified，但无法满足下一次编辑所需的新版本。

协议 `before` 必须精确含 `item_id/uid/version/status/title/desc/price/invariants`，`response_paths` 对应这八项独立对象键路径；`request_paths` 只允许 `title/desc/price` 三项互不重叠的既有叶子路径。`template.itemId` 为原商品字符串 ID；`before.item_id/uid` 及响应要求同类型字符串，不自动将平台整数归一。`before.price` 和新 `price` 均为两位小数元字符串，`price_encoding` 明确为 `yuan_string` 或 `cent_string`；不支持 SKU 改价或组合正文映射。平台响应没有完整独立不变量对象、稳定版本或兼容字段形状时，当前协议不能启用，须进一步独立适配及测试。管理员声明 `complete_semantics_confirmed=true` 必须基于完整原值请求与响应取证，含原商品在线、所有固定字段无额外写入含义；不能用本地 fixture 填充证据。

`api_version` 是管理员取证值，固定用于 editDetail/edit（不同版本组合暂不支持）；`success_ret/read_success_ret` 必须分别精确匹配。本地配置不发起只读探测，执行前才读取；没有平台原子 CAS 保证。协议不含 URL、HTTP 方法、脚本、任意 API 名字段。单次提交后不会更新商品历史缓存为当前真实快照，动作结果为该次回读证据。

所有协议样本为虚构；独立临时数据，项目 .venv，env -u PYTHONPATH，专用 Chromium。真实工作台编辑/改价未验收，生产开关/协议未配置。测试结果见 TEST_REPORT。
