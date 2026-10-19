# 受限每日发布管理员授权

2026-10-19：代码默认关闭；本机已完成真实工作台单条发布/精确回读，并由管理员启用固定商品每日09:00策略。目标为固定账号的“6米3.5架子管”、原价2200、原图1张、持续库存、每天新建同款。首次计划分钟真实执行尚未发生，详见 [真实部署验收](LIVE_PUBLISH_ACCEPTANCE.md)。该事实不是其他部署的默认授权。

## 授权而不是移除审批

所有平台写仍经 actions 队列及 operations.lock。管理员批准一个固定范围的持久策略，tick 只原子插入该策略自己的新 approved action（审计 actor=admin_policy），不领取历史批准，不给 Agent 管理员权。普通单条发布仍逐条审批。

固定 Asia/Shanghai、默认09:00，可配置 HH:MM。仅该分钟的 tick 可领取；错过不补发、不追赶昨天。账号＋当地日期为数据库永久唯一键；撤销、改时间、重建策略不能清除占位。所有非 submitted 结果（包括 failed/blocked/rejected/expired/pending/approved/running/unconfirmed）以及账本引用的 action 缺失，统一阻止后续日期。配置 enabled=true 返回409 daily_unresolved，tick 返回 reason=daily_unresolved；管理员状态返回 effective=false、blocked_reason=daily_unresolved，不以存储的 enabled=true 冒充有效授权。可保存关闭配置但不清除账本阻塞。状态的 effective 还核对开关、生成模式、暂停/接管及当前快照，仅代表授权条件可用，不代表当前正值计划分钟。配置与tick事务内复用同一 LEFT JOIN 检查，缺失action也 fail closed；不确定结果不能靠重新配置绕过。未完成的领取（包括进程中断）不会重新调度。管理员也不能重发已经上传或提交的 action。

启用要求：同账号 live item.publish 工作台 action 为 submitted，且 ownership/status/content_verified 全部为 true；当前快照仍一致；管理员填写真实验收证据，显式选择 generation_mode=timestamp_random_v1。仅网页发布、人工 reconciliation、demo 或 fixture 都不能作为生产启用依据。系统核验保存的执行结果，不能自动鉴定管理员证据文字真实性；生产管理员必须提供真实证据，开发测试永不触及真实实例。

冻结完整 payload、凭据指纹、UID、协议/defaults revision、素材 ID/hash、标题/描述、价格、配送、地区。每个上传/提交/回读阶段重新核验。暂停/人工接管立即阻断；API 暂停/接管撤销每日策略，解除不恢复授权；任何快照变化阻断并要求重审。撤销不能撤回已发出的网络请求。ACK 返回先前已记录 itemId 时不能视作新建，保持 unconfirmed。不会删新帖、改其他商品、失败重发或生成未知 uniqueCode。

## 已证 uniqueCode 生成模式（2026-10-19 修正）

公开官方 JS `https://g.alicdn.com/idle-pc/xy-site/0.0.178/js/p_publish-index.js` 模块18200的 YG：`Date.now()` 字符串拼接 `Math.floor(1000*Math.random())`，不补足三位；网页发布/编辑每次提交新生成。此前要求证明固定码复用的控制面已删除，不能要求管理员提供不存在的复用证据。

每日新 action 在 BEGIN IMMEDIATE 创建事务内抽取一次：当前毫秒字符串＋0～999随机整数（Python secrets.randbelow 均匀采样），仅替换 template.uniqueCode；码、payload、digest、日期账本及 settings 中哈希索引的加密占用记录一起提交。碰撞检查已有码占用和历史发布快照，碰撞返回 generation_collision，不创建 action、不占日期、不写平台、不在本次调用重抽。不同账号并发也由同一数据库事务串行保护。它不是平台幂等保证。

执行预检只允许有日期账本、当前策略 revision 和首次码占用记录的 action 将该单一字段归一到授权模板进行比较，其他整个 payload 必须完全一致；码被替换也拒绝。相同 action 重进/恢复不重新生成、不重发，日期占用永久保留。settings 索引随既有加密备份保留，恢复仍撤销每日策略。

## 管理员 API / UI

商品管理的管理员每日授权表单支持配置、读取范围、撤销、单次 tick。接口全部 admin-only：

- `GET /api/accounts/{id}/daily-publish`
- `PUT /api/accounts/{id}/daily-publish`
- `POST /api/accounts/{id}/daily-publish/revoke`
- `POST /api/accounts/{id}/daily-publish/tick`

PUT JSON：

```json
{
  "enabled": false,
  "source_action_id": "经真实工作台精确回读验收的action编号",
  "time": "09:00",
  "evidence": "真实验收时间、来源与重复新建协议证据摘要，不填凭据",
  "generation_mode": "disabled",
  "confirm": "授权每日最多一条"
}
```

开启必须显式设 enabled=true、generation_mode="timestamp_random_v1"，且双执行开关已配置。默认 generation_mode="disabled"；旧 reuse 配置不自动转换授权，旧启用策略 tick 时撤销并要求重新授权。原单条静态协议保留兼容。GET 含私密冻结范围与证据，只允许管理员；不向 MCP/Agent 暴露。

## CLI / 父助手调度

`xianyu-workbench daily-publish {status,configure,revoke,tick} --url <固定工作台URL> --account-id <账号ID>`；configure 另用 `--config <管理员JSON路径>`。从已导出的 `XY_ADMIN_TOKEN` 读取管理员凭证，不读取 .env，不启动第二 worker、不直接打开数据库；只请求现有工作台 HTTP。仅 HTTPS 或 loopback HTTP，拒绝重定向、不使用环境代理、不自动重试。命令输出配置可能包含私密快照，禁止公开保存。网络超时应先在工作台核对，不能据此假设没发布。

应用安装本身不创建宿主定时器。父助手已在本机配置用户systemd服务及timer每分钟调用一次tick；其他分钟无操作，计划分钟内重复调用由数据库唯一键拒绝。服务和timer均enabled/active，WSL宿主须在线，首次09:00真实执行仍待验证。

## 迁移 / 恢复

schema v12→v13 显式新增 daily_publish_dates，升级前按既有机制备份；策略沿用加密 settings，旧库没有策略即关闭。离线恢复保留日期账本，撤销所有每日策略、更换 revision、暂停账号，旧 actions 按原规则失效/转不确定，不重放。回滚到旧程序不能打开未来 schema。

## 仍需真实证据

1. 发布ACK与工作台自身上传/提交/精确内容回读已验收，证据范围见LIVE_PUBLISH_ACCEPTANCE；不以网页操作替代。
2. 首次每日计划分钟的动态生成→新action→新itemId→精确回读仍待发生；非计划分钟tick已实测无操作。
3. 图片当前验证数量并经本地EXIF清理/JPEG重编码，不证明像素等价。
4. 撤销/恢复/未知停止的隔离测试已通过；本机策略当前开启，不宣称已现场演练所有故障。

付款、退款、确认收货、下单等永久人工。改价、非删除上下架、可靠消息 ACK 缺协议，未猜接口。
