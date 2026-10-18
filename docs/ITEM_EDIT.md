# 管理员单条同 ID 编辑：设计与验证边界

## 已批准范围

默认关闭；仅管理员对已有在线本人商品提出并指定执行一条标题/正文/价格编辑。不能发布替代、不能改图片/配送/库存/SKU/状态，支付退款等永久人工。公开前端已证 editDetail/edit 入口；父助手同 ID 正文编辑成功，并已拦截取消实际完整请求、提供公开 shape；具体映射尚未完整交付开发端，改价未验收。此实现不得作为平台契约证据。

## 2026-10-19 新增 bounded_snapshot（默认不启用）

原 v2 `version_required` 原封保留其版本/分离字段/完整映射门槛。新 v3 必须显式 `concurrency_mode=bounded_snapshot`、`external_race_acknowledged=true`，不自动升级旧协议。仍需 XY_LIVE_ENABLED / XY_EDIT_ENABLED，均未在生产开启。以下旧 v2 章节只描述版本模式，不将其版本要求套用到 v3。

已读取父助手提供的三份脱敏公开证据：真实 Request-stage 编辑请求已拦截并取消，完整 shape 已获得，无 version/CAS，组合正文 title=desc、titleDescSeparate=false；editDetail.userId 不具有已证 seller 语义。未读取任何私有原件。shape 不是具体值映射证据，不能直接启用。

### v3 有界协议与执行

- `before={detail: <普通 detail 完整 data>, edit: <editDetail 完整 data>}`，不裁剪未知字段。`before_content_hash=digest(before)` 使用项目 typed-canonical SHA-256；**内容 hash 不是平台版本，不是 CAS**。完整类型/值精确比较，额外字段、数组顺序、空容器和 userId 都冻结，但后者不当作身份。
- `identity_paths.uid` 固定 `detail/sellerDO/sellerId`，`item_id` 固定 `detail/itemDO/itemId`；edit_item_id 为已证 edit 商品路径。只接受严格字符串/整数 ID，比较后仍保留原类型，回读必须原类型全等。
- `status_path` 必须明确指向普通 detail 已取证状态（非空字符串或严格整数），与身份/内容路径不重叠；原状态逐类型冻结，不以猜测 ONLINE 枚举代替证据。
- `before_values` 为原 item_id/title/desc/两位小数元价格。`content_mappings` 只允许对象路径和 field=title/desc/price；编码仅 identity（文字）、yuan_string/cent_string（金额）。必须独立覆盖普通 detail 三项及 edit 正文/价格；互不重叠。不支持表达式、JS、任意 URL/API。
- 请求文字严格固定 `itemTextDTO={title: before.desc, desc: before.desc, titleDescSeparate:false}`，价格严格固定 `itemPriceDTO={priceInCent: 分整数字符串}`。实际提交只替换这两个正文叶子和价格；**独立改短标题尚缺转换证据，申请时拒绝任何 title 变化**。新正文仍要求普通 detail 短标题保持原值；若平台改变它，则 unknown，不能猜截断后宣称 verified。
- `original_request == template` 全等。其余请求叶子须 `invariant_mappings` 从完整 edit 快照逐类型精确映射；图片目前仅完整数组精确相等（有限 identity），不推导/补默认图片字段，不支持缺证的数组转换。变化内容不能成为固定字段来源。
- 例外仅 `fixed_constants` 中逐字冻结的 sourceId/bizcode/publishScene（后两者须 pcMainPublish）；sourceId 具体值仍须管理员取证。unique_code_mode 必须 timestamp_random，原始 uniqueCode 保留，申请时按毫秒拼接0～999整数生成一次并冻结到 action/digest；同账号历史碰撞在申请事务内拒绝，不自动重抽。它不是版本、幂等或 CAS 保证。
- `api_version/detail_api_version` 分别绑定固定 editDetail/edit 与普通 detail；三个精确 success ret 独立冻结。双读完整 before 匹配→构造→再次双读完整匹配→重验授权→持久化提交阶段→单次 edit→精确 ACK→双读完整 after。共享 operations.lock；提交后任何异常仍 unknown，不重试。
- 三层未知阻断保留：保存协议、新申请的 IMMEDIATE 事务及执行历史检查。verified 后允许新 revision / 完整新 before（必须等于最近 after）及逐条重新审批；不要求伪造新版本，执行前两轮双读都必须匹配。SQL schema 仍 v13，恢复删除协议、撤销旧审批。

### 显式 observational_projection（2026-10-19）

父助手同目标两轮只读证据仅观察到以下三条值变化，editDetail 完全相同。v3 默认 `comparison_mode=full_snapshot`、`observational_fields=[]`，旧协议不自动切换。管理员可在协议 JSON 显式选择 `comparison_mode=observational_projection`，并选择以下非空、无重复枚举子集：

| observational_fields 枚举 | 原始响应路径 | 严格类型 |
|---|---|---|
| browse_count | detail.data.itemDO.browseCnt | int（不含 bool） |
| server_time | detail.data.serverTime | str |
| commerce_subtitle | detail.data.commerceDO.idleItemDetailFloatInfo.subTitleTextInfo.text | str |

路径内置，不接受自定义路径、通配符、父层删除或自动发现易变字段。协议快照中的 `detail` 已是 response.data，不再嵌套 data。每次比较均先验证选中叶子存在及严格类型，再仅在副本归一化其值；所有父对象、兄弟叶子、数组、editDetail 仍完整精确比较。任何选中路径与身份/内容/金额/状态/请求不变量源路径相等或祖先/后代重叠，一律拒绝配置。原请求映射门槛不变。

选择进入协议 revision、action payload/digest；模式或选择变化需要新申请审批。保存协议与提案事务内、执行历史检查、提交前两轮双读、after 均使用同一投影规则。涉及投影的 verified 后续 before 必须同时通过新旧两份契约与上次 after 比较，不允许通过扩大排除范围掩盖历史差异；新 before 仍是完整原始数据，并与当前两轮回读匹配。

`before_content_hash` 仍验证完整原始 before；执行结果加密保留 `preflight_snapshots` 两轮原始 data 和原始 `after`（含写后不匹配数据），另记 `before_projection_hash/after_projection_hash` 及选择。投影 hash 只用于内容一致性证据，**不是平台版本或 CAS**，不能消除外部并发窗口。未知三层阻断不变。其他真实请求映射仍待父助手，编辑默认关闭。

非管理员结果投影采用默认拒绝的字段白名单，仅公开 `stage/item_id/ownership_verified/status_verified/content_verified/verified_at/notice`。HTTP列表、详情及MCP共享此边界；完整 before/after/preflight、协议、hash、任何未来新增字段均不公开。白名单值也严格投影：阶段仅submitting/verifying/verified，ID为与动作目标匹配的1～30位ASCII数字字符串，验证结论仅bool，时间仅有限非负int/float且不含bool，notice仅现有固定不确定提示。错型、容器、未知字符串直接丢弃，不隐式str()转换。管理员完整审计不受影响。该边界经父助手复审FAIL后修复，历史失败与验证见TEST_REPORT。

### 父助手最小补充结构（不是请求私有原件）

请继续只给脱敏结构和逐字段语义证据，不给 cookie、账号或私有快照：

1. 同次普通 detail / editDetail 完整 `data` 的逐叶路径、类型及一一对应关系，尤其状态、图片完整数组、运费/配送、类目、SKU/库存和 edit 商品 ID；标明所有动态只读字段。当前全快照不提供任意忽略字段逃生口。
2. 对捕获请求每个固定叶子，提供 `request_path -> editDetail data path` 的精确类型/值转换规则。图片若补 extraInfo/status/type/templateIndex 等，请逐项列出固定默认值、源字段和触发条件；在补齐前仅 identity 可用，真实协议可能仍被拒绝。
3. sourceId/bizcode/publishScene 的已证固定常量；完整 original_request 由管理员在本机私下录入，开发者不读取。当前 shape 不能替代其值。
4. 普通 detail 的 price/status/title/desc 精确路径与金额编码，edit 的正文/价格路径；三种接口精确 success ret、版本、编辑 ACK 的 itemId 路径及类型。本实现 ACK 仍要求 data.itemId 字符串，不猜别的形状。
5. 若需独立改标题，给出组合正文与普通 detail 短标题的确定映射规则及前后实例结构；当前拒绝，不将任意预期标题当成已传输标题。

单元/HTTP/UI fixture 都是虚构证据，不可复制到生产。该路径代码已实现不等于真实协议已可启用或已平台验收。

## 原 v2 协议设计

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
