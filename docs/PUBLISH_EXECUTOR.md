# 受控单条发布执行器（2026-10-16）

## 已实现与证据范围

实现了真实传输代码，不是 candidate DTO：固定 Cookie 上传 → 显式完整 payload 调用 `mtop.idle.pc.idleitem.publish` v1.0 → 按 ACK itemId 调用 `mtop.taobao.idle.pc.detail` v1.0，核验独立精确 ret、同 itemId / seller UID 及管理员取证冻结的状态契约。独立子进程内加载固定上游 Session/mtop；不调用旧 publish、类目推荐或默认地点，不使用浏览器、不读取浏览器 Cookie、不触原页。旧 Provider `item.publish` 阻断仍在。

**默认关闭，未真实平台验收。** `XY_LIVE_ENABLED=true` 与 `XY_PUBLISH_ENABLED=true` 同时开启才可执行。capabilities 的 `publish_policy.executor_implemented=true`，`live_executor_enabled` 与顶层 `live_publish` 均等于两个开关的逻辑与，表示运行启用而不是账号授权或平台验收；`platform_verified=false`、`publish_complete_snapshot=false` 继续明确未做真实验收。默认或仅单个开关开启时运行启用为 false。这不是普通重新上架，不修改旧商品。通过状态核验仅表示命中了管理员已取证的允许值（可能含审核中），不必然等于在售，亦不证明价格/内容完全一致。

## 管理员单条流程

1. 独立导入本人 Cookie（UID 必须匹配），不从 CDP 导出。先保存本地图片和草稿、类目/地点 defaults。
2. `PUT /api/accounts/{id}/publish-protocol`（仅管理员，UI 商品页提供 JSON 表单）保存：
   - `template`: 经父助手核验的**完整发布请求 data 对象**。`imageInfoDOList` 必须为空数组占位；`uniqueCode` 必须显式提供，执行器不生成、不重算，也不假定它有幂等语义。
   - `success_ret`: 已证精确成功 ret 字符串数组，元素须以 `SUCCESS::` 开头；运行时必须精确相等。
   - `readback_success_ret`: **独立**的详情回读精确成功 ret 数组，必填；不默认继承发布 ret，不接受仅 SUCCESS 前缀相同。运行时整个数组（包括顺序）必须相等。
   - `readback_status`: 必填的已取证状态契约：`path` 是从完整回读 JSON 根开始的对象键数组；`value_type` 为 `string` 或 `integer`；`allowed_values` 是该类型的审核中/在售允许值列表。严格类型，不把字符串数字、浮点或 bool 当整数；空路径/空允许值或类型不一致拒绝。字段路径和状态值没有平台默认值，不猜取值。当前仅支持对象键路径和字符串/整数；若真实证据不是此结构，保持关闭。
   - `evidence`: 管理员证据说明（10–2000 字），应覆盖独立 ret 和状态字段语义/允许值的取证来源；不得填 Cookie/密钥。
   - `upload_authorized: true`: 明确这次队列执行包含每个冻结素材的一次外部上传，以及一次发布。
3. `POST /api/publish-preview` 使用新 idempotency_key。已有协议时把完整模板、协议 revision、独立凭据 fingerprint/UID 与原 defaults/素材 hash 一并冻结到加密 action。相同幂等键只返回旧 action，不重新授权。
4. 管理员查看完整 action，approve 后仅 `POST /api/actions/{id}/execute`，digest + `confirm: "确认执行"`。worker 永不领取 live action。Agent/MCP 没有协议设置、approve、execute 权限。
5. 检查执行阶段与结果；**unknown 对应现有 `unconfirmed` 状态**，不得自动重试、更换幂等键绕过人工核对。即便上传失败，图片可能已写入 CDN。恢复/启动时 running 变不确定，保留已保存的 result 阶段。

旧协议缺少 readback_success_ret 或 readback_status 时，执行前明确拒绝，必须管理员补证后重新保存协议、预览及审批；不为历史 approved 自动补默认值。以上字段随完整协议进入加密 payload/digest，任一变更阻断旧审批。回读 ret 不匹配、状态缺失/未知/类型错误一律停在 verifying/unconfirmed，不重传、不重复提交，不设置 status_verified。结果不保存或向 Agent 暴露原始状态字段值。

模板中的 itemTextDTO/itemPriceDTO/itemPostFeeDTO/itemAddrDTO/顶层 onlyTakeSelf 必须与草稿 candidate 的 canonical JSON 完全相等（包括类型；数字 0/1/1.0 不能替代布尔 false/true）；itemCatDTO 必须包含且匹配四个基本类目字段，附加层级字段冻结原样保留。其他模板字段也全部冻结并直接发送，管理员必须核验其含义；执行器不是平台 schema 验证器。模板会绑定具体草稿，不是任意商品可复用的默认值。

图片转换沿固定上游：extraInfo 三项字符串 false、isQrCode=false、major=true、type=0、status=done，按冻结素材顺序填 url/heightSize/widthSize。该源码映射尚需平台证据（尤其多图 major）。当前 URL 仅接受 HTTPS alicdn.com 或其子域，正整数宽高；其他域返回停止，不猜着放宽。

## 持久化与隔离

- 发布自身不新增 schema，沿用加密 settings / actions.payload / actions.result；当前离线运营迁移为 v12。
- 在统一 operations.lock 下串行执行全部阶段。action 原子 approved→running 防并发/双击。
- 第一次外部写前保存 prepared，每张上传前 uploading，上传后保存素材 ID/hash/URL/宽高，提交前 submitting + 请求 digest，成功 ACK 后 verifying + itemId，回读成功 verified。
- 每个阶段重新核验开关、暂停、时效、模式、凭据、图片、defaults/protocol revision；回读后再次核验身份。上传子进程对读取到内存的实际字节核 hash 后上传同一份字节。
- HTTP 禁止重定向（含 307 POST 重放），mtop `_auto_refresh=False`，不自动刷新登录态或重试。传输异常/格式不明/错误 ret/不匹配归属均 unconfirmed。只有首次外部写前的 busy/rate_limited 可回 approved，仍需管理员再次指定。
- 上传回执仅管理员可读；Agent 不见 URL/凭据 fingerprint/完整模板/精确地点。审计不含上述私密值。
- 成功不意味着完整库存同步或自动确认在售。管理员可用既有人工核对记录附加证据，不能据此重放原 action。

## 父助手最小真实证据清单（开发端未访问真实账号）

1. **新发布最终请求 data**：itemCatDTO 的 catId/catName/channelCatId/tbCatId；root/level2/level3ChannelCatId 的实际所在层级、类型、是否必填；任何类目属性/版本字段。旧商品 catId=50023914、tbCatId=50010609、channelCatId=201409706 只能证明旧记录，不能证明新发布可沿用。
2. **完整固定字段**：freebies/itemTypeStr/quantity/simpleItem/itemLabelExtList/userRightsProtocols/defaultPrice/sourceId/bizcode/publishScene，以及 uniqueCode 的生成来源、是否与页面或一次操作绑定。不要照抄上游固定 uniqueCode 当成平台幂等键。
3. **配送与地点**：选定 UI 的 itemPostFeeDTO、顶层 onlyTakeSelf 的确切映射；itemAddrDTO divisionId/prov/city/area/gps/poiId/poiName 的类型和空值约束。精确地址只留父助手私有文件/管理员加密存储，开发端只需结构。
4. **一次已授权上传**：送出的素材 SHA256；`object.url`、`object.pix` 的形状/域名；是否符合 width×height；图片顺序与 major/extraInfo/type/status 的新发布语义。上传本身是写，不在预览或取证时偷跑。
5. **一次已授权提交的 ACK**：完整 ret 数组，data.itemId 的实际类型/值；失败/验证码/超时的结构。若未知，不为了得到 ACK 自动重发。success_ret 必须来自已确认协议证据，不能用测试 fixture 值。
6. **同 ID 只读回读**：完整精确 ret 数组（不能只报告 SUCCESS）、data.itemDO.itemId、data.sellerDO.sellerId 的结构和类型；状态字段从响应根开始的完整键路径、JSON 类型、实际审核中/在售允许值，以及对应 UI 状态的证据。无此证据不能配置或启用；不要使用测试里的 fixtureStatus/FICTIONAL_LISTED 等虚构值。另记录实际价格/标题/描述/图片数用于人工核对；状态命中允许值不证明内容和价格等价。

用户授权旧商品按原内容 20 元再次出售不替代上述协议证据。本实现不读取私有 source snapshot；父助手负责准备真实参数和单次验收。未提供未经取证的浏览器控件/选择器替代路径。无 push、无部署、无真实外部写。
