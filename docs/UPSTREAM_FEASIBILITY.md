# 固定上游静态可行性核实（2026-10-15）

仅静态读取已安装 goofish_cli 源码，未在主进程导入业务、未登录或调用平台；固定提交仍为 `c2d5a02ad83b18863514389cedf7afbd993b683d`。路径以下均相对该包。

| 任务 | 入口与证据 | 结论 |
|---|---|---|
| P1-01 | `core/ws.py:200 create_chat(ws, *, myid, toid, item_id)` 发送 `/r/SingleChatConversation/create`，217 行返回本地产生的 mid；无匹配响应/可靠 cid 解析。`collect_session_cids` 明示不含可靠 peer。 | 阻塞；mid 不能当 cid，first_contact 保持 false |
| P1-03 | `commands/item` 只有 get/view/publish/delete；search 是公开搜索，非本人分页库存入口。 | 没有本人库存分页、状态/完整性契约；full_inventory_sync 保持 false |
| P1-04 | 同上；无更新现有商品入口或旧值并发条件。 | platform_edit_price 保持 false，不以发布替代编辑 |
| P1-05 | `commands/item/delete.py` 是删除；无非删除上下架入口。 | platform_relist 保持 false，不以删除冒充下架 |
| P1-07 | `commands/item/publish.py:27 publish(title, desc, images, price, original_price, delivery, post_price, can_self_pickup)` 内部先上传，再 recommend（46），再默认地点（49）；不接受冻结类目/地点。私有 `_build_publish_data` 接受字段，但不是具备预览/校验/持久快照的发布接口。 | 不足以安全完整适配；新增 live_publish=false、publish_complete_snapshot=false，Provider 在任何真实发布子进程之前拒绝。演示/本地发布申请仍可用，不表示真实发布可用。 |

## 121f3c8 后的底层复核（2026-10-15）

本轮重新读取固定源码，不以缺少公开命令作为最终不可行结论：

- publish.py:84–174 的 `_build_publish_data` 明确接收 cat_info/location/image_infos，可在本项目 adapter 复用构造，且能用 Decimal；但 39–49 的类目推荐以已上传图片为前提，预览必须处理“上传本身是外部写”而不能偷跑。136–148 从 location.all[0] 构造 GPS/POI 完整地点，不能直接暴露给模型。170 的固定 uniqueCode 不构成幂等保证。可靠预览/执行需要独立冻结、默认地点比较和真实响应取证；本轮未打开 live_publish。
- ws.py:200–217 可复用 create 请求构造；327–386 可复用 listUserMessages 请求、mid 响应匹配、hasMore/nextCursor。368–372 只是高层输出丢失 ID，并不证明底层永无 ID。需要脱敏原始消息模型证明稳定 ID 与 sender/content 同记录后，项目适配器有界读取，不另启第二自动回复后台。
- 固定 commands 目录没有本人库存/订单分页/价格修改/状态转移来源；不能猜 endpoint。浏览器可作为项目内可维护适配器，但先要具体页面、账号 uid、分页末页、状态语义及字段证据；复用现有 task_page 生命周期与 cancellation，不提供任意 URL/JS。

完整矩阵、依赖与 Hermes 只读字段清单见 [OPERATIONS_NEXT](OPERATIONS_NEXT.md)。本轮没有请求真实页面或公开网络源码，证据均为固定安装包静态阅读。暂不需要依赖变更；若后续确需 fork/升级，须另报具体提交/license/风险/验收再决策。

没有升级上游、引入第二后台、远程 browser 或猜测私有 API。A 的阻塞不影响继续 B/C。本次补上真实发布 fail-closed 安全保护，避免审批后默认地点/类目变化。

## D / P1-06 第一阶段来源核实

`commands/message/history.py:21 history(cid, limit_per_page=20)` → `core/ws.py:327 list_user_messages` 会翻页到底；368–372 只返回 send_user_id/send_user_name/message，丢弃每条消息 ID/时间。`extract_incoming_text` 469–476 的正文事件也无 message ID；`extract_meta_event` 519–525 的 new_msg 有 msg_id/cid/ts，但没有发送者和正文，两者没有可靠关联契约。不能用正文 hash 伪装消息 ID（相同文字可多次合法发送），也不能凭空生成平台 ID。

因此 D 保留阻塞：未实现低频增量采集/去重/客服待办 UI，不启动第二 WS 监听或后台，不声称实时客服完成。下一项需先在固定桥子进程建立有最小消息 ID、发送者、正文可靠关联且有界分页的只读适配契约；之后再做持久去重与暂停停止测试。
