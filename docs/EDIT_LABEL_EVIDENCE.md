# 官方 0.0.178 标签转换公开证据（2026-10-19）

仅公开静态源码分析，无真实 API 请求或账号访问；未读取私有原件。源码：
https://g.alicdn.com/idle-pc/xy-site/0.0.178/js/p_publish-index.js

本次下载 1,391,053 bytes，SHA-256 `adaa298b7202e14104c2ae125276432152fc4f30d6208b5bd2f13b8781958d86`。
公开副本在 `/home/lan/.hermes/cache/scratch/xianyu-transform-public-0.0.178.js`。以下 offset 是 Python 解码字符串中的零起点字符位置，便于复核，不是私有数据位置。

## 已证逻辑

1. 模块18200 `nl`（offset 1347370附近）初次加载直接使用 `itemLabelExtList: e.itemLabelExtList || []`。这一步本身不能解释捕获请求新增的字段。
2. 标签表单组件（offset 1083904附近）读取原标签 `properties`，按 `:` 与 `##` 拆出 property/value，建立 `selectedMap`；生成 selectedList 时保留原对象并设置 `text/valueName/isUserClick/properties`。这包含编辑初始化逻辑，不是纯可逆映射。
3. 模块9370 导出 `lO` 对应固定 `mtop.taobao.idle.kgraph.property.recommend` v2.0（offset 1029300附近）。标签组件调用它取得 `data.cardList`，卡片含 `cardData.valuesList`，再根据 selectedMap 更新 `isClicked/isUserClick`，还可继续调用一次推荐接口（offset 1085480附近）。本批没有调用这些接口。
4. 局部 `R` 函数（offset 1083150附近）收集各卡片 `valuesList` 中 `isClicked === "1"` 的项，展开 **服务端项的 `transportData`**，并覆盖：
   - `text`: propertyId 为 `"-10000"` 时取 `catName`，其他取 `valueName`；
   - `isUserClick`: 选中项的值；
   - `properties`: `propertyId + "##" + propertyName + ":" + (channelCatId 或 valueId) + "##" + (catName 或 valueName)`。
5. 点击/取消分支（offset 1088730附近）会设置 `isUserClick` 和 `isUserCancel`（`"1"` 或 null）并更新 transportData。不能将 null 当作所有标签的固定默认。
6. 初始化合并函数 `I`（offset 1082244附近）按 properties 去重合并原标签与新标签；因此顺序、保留项和服务端补充项都需要实际证据。
7. 模块18200 `xP`（offset 1341191附近）先展开 `values`，再覆盖文字/金额等；未在该构造器内重新定义 itemLabelExtList。提交标签实际来自表单处理后的数组。

## 追加真实匹配证据与本批实现

父助手新增四份脱敏证据（live-evidence/match-evidence/request-evidence/binding-summary）确认：两次推荐唯一选中category的15字段transportData与实际编辑标签严格全等，额外text/properties符合R函数。未选品牌/成色不纳入。null来自响应原值，不补默认。

本批再次核对公开代码：offset1083904 的首selectedList为原标签展开，text/valueName=`old.text || properties.split(':')[1].split('##')[1]`，isUserClick="1"；offset1341191的YG为Date.now字符串拼接floor(1000*Math.random())，实际推荐调用点显式YG。没有未知uniqueCode生成规则，不把它当版本/幂等保证。

可选 `label_dependency.mode=single_category_v1` 绑定两份完整请求与响应证据，执行前仅调用固定推荐v2.0两次，精确重验后再双读/提交。详见ITEM_EDIT。对新实际协议依然需要管理员录入完整脱敏外的值，开发fixture不能作为启用证据；请求/响应过大、额外选中标签、SKU、动态响应差异一律停止，不猜过滤。无平台编辑验收。

## 追加证据前的结论（历史）

公开源码证明标签数据依赖 **推荐卡片 transportData + 表单选中状态 + 原标签合并**，不是从 editDetail 九个字段必然推导成请求十八个字段。脱敏 shape 中的 channelCateName/valueName/tbCatId/subPropertyId/subValueId/propertyName/labelFrom 等新增字段，以及 valueId/labelId 等从字符串变为 null 的原因，仍无法仅凭源码和 shape 对应到该目标。

不新增 labels_v1，不补 null/空串/类目默认值，不复制源码中的默认类目到协议；现有 identity 仅在原始请求数组与完整源数组逐类型全等时有效。提供的真实标签数组不满足 identity，继续明确阻塞真实协议录入，不妨碍其他已证转换的本地实现。

## 父助手最小补充证据

只需脱敏结构/语义关系，不需要提供私有原件：

- 同一次编辑初始化所消费的相关 cardList/cardData/valuesList/transportData 完整逐字段类型，以及与最终 request.itemLabelExtList 的逐叶对应；未知新增字段也必须列全。
- 选中分支：propertyId 是否为 `-10000`、isClicked/isUserClick/isUserCancel 的来源；原标签 properties 与推荐项匹配/合并规则、最终顺序和数量。
- null、缺字段、空字符串的逐项区分，说明哪些来自 transportData 原值，哪些由页面确切分支产生；不能概括成“缺省置null”。
- 若推荐结果参与请求，需定义如何冻结和重新验证其依赖。当前协议只读 detail/editDetail，不会为补齐标签自动添加推荐请求通道。

得到这些证据后再单独批准/实现有限标签适配；当前真实编辑仍默认关闭，未平台验收。
