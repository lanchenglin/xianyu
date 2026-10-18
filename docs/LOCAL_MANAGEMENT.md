# 本地草稿、素材与批量导入

这些接口不访问平台，不改变 FAQ/逐条审批策略。取消归档、导入与逐条申请允许管理员/Agent；素材永久删除仅管理员。

## 取消归档与素材回收

- POST `/api/drafts/{id}/unarchive`：`{account_id,revision}`，仅当前归档版本可恢复；成功 revision+1，冲突409；不改变历史审批。
- GET `/api/accounts/{account_id}/assets`：最多200条 id/account_id/sha256/created/referenced，不返回文件路径。
- POST `/api/assets/{id}/recycle`：管理员提交 `{account_id,sha256,confirm:"永久删除未引用本地素材"}`。
- 所有草稿（包括归档）、所有历史 actions 的 payload/result、加密 settings 都参与引用保护；密文损坏不当作无引用。审批过期/拒绝不是删除素材授权。
- 引用检查和删除登记在 SQLite 写事务内；草稿新建/编辑及 action 创建在写事务中再次验证图片。先删除登记再删文件：中断可能留下未登记孤立文件，但不会留下已登记悬空素材。孤立文件不自动扫描删除；人工文件修复不在 HTTP/MCP 范围。
- UI 提供取消归档、候选查询和逐张输入确认删除；MCP 只有恢复和候选查询，没有删除工具。

## 批量本地导入

POST `/api/draft-import/preview`：`{account_id,rows:[{title,desc,price,images,...}],idempotency_key}`。1～50行，字段沿用 DraftIn；每行禁止 account_id，图片须本账号已有 ID，无路径/URL导入。预览不持久化，返回规范化 rows/digest。

POST `/api/draft-import/confirm`：相同参数加 digest；事务中重新规范化/验证素材，同账号幂等键与摘要唯一，原位重复返回同一批次。只创建草稿，actions 数量不变。批次和草稿关系为 schema v12，正文仍在草稿密文。

GET `/api/accounts/{account_id}/draft-imports` 最近100批；GET `/api/accounts/{account_id}/draft-imports/{id}` 返回每行当前 revision/归档及当前版本对应 action ID/state。

POST `/api/draft-imports/{import_id}/{draft_id}/propose`：`{account_id,revision}`，仅一条。复用本地发布冻结链，需管理员已设置发布默认值、完整发布字段及素材；稳定 `import:<draft_id>:<revision>` 幂等键。管理员仍到唯一队列逐条审批，live 仍需单 action 指定执行。编辑后的版本显示尚未申请，不删除或改写旧 action；旧 action 仍在审批队列可见。

UI 入口在本地草稿列表，JSON文本预览、确认导入、批次逐条进度；MCP 提供预览/确认/进度/单条申请，不提供批量批准或批量执行。
