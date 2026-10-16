# 人工审批单条消息（2026-10-16）

## P0 独立审查 FAIL 与修复边界

`75b6f98` 独立审查 **FAIL / P0，禁止上线**：当时仅 live+CDP 执行新安全检查，无 CDP 的旧 Cookie 直发仍可绕过默认关闭开关，worker 也可领取历史 approved live 消息。此前测试通过不能抵消该漏洞。

本次关闭旧无 CDP 真实直发路径：**所有 live message.send 无条件检查默认关闭开关；没有 CDP 一律拒绝**，不提供另一核验机制或回退。worker 无条件排除 action 或账号模式为 live 的消息，含历史 approved；演示自动流程保留。只能由管理员指定单条 execute，通过前置核验后进入线程局部、一次性发送作用域；Provider 在操作锁内独立校验开关、CDP/凭据/接管 revision、running 队列记录、账号/模式/操作、批准时间、有效期及完整 digest/参数。仅提供 expected_binding 或直接 Provider.call 不构成授权。

修复本地测试不等于独立复审通过，不恢复上线许可。真实发送、accepted 回执判定及 Hermes 验收均未完成。

## 范围与来源

仅已有、当次 CDP 样本可核验 peer/CID 的普通文本；不建立会话、不发送图片、不提供任意 URL/JS。固定上游仍为 c2d5a02ad83b18863514389cedf7afbd993b683d。

管理员部署开关 `XY_MESSAGE_SEND_ENABLED=true` **默认 false**，还需 `XY_LIVE_ENABLED=true` 及完整 CDP account_id/uid/endpoint 绑定。此开关只允许 `message.send`；item/delete/publish/chats/history 等 CDP 操作仍拒绝。`browser_policy.cdp_writes=false` 指浏览器不执行写入；独立 WS 路径声明见 `message_send_policy`，不是账号已经启用的证明。

发送凭据是管理员独立导入工作台的同 UID Cookie，绝非“浏览器登录是唯一来源”。CDP 只读取会话双方并前后核验浏览器 UID；不从浏览器导出 Cookie，不向借用 context 注入 Cookie，不切换登录态。WS 使用账号隔离的临时 Cookie 文件和固定上游 token 获取过程，发送结束清理 Cookie 与 IM token 文件。新导入凭据或变更 CDP 绑定必须重新审批。

## 统一审批 / 执行

1. 通过既有 HTTP `/api/actions` 或 MCP 消息提案工具提交 account_id、kind=`message.send`、payload={cid,toid,text}、稳定 idempotency_key。
2. 开关、账号及独立 Cookie UID 检查，按需 CDP 只读采集并确认同 CID 的 peer；缺失/冲突即拒绝，不猜 CID、不使用历史缓存替代当前采集。
3. 加密 payload 冻结 UID、独立凭据 digest、CDP endpoint、接管 revision 与完整正文；整体审批 digest 覆盖账号、模式和所有 payload。绑定元数据仅管理员可见，不给 Agent 凭据指纹/端点。
4. 管理员核对完整 payload 并批准；有效期 15 分钟。批准不是立即发送。所有 live 消息不由定时 worker 自动领取，历史 approved 消息也不会因开关启用被批量执行。
5. 管理员 POST `/api/actions/{id}/execute`，body 为 `{digest,confirm:"确认执行"}`，或 UI “仅执行这一条”。原子领取指定 approved action，不启动其他历史操作。Agent/MCP 无执行、审批、解除接管、开关配置权。
6. 执行前再次只读核验 peer/CID、账号/凭据绑定、时效、接管、暂停；Provider 在操作锁内重查凭据绑定与限速。正文只接受 cid/toid/text；上游 item_id/image/任意扩展拒绝。
7. 未领取前可撤销；running 无法撤回已发出的请求。失败/超时/中断保持终态待核实，不自动重试。只有 Provider 明确在出站前拒绝的 busy/rate_limited 可保留 approved；CDP live 仍需重新显式选择执行，同一幂等申请不重放终态。

所有 FAQ 策略继续不可执行，autonomous_reply=false，人工接管继续阻断消息采集及发送；未放宽商品/会话/模板/期限/限额约束。此批不是无人值守客服。

## 返回语义与证据缺口

固定上游 send.py 调用 send_text 后 sleep(1)，返回本地产生的 mid，**没有解析发送 ACK**。现有实现不会产生 accepted，不将 ok=true 当平台接受。

发送后最多等待 10 秒读限速窗口（可停止，仍检查暂停/接管），再次只读采集；检查新增 outgoing message ID、本人 sender、同 peer/CID、精确正文。只记录 `matching_new_outgoing_observed`：人工同时发送同文也可能匹配，不能可靠关联本次请求。`verification=unconfirmed`、`delivery_confirmed=false`，不宣称接受/送达/已读；核对失败也不重发。写异常的只读核对不能将失败解释成未发生。

**因此完整 accepted/unconfirmed 自动区分尚未完成。** 不是通过虚构 ACK 字段让验收变绿。真实平台发送和首次联系由父助手/Hermes 执行，本地测试全部假数据。

### 父助手最小取证（不交真实 Cookie/正文）

- 在已经人工批准的单条发送中，记录 sendByReceiverScope 请求 headers.mid 与对应响应 headers.mid 是否严格相同；响应 code 类型、body 的键/类型，以及是否含稳定平台 messageId、cid、错误码。保留脱敏结构，不传真实正文或 token。
- 证明响应是该发送请求的 ACK，而非 /reg、heartbeat、push 或本地生成 ID；明确 code=200 在该响应中的接受语义。若缺证继续 unconfirmed。
- 只读验证 ACK messageId 与同 CID outgoing 记录的 messageId 是否相等；sender=本人且 pair=本人/指定对方。送达/已读另需专门回执，不能推断。
- 已有会话发送安全验收后，首次联系才取 `/r/SingleChatConversation/create` 请求 mid 与响应 mid 的关联及实际 cid 字段结构，证明双方及商品关联；当前 create_chat 返回的 mid 绝不能当 cid。

## 测试与部署

双 Python 全量、真实 stdio、临时演示 HTTP/UI 与隔离 Chromium 是本地验收，不代表真实账号/Hermes 部署。证据在未跟踪 scratch/xianyu-send-evidence，不提交。开关未在真实实例启用；本批不 push、不部署。既有分页不再改动。
