# 商品发布本地冻结链（2026-10-16）

> 更新：本文件下方记录 ac4e991 本地预览阶段。后续已实现默认关闭的独立受控执行器，最新执行方式与证据门槛见 [PUBLISH_EXECUTOR](PUBLISH_EXECUTOR.md)。旧隐式 publish 仍拒绝；预览本身仍不上传、不发布。

## 完成与未开放必须分开（历史）

已实现真实可运行的**本地**流程：管理员加密类目/地点输入 → 本地图片 SHA256 校验 → 冻结预览进入唯一 actions 队列 → 人工审批 → 管理员指定 action 校验。演示账号执行结果仅 `simulated`；live 在任何上传/网络传输之前返回明确失败。没有真实发布成功接口，没有新增可打开真实发布的环境开关。

`local_publish_preview=true`，`live_publish=false`、`publish_complete_snapshot=false`。完整平台快照还需要上传返回、平台类目/地点字段语义及可靠响应证据。候选 DTO 是源码投影，不是可发送协议；特意不生成 imageInfoDOList/uniqueCode，不调用上游 publish 自动重算入口。

所有 live action（包括历史商品 approved）不由 worker 自动领取。Provider 继续拒绝 live publish，并关闭旧 live delete 直通；delete 不是普通下架。改价/非删除上下架的真实执行、同 itemId 自动回验仍未实现，不宣称完成。现有管理员人工核对可用于已有不确定操作，但不是自动回验。

## 使用

1. 管理员 PUT `/api/accounts/{id}/publish-defaults`，或商品草稿页面的管理员 JSON 表单。以下仅为虚构格式，不是推荐类目/地点：

```json
{
  "category": {"cat_id":"1","cat_name":"虚构类目","channel_cat_id":"2","tb_cat_id":"3"},
  "location": {"divisionId":"123","prov":"测试省","city":"测试市","area":"测试区","gps":"120.1,30.2","poiId":"fictional","poiName":"测试地点"},
  "region_summary":"测试市"
}
```

`region_summary` 是允许 Agent 读取的摘要，管理员不得填入详细地址。完整 location 仅管理员读取，Fernet 加密存储，不进入审计、通知或商品台账。每次保存产生新的 revision，即使值改回也要求重新预览。此输入来源明确标为 `admin_local_unverified`，不假称从平台采集。

2. 本地素材上传沿用现有接口，自动去 EXIF；这不是上传闲鱼。POST `/api/publish-preview` 接受现有 ActionIn（kind 必须 item.publish）。完整 PublishIn 参数、不可变素材 ID/hash、类目、配送候选 DTO、地点、revision、账号 UID/模式全部进入加密 action payload 和审批 digest。HTTP 与 MCP `preview_listing` 返回角色投影，Agent 看不到 GPS/POI/完整 candidate。
3. 管理员检查 `/api/actions/{id}`，使用既有 approve 与 execute 路由。指定 action 和 digest 才执行一条，重复执行被拒。执行前重新比较默认 revision、UID、图片文件 hash 与全部候选字段。变化则失败，需新幂等键重新预览/审批。相同幂等键只返回旧冻结操作，不会重新授权。UI 对相同内容在本页面内复用幂等键；修改默认快照后如需对相同内容重新申请，请刷新页面并重新载入草稿，再生成新预览（或 API 显式使用新幂等键）。旧“发布申请”与“冻结预览”使用不同的幂等键命名空间。
4. 演示可走完整审批/模拟执行；live 即使 XY_LIVE_ENABLED=true 也只完成本地校验后停止。预览绝不调用上传、类目推荐、地点接口或浏览器。旧 `/api/actions item.publish` 和旧 MCP propose_listing 仍为不完整本地申请，不能绕过真实执行阻断。

## 存储及恢复

没有新增数据库列/表：使用既有加密 settings（命名空间 `publish-defaults:<account_id>`）和加密 actions.payload 的版本化快照字段。schema 仍 v10；既有 key 校验、备份恢复加密验证覆盖这两类字段。恢复会按既有规则使 pending/approved 失效，running 不确定，不能重放。

## 固定上游证据与父助手最小取证

固定 `c2d5a02ad83b18863514389cedf7afbd993b683d` 的 `commands/item/publish.py`：39–49 行先上传，再推荐类目，再读取默认地点；84–174 行 builder 接受显式 cat_info/location。配送双层 onlyTakeSelf 与固定 uniqueCode 只有源码行为证据，不能当作正确业务含义或幂等保证。项目候选 DTO 用 Decimal 精确到分，不导入上游业务模块，不修改 site-packages。

父助手可先在**本人正常出售商品的编辑/发布页面**手工打开开发者工具。只读阶段不上传、不点击提交或状态确认；不导出 HAR/Cookie/Authorization，不向 Agent 回传地址原值。最小可交付证据：

- 类目：同一选择记录的 catId/catName/channelCatId/tbCatId，是否有额外必填属性/枚举/版本；区分推荐值与最终选定值。
- 地点：默认来源与被选记录标识；divisionId/prov/city/area、longitude/latitude 或 gps、poiId/poi 的字段名/类型/空值约束。原值只留管理员本地加密文件，Agent 只收字段类型与非敏感区域摘要。证明选择不是任意 all[0]。
- 配送：三种 UI 选项与 itemPostFeeDTO、顶层 onlyTakeSelf 的对应关系；尤其“允许自提”是否等于 onlyTakeSelf；运费单位和无邮寄时是否保留运费。
- 图片：在另行授权的一次上传中，素材 hash 与响应 URL/宽高对应关系、主图与顺序语义。上传也是外部写，必须有独立审批边界，不可作为只读预览暗中执行。
- 发布：另行指定单条写审批后，请求关联标识与 ret/data.itemId 的实际响应结构，失败/验证码/超时表现；不把包含 SUCCESS 的任意字符串当可靠成功。核验同 UID 本人记录与 itemId、在售/审核中状态。
- 改价/上下架：本人 itemId、seller UID、精确原价/运费/状态/版本时间；按钮文字、确认提示及明确非删除操作的请求字段名、更新返回与同 ID 只读记录。没有接口证据不猜 endpoint，不用 delete/recreate。

最小只读脚本建议：父助手在已有授权采集框架中仅为新建任务页增加 response 监听，白名单限定页面实际观察到的类目/地点/本人详情响应；回传 `Object.entries(record).map(([key,value]) => [key, Array.isArray(value) ? 'array' : typeof value])` 的**字段名与类型**，不回传 value、不调用 evaluate(fetch)、不拦截修改请求、不监听 Cookie。未知 endpoint 先人工识别再写白名单，不能在开发端猜造自动采集脚本。真实 ACK 只能在批准的一次写后取证，不能为采集 ACK 自动重发。
