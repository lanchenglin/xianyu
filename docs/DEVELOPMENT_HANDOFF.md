# 本地开发交接与未完成功能清单

更新：2026-10-18；核对基线 `feat/local-next` / `f8d1ad8`。本文正文只描述当前实现，不用“最新段落优先”覆盖旧声明。历史失败、CI 和分批测试证据保留在 [TEST_REPORT](TEST_REPORT.md)。本批未提交、未 push、未部署、未访问真实平台。

## 1. 从哪里开始

先读 [AGENTS](../AGENTS.md)、[README](../README.md)、本文、[当前能力矩阵](CAPABILITY_MATRIX.md)、[测试记录](TEST_REPORT.md)。专项入口：

- [部署](DEPLOYMENT.md)、[安全](SECURITY.md)、[MCP](MCP.md)
- [发布预览](PUBLISH_PREVIEW.md)、[发布执行器](PUBLISH_EXECUTOR.md)、[消息发送](MESSAGE_SEND.md)
- [消息样本](MESSAGES.md)、[低频观察](MESSAGE_OBSERVATION.md)、[分页](OPERATION_PAGINATION.md)
- [通知](NOTIFICATIONS.md)、[离线灾备](BACKUP.md)、[后续断点](OPERATIONS_NEXT.md)

## 2. 当前状态：实现、启用、验收必须分开

### 2.1 已有代码，可继续复用

FastAPI + SQLite 单实例；中文 UI、管理员/Agent 分权、加密账号和动作、唯一审批队列、幂等、暂停、不确定不重试。搜索/详情/既有会话/历史有固定上游适配，但 CDP 只允许 search/orders/inventory/messages；隔离模式与 CDP 的支持范围不同。

本地草稿原位编辑/revision/归档、素材、商品台账、人工核对、站内通知已读/归档、默认关闭的外部固定摘要通知、管理员离线 backup/restore CLI 已实现。schema v10；恢复使旧授权失效并暂停账号/监控/观察、关闭外部通知、撤销 FAQ。

订单买到列表与本人发布列表支持有界分页及加密历史缓存；消息支持末条样本、严格普通文本、按需本地草稿及默认关闭的低频采集/接管。有限 FAQ 仅保存策略，永不发送。

发布预览不上传。默认关闭的发布执行器已有独立 Cookie 上传、完整模板单次提交、精确 ret/同 ID UID/严格类型状态回读；管理员录入协议、冻结审批、指定一条执行，worker 不领取 live。消息独立 Cookie/WS 单条执行同样默认关闭，需 CDP peer/CID 核验；没有可靠 ACK，保持 unconfirmed。二者均未真实写验收。

### 2.2 尚未实现或未开放

- 首次联系陌生卖家、可靠消息接受/送达/已读自动判定。
- 同 itemId 改价/内容编辑、普通下架/重新上架；旧 live delete 已关闭，不能以删除重建代替。
- 卖出订单、订单真实末页、下架列表/全状态库存同步；现有有界样本不是完整同步。
- 完整消息历史增量监听、漏消息补偿、无人值守 FAQ 执行/限额账本；低频末条采集不是实时客服。
- 批量运营、草稿取消归档、素材回收；已有单条编辑/归档不应再列为未实现。
- 价格历史/降价提醒、微信/邮件通道；已有钉钉/受限 webhook 摘要通知不应再列为未实现。
- 自动定时备份、保留/清理、云备份、密钥轮换；已有离线恢复及虚构数据演练不应再列为未实现。
- 发布完整协议的真实平台验收、图片与配送语义、uniqueCode 来源及真实状态证据；有执行代码不等于已验收或可直接开启。
- 实际 Hermes 等客户端、真实模型服务、Docker 部署验收；Windows 原生支持暂停。

`GET /api/capabilities` 是代码声明，不是账户授权。`live_publish` 与嵌套启用字段为双开关逻辑与；`executor_implemented=true` 与 `platform_verified=false` 并存。详见逐项矩阵。

### 2.3 永久人工

付款、购买/下单、退款、确认收货、提现、成交承诺等由主人在平台完成。不因批准消息/发布而授权交易。所有已开放平台写仍逐条审批；自动客服策略改变须另行设计授权，不能删审批或给 Agent 管理员令牌。

## 3. 环境与验收状态

默认 Linux/WSL Python 3.11/3.12，当前开发 `.venv` 为 3.12.14。早期 pyee 3.11 安装问题已修复，锁解析必须保留 `--universal --python-version 3.11`。Windows 原生支持暂停：`53400f8` CI 38727928186 的 Windows 双版本失败，Linux 五作业通过；快照在 `work/windows-support-53400f8`。早期 Windows CI 成功不恢复当前支持。

用户报告 `b8ea112` 的真实 inventory 2页40条 self_published complete、orders 13页130条 time_limit partial；这是外部报告，不是本批复测，更不是所有范围验收。用户报告 `cea21b7` 消息 P0 复审 PASS、CI38868085093 五绿；真实消息开关仍未开、ACK 未核实。发布历史独立审查 FAIL 与 f8d1ad8 修复证据保留，本批本地审查不冒充第三方独立复审。

## 4. 经核实的后续任务

| 编号 | 当前实现与剩余门槛 | 入口 |
|---|---|---|
| P1-01 首次联系 | 未开放；须真实响应 CID 与请求关联，mid 不能代替 CID | message_send.py、provider.py、bridge.py |
| P1-02 回执闭环 | 人工核对已实现；同文观察非 ACK，可靠自动回执待证 | service.py、message_send.py |
| P1-03 本人库存 | self_published 有界分页已实现；全状态范围待证，失败不可清历史 | operations_browser.py、operation_pagination.py、operations_cache.py |
| P1-04 改价/编辑 | 未实现；同 ID 原值/归属/版本及写语义待证 | models.py、provider.py |
| P1-05 普通上下架 | 未实现；delete/recreate 禁止替代 | provider.py、service.py |
| P1-06 客服 | 末条低频采集/接管/策略存储已有；历史游标、item/cid 绑定、限额账本、授权决策仍缺 | message_observation.py、faq_policy.py |
| P1-07 发布 | 本地冻结和默认关闭单条执行已有；平台协议/状态/图片/配送真实验收未完成 | publish_preview.py、publish_executor.py、bridge.py |
| P2-01 订单 | 买到有界分页/API/UI/MCP 已有；卖出、末页和全状态待证，无交易写 | operations*.py |
| P2-02 本地管理 | 单条编辑/归档已有；批量、取消归档、素材引用回收待设计 | service.py、app.py、static/ |
| P2-03 通知 | 站内状态及钉钉/webhook 已有；真实接收端验收、价格历史未完成 | notifications.py |
| P2-04 灾备 | v10迁移、离线备份恢复已有；本批补发布阶段恢复回归，定时/保留策略未做 | db.py、backup.py、cli.py |
| P2-05 接入 | 真实 MCP stdio 临时集成已测；实际客户端未验收，不引入竞争账号的第二后台 | mcp_server.py |

## 5. 改代码的路径与完成定义

按需核查 `models → app 鉴权/capabilities → service 审批/执行 → provider/bridge → db 迁移 → UI → MCP → 测试/文档`。固定上游 `c2d5a02ad83b18863514389cedf7afbd993b683d` 仅在 bridge 子进程导入；不改 site-packages。

每项均需适用的跨账号、摘要/变化、幂等、并发、超时/重启、暂停、权限投影回归。发现缺陷先 RED 后最小修复；补充回归首次通过如实说明。状态必须区分代码、隔离测试、真实验收。不得删除历史 FAIL 或用 fixture 当真实协议证据。

## 6. 本地验证命令

已有工作副本先 `git status --short`、核对分支和 HEAD；不要自动切 main、拉取、提交或清理未跟踪文件。本批不安装/升级依赖。不要执行真实服务的 init/serve 或读真实配置。

```bash
env -u PYTHONPATH .venv/bin/python -m pip check
env -u PYTHONPATH .venv/bin/python -m ruff check .
export XY_TEST_CHROMIUM=/snap/bin/chromium
export PLAYWRIGHT_BROWSERS_PATH=/home/lan/.hermes/cache/scratch/xianyu-audit-browsers
export PLAYWRIGHT_SKIP_BROWSER_GC=1
env -u PYTHONPATH TMPDIR=/home/lan/.hermes/cache/scratch .venv/bin/python -m pytest
env -u PYTHONPATH TMPDIR=/home/lan/.hermes/cache/scratch .venv/bin/python scripts/smoke_ui.py
node --check xianyu_workbench/static/app.js
git diff --check
```

路径仅为本机开发示例。测试必须临时虚构数据、随机本地端口、新 profile；未安装 live 或浏览器不可用时如实记录 skip/环境阻塞。必须等待完整 summary。Windows 命令不作为本分支支持指南，历史见测试报告。

## 7. 后续交接要求

报告修改文件、问题与复现证据、实际命令/完整结果、真实未验收边界及剩余事项。不要把单批完成写成全部需求完成。是否 commit/push/部署由当前用户明确授权，不依照历史计划中的提交指令行动。
