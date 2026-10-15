# 固定上游静态可行性核实（2026-10-15）

仅静态读取已安装 goofish_cli 源码，未在主进程导入业务、未登录或调用平台；固定提交仍为 `c2d5a02ad83b18863514389cedf7afbd993b683d`。路径以下均相对该包。

| 任务 | 入口与证据 | 结论 |
|---|---|---|
| P1-01 | `core/ws.py:200 create_chat(ws, *, myid, toid, item_id)` 发送 `/r/SingleChatConversation/create`，217 行返回本地产生的 mid；无匹配响应/可靠 cid 解析。`collect_session_cids` 明示不含可靠 peer。 | 阻塞；mid 不能当 cid，first_contact 保持 false |
| P1-03 | `commands/item` 只有 get/view/publish/delete；search 是公开搜索，非本人分页库存入口。 | 没有本人库存分页、状态/完整性契约；full_inventory_sync 保持 false |
| P1-04 | 同上；无更新现有商品入口或旧值并发条件。 | platform_edit_price 保持 false，不以发布替代编辑 |
| P1-05 | `commands/item/delete.py` 是删除；无非删除上下架入口。 | platform_relist 保持 false，不以删除冒充下架 |
| P1-07 | `commands/item/publish.py:27 publish(title, desc, images, price, original_price, delivery, post_price, can_self_pickup)` 内部先上传，再 recommend（46），再默认地点（49）；不接受冻结类目/地点。私有 `_build_publish_data` 接受字段，但不是具备预览/校验/持久快照的发布接口。 | 不足以安全完整适配；新增 live_publish=false、publish_complete_snapshot=false，Provider 在任何真实发布子进程之前拒绝。演示/本地发布申请仍可用，不表示真实发布可用。 |

没有升级上游、引入第二后台、远程 browser 或猜测私有 API。A 的阻塞不影响继续 B/C。本次补上真实发布 fail-closed 安全保护，避免审批后默认地点/类目变化。
