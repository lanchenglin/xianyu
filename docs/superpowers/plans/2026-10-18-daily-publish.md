# 受限每日发布 Implementation Plan

**Goal:** 兼容已取证发布结构、精确内容回读和管理员每日一条持久授权。

**Architecture:** 使用现有加密快照与 actions 队列。新增加密策略和账号/日期唯一账本，所有外部操作继续通过 operations.lock；没有独立平台写通道。

**Tech Stack:** Python/FastAPI/SQLite/Pydantic，原生 JS UI。

**Spec:** 本次会话父助手批准的设计与补充字段路径。

## Global Constraints
- 不读真实 .env/data/profile、私有快照，不连接真实实例，不 commit/push/部署。
- 默认关闭；Asia/Shanghai 默认09:00，仅计划分钟 tick，错过不补发。
- 不消费历史 approved；未知结果停止后续日期；恢复撤销策略。
- ACK 缺证不猜；付款、退款、确认收货永久人工。

## 执行顺序
- [x] RED：真实模板无顶层 onlyTakeSelf、整数 divisionId、标题/描述偏差不能确认。
- [x] GREEN：publish_preview.py/publish_executor.py 增加显式内容契约、精确传输与回读。
- [x] RED：tests/test_daily_publish.py 覆盖管理员权限、证据门槛、时区分钟、去重、未知停止、快照变更、恢复。
- [x] GREEN：daily_publish.py；db.py v13；app.py 管理员接口；执行器逐阶段策略检查。
- [x] CLI 通过显式管理员 HTTP 配置/撤销/tick，绝不建立第二数据库 worker；UI 使用既有安全 textContent/JSON 输入风格。
- [x] 全量 pytest、pip check、ruff、node、隔离 UI、diff；整理当前文档与未完成证据清单。

不安装宿主调度器；不把 fixture 当真实启用证据。所有测试独立临时数据。
