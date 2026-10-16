# 有界页面读取（2026-10-16）

## 买到订单

固定自建 `/bought` 页观察 allowlisted MTOP，不回放请求、不猜页码/POST 参数、不点击订单动作。首屏响应不代表 DOM/hook 就绪：以 750ms 最小 tick 等待队列和页面，allowlisted 请求 loading/pending 时不滚动；document.scrollingElement.scrollHeight 跨 tick 稳定才使用 window 滚动，底端按同一 root 的 scrollHeight - clientHeight 计算，当前位置用 scrollTop，避免 innerHeight 包含横向滚动条导致提前停下。已到底时先回退 64px，下一 tick 再到底，以恢复在加载 hook 注册前错过的滚动事件；每 tick 最多一次移动，不发 synthetic 事件、不主动请求。高度变化或新数据后重新等待稳定。总 25 秒 deadline 不重置，没有新响应仍 partial/time_limit；高度稳定不等于末页。UID 前后核验、原页不导航、借用 context 不关闭保持不变。

结构来源：父助手 `/home/lan/.hermes/cache/scratch/xianyu-readonly/order-pagination-observation.json` 和 ORDER-PAGINATION-NOTE.md。仅严格字符串 `"true"` 已证。`"false"`、空值、布尔值等仍未知，不能推断订单末页。因此 order_sync 完整能力仍 false。本次范围仅 bought_orders，**卖出订单不支持**。

上限：每响应 1 MB、累计 5 MB、每页 100 条、最多 20 页/500 个稳定 ID、采集 25 秒（外层操作超时更短时可能直接失败）。达到限制或未证末页为 partial；重复游标/重复 ID 页立即停止，无重放循环。不同页相同 ID 同内容合并；内容冲突 fail closed，缓存不覆盖。原始 lastEndRow 仅在本次内存作重复检测，不持久化、不输出。

## 本人发布列表

固定自建 `/personal` 页使用同一有界滚动路径，必须观察 `head.baseInfo.self is True`，仍保留前后 UID 核验。仅 bool `nextPage is False` 且分页结构有效才返回 `partial=false/completion=complete/stop_reason=end_reached`，范围严格是 `self_published`。空末页可完整；未知类型、无新响应、重复页、限制停止均 partial。短页和 totalCount 不作为末页依据；同一 ID 内容冲突失败而不覆盖。

**未实现范围单列：卖出订单、下架列表、全状态库存。** full_inventory_sync 与 order_sync 仍 false；能力接口分别声明 scopes/unsupported_scopes、orders_terminal_verified=false、platform_verified=false。父助手报告直接页面等待 2.5–3 秒后 window 滚动已读 personal 两页 40 条/bool false、bought 五页 50 条/仍 true；但部署基线 1ef2c3f 的 API 均仅一页/time_limit，因此工作台真实分页仍未验收。父助手进一步报告 27298e5 API 仍一页/time_limit，并确认横向滚动条导致旧几何计算少滚 15px；本轮统一 scroll root 修复该确证缺陷，但一次滚到真实底端后 2.5 秒仍未增卡，不能认定它是唯一根因。本地延迟 HTML/真实 CDP 回归覆盖两页、五页及横向滚动条路径，不以假数据冒充真实验证；修复后真实 API 由父助手再测。

## 持久与接口

v9→v10 显式迁移给 operation_syncs 增加 scope、pages_read、stop_reason。迁移前备份，旧记录标记 legacy_samples/0 页，不追认完整。API sync 返回本次进度；GET 的 last_sync 保留该边界；MCP 现有名称兼容，透传相同结果。UI 展示范围、页数、停止原因。

缓存是最多 500 条的历史并集，不是最近完整快照，始终 partial/cached_samples；即使某次范围读取完整，也不表示历史混合缓存完整或最新。完整/部分/失败均不清除缺席记录、不标售罄，不动本地草稿。失败写独立安全错误状态，历史不清。

## 3bb8734 后连接默认设置差异

父助手报告 3bb8734 API 仍一页/time_limit，且同浏览器 no_defaults=True 的任务页高度 1241、普通连接高度 3729，相同 inner 尺寸，单改 viewport 无改善。后续父助手同任务页控制实验：baseline 3秒再4秒、bring_to_front 后2500ms均1241；只对任务 target 启用 focus emulation 后3秒3729，hidden=false/hasFocus=true、图片93/93decoded、媒体布尔值均不变。列表父容器 maxHeight 480→3060px，是实际几何变化，不是仅 document.hidden 的原因。经授权仅 orders/inventory 新任务页在导航前启用 focus emulation；保留 no_defaults、geometry、节流与UID校验，不改借用context默认或原页，失败/取消 detach session 并关闭新页。search/messages不启用。完整证据与诊断脚本见 [CDP_DEFAULTS_DIAGNOSIS.md](CDP_DEFAULTS_DIAGNOSIS.md)。**真实应用分页尚待父助手验收**，不宣称已修复真实 API。

## 需要父助手补证

- 订单真实终页 nextPage 原始类型和值及其页面语义；不能仅给字符串类型。
- 第一页→下一页→末页 POST body 的字段名和脱敏分页字段变化：尤其 lastEndRow、页码、页大小、状态筛选（若存在）。此前 URL query 没有 data 不代表 POST 无参数。
- 页面滚动容器 DOM 选择器；若使用按钮，提供只读加载更多选择器、禁用/末页选择器及触发请求的对应关系。
- 本人商品默认激活标签/筛选、head.self=true 与分页请求归属、分页字段和 bool false 终页；不能由“我发布的”标题推出下架/已售全覆盖。

本地 fixture 验证不是真实平台验收。发布、首次联系、改价/上下架、FAQ 执行与实际 Hermes 接入仍未完成。不 push、不部署。
