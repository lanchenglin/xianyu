# 发布审查与当前能力整理计划

**目标：** 在 f8d1ad8 上复核执行器，最小修复可复现缺陷，整理当前能力正文并补离线恢复可靠性回归。

**架构：** 沿用唯一 actions 队列、现有加密快照与离线恢复，不新增平台接口或 schema。执行器模板比较使用现有 canonical JSON 工具，避免 Python bool/int 相等掩盖类型变化。

**约束：** 本会话原地执行，不切分支、不提交、不 push、不部署；不读取真实 .env/data/profile/私有快照，不连接8099/9235；不动 scratch。测试仅临时虚构数据。

- [x] 审查 publish_executor/publish_preview/service/provider/bridge 与 f8d1ad8 回读契约测试。
- [x] 在 tests/test_publish_review.py 参数化配送布尔值被数字替代的预览拒绝测试，运行确认 201 而非 409 的 RED；将模板比较改为 canonical(actual) != canonical(value)，复跑。
- [x] 在 tests/test_publish_backup.py 使用临时真实 SQLite/归档，覆盖 prepared/uploading/submitting/verifying/verified 阶段恢复、私密字段保留与 Agent 投影、旧审批失效且恢复账号后不重放。这是补充回归，若首次通过不声称 RED。
- [x] 重写 DEVELOPMENT_HANDOFF 当前正文及 OPERATIONS_NEXT 待办，建立与 app.py capabilities 对齐的实现/隔离测试/平台验收/阻塞矩阵；README、AGENTS 与相关专项文档直接修正旧声明。历史测试证据留在 TEST_REPORT，不覆盖 FAIL。
- [x] 使用 .venv、env -u PYTHONPATH、指定 TMPDIR 与独立浏览器缓存运行 pip check、ruff、全量 pytest（完整 summary）、smoke_ui、node --check、git diff --check，记录真实结果与未验收边界。
