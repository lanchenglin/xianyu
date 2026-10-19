# Publish Preview Implementation Record

**Goal:** 按用户已批准设计实现可运行本地发布冻结链，缺证时阻断真实执行。

**Architecture:** 复用 settings 加密默认输入与 actions 唯一审批队列；独立 publish_preview 模块执行快照构造和比较。上游仅静态阅读，不导入主进程；候选 DTO 不是完整平台协议。

**Spec:** 用户本次已批准约束及 docs/PUBLISH_PREVIEW.md。

**Constraints:** 不读真实 .env/data/profile，不连接 8099/9235，不真实写，不改分页，不 push/deploy。固定上游不升级，Python 3.11/3.12。

## 执行记录

- [x] 阅读 AGENTS / OPERATIONS_NEXT / UPSTREAM_FEASIBILITY / 固定 publish builder。
- [x] API 冻结/隐私/默认变化/真实 worker 排除先 RED，再实现 GREEN。
- [x] UI 入口与 MCP discovery 先 RED，再实现 GREEN；实际 Chromium 集成随后验证。
- [x] Provider 旧删除关闭先 RED，再实现；演示保留。
- [x] 复用现有加密字段，无 schema 变化；记录候选协议与真实执行器界限。
- [ ] 真实发布/自动回验：等待管理员类目/配送/地点/上传/ACK 字段证据，不能用上游隐式重算替代。
- [ ] 改价/非删除上下架：等待同 itemId/归属/旧值/非删除转移的实际协议证据；没有猜造接口或 delete/recreate。

本文件是实际执行记录，不是已完成真实商品写的计划承诺。完整本地 API 使用及父助手字段清单见 spec。
