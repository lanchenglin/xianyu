# 部署说明

文档导航：[仓库首页](../README.md) · [本地开发交接/未完成清单](DEVELOPMENT_HANDOFF.md) · [MCP 接入](MCP.md) · [测试记录](TEST_REPORT.md)。

## 1. 推荐落地方式

默认支持 Linux / WSL，使用 Python 3.11/3.12；推荐工作台、虚拟环境、系统 Chrome/Chromium、Node.js 位于同一个操作系统会话中。无需显卡。Windows 原生支持暂停：`53400f8` 的 CI run 38727928186 中 Windows 3.11/3.12 失败，Linux 双版本、双 upstream-contract 和 browser-smoke 通过，详见[测试记录](TEST_REPORT.md)。独立分支 `work/windows-support-53400f8` 保存快照 `53400f82f1ce4f1b1322f184b4b15e2e2c949e97`，当前分支不继续修 Windows。新的 Linux CI 全绿不代表 Windows 支持恢复。不要修改其他项目的 Python 环境，也不要把 Windows 和 WSL 的浏览器 Cookie 数据库当作可自动互通。

仓库 README 给出 Windows / Linux 演示安装命令。`init` 仅首次运行，生成 `.env`；重复运行会拒绝覆盖，避免丢失加密密钥。服务默认绑定 `127.0.0.1:8099`，只启动一个进程。不要使用 `uvicorn --workers 2` 或多副本；单实例文件锁会拒绝第二个实例。

### Python 3.11 兼容修复

首轮 CI 的 pyee 14 安装失败已本地复现并修复：Playwright 1.64 在 3.11 使用 pyee 13.0.1，在 >=3.12 使用 14.0.0。两份锁均以 `uv pip compile ... --universal --python-version 3.11` 生成；不要省略 Python 下限。Linux 两版本干净安装、`pip check`、完整固定 live 测试通过。当前 CI tests 仅运行 Ubuntu 3.11/3.12，保留依赖一致性检查、双版本固定 live 契约和 Linux browser-smoke；跨平台源码与回归不删除。Windows 历史 CI 结果不作为当前支持承诺。

安装示例仍使用 3.12，也可在独立 3.11 环境安装当前锁文件。不要删除 `.env` 或 data 来重建环境。

## 2. 配置项

| 配置 | 说明 |
|---|---|
| XY_ADMIN_TOKEN | 人工控制台令牌，随机生成；可以审批和配置账号 |
| XY_AGENT_TOKEN | 只给 AI 的令牌，不可审批、改配置或导出 Cookie |
| XY_VAULT_KEY | Fernet 数据加密密钥，必须独立妥善备份 |
| XY_DATA_DIR | 数据目录，默认当前工作目录的 data |
| XY_LIVE_ENABLED | 默认 false；真实查询和写操作全部关闭 |
| XY_WORKER_ENABLED | 是否运行审批执行队列与搜索监控；默认 true |
| XY_OPERATION_TIMEOUT | 上游单次操作超时，默认 120 秒 |
| XY_ALLOWED_HOSTS | 允许访问的主机名/IP，逗号分隔；默认为本机 |
| XY_UPSTREAM_PYTHON | 可选上游 Python 可执行文件完整路径；此环境也必须安装本工作台和固定 live 依赖 |

读取 `.env` 后不会覆盖已设置的系统环境变量。诊断配置异常时同时检查系统环境。不要把整个配置文件交给 Hermes。

## 3. 真实连接

在同一工作台虚拟环境安装 `pip install -e '.[live,mcp]'`。固定 Git 提交来自 pyproject.toml，不需要再次安装一个版本不明的 `goofish-cli` PyPI 包。

安装系统 Google Chrome 或 Chromium 和 Node.js，并确保 Node 可在服务 PATH 中运行。项目管理的适配在 bridge 子进程安装，不修改固定上游。auto 启动前优先 Chrome、否则 Chromium；显式选择/路径失效不回退，运行失败不启动另一个浏览器。doctor 检查 PATH 及标准安装目录，仅读取已导出的环境配置，不读取 .env、不连接 CDP 或登录态。

浏览器管理员变量：`XY_BROWSER=auto|chrome|chromium`、`XY_BROWSER_EXECUTABLE`（可选绝对路径）；可选 `XY_BROWSER_CDP_ENDPOINT` + `XY_BROWSER_CDP_ACCOUNT_ID` + `XY_BROWSER_CDP_UID` 三项绑定唯一账号。CDP 仅 loopback 且仅 search，其余操作拒绝，不注入 Cookie、不关闭用户浏览器。完整配置示例、隔离/清理、WSLg 和 snap 限制、CDP 端口安全见 [浏览器适配约束](BROWSER.md)。这些变量不是 Agent/MCP 参数。

首次登录由账号主人自己在浏览器完成。导入对象应是本人闲鱼登录态的 JSON：可以是 name/value 数组，也可以是键值对象；需要 unb 与 _m_h5_tk。数组包含域名时只接受 goofish.com / taobao.com 的相关域。不要使用来历不明的登录态导出扩展。工作台不会自动扫描本机浏览器。

在设置 `XY_LIVE_ENABLED=true` 并重启后，新增真实账号并导入。验证顺序：一次搜索 → 一次商品详情 → 会话列表 → 已有会话历史 → 审批一条低风险咨询 → 人工在闲鱼核对 → 最后单条商品发布。

上游发消息目前不能证明送达。没有会话时先在闲鱼人工联系，不要使用伪造 cid。删除可能永久生效，不应拿重要商品测试。平台要求验证码/验证时立即停，不提供绕过或频繁重试逻辑。

## 4. WSL / Linux 图形环境

工作台本身可在 Ubuntu/WSL 无桌面运行演示与管理页面，但真实搜索默认需要可见 Chrome/Chromium。WSL 需有可用 WSLg/显示环境，并在 WSL 内安装 Linux Chrome 或 Chromium 和 Node。Linux 无桌面服务器没有显示环境时，本版不承诺真实搜索、详情可运行。

不建议第一步就自行拼 Windows 浏览器 + WSL 子进程 + 远程网关。先在一个系统中跑通，再考虑增加独立浏览器服务适配。代码没有偷偷回退到另一个账号、另一个浏览器或另一个网关。

## 5. Docker

首版 Docker 镜像面向演示、审批后台和 MCP API；没有安装真实连接所需的 Chrome/Node/live 依赖，compose 强制关闭真实模式。

先按 README 在本机生成 `.env`，然后：

```bash
docker compose up -d --build
docker compose logs --tail=100 workbench
```

访问 `http://127.0.0.1:8099`。使用命名卷 `workbench-data` 保存数据，不会把 `.env` 打进镜像。运行用户为 10001，drop all capabilities。容器内部 `/app/data` 所属用户已预设；不要直接换成 root 拥有的空宿主机 bind mount 后忽略权限报错。

```bash
docker compose down
```

不要加 `-v`，除非确实要删除所有数据。Docker 构建与真实浏览器环境应在自己的部署机再次验收；本次开发环境的测试记录以 TEST_REPORT 为准。

## 6. 手机与远程访问

手机界面已做响应式布局。仅在可信网络访问，不要把裸 HTTP 管理口直接开放公网。远程通过 HTTPS 反向代理或可信隧道转发到本地 8099，并把实际域名加入 XY_ALLOWED_HOSTS。HTTP 仅支持 localhost 本机通信。修改绑定地址时需同时考虑防火墙和主机名校验。

管理员令牌在当前页面内存中，刷新后需重登。静态资源本地提供，无第三方 CDN、跟踪脚本或网页 Cookie 登录。

## 7. 备份、升级与停机

备份前正常停止工作台，再分别备份 `.env` 与完整数据卷/目录。只复制正在写入的 workbench.db 而忽略 WAL 不保证一致性。丢失 XY_VAULT_KEY 后无法恢复加密内容。

升级前正常停机并完整备份，运行测试，再启动单实例。数据库现以 `PRAGMA user_version` 显式版本化；旧版无版本数据库视为 v0，按顺序升级 v1 基础表、v2 人工核对表。迁移与服务使用同一个 `server.lock`；未知未来版本拒绝打开。已有数据库升级前在 `data/backups/before-v*-<随机ID>.db` 创建 SQLite backup API 一致性快照（包含已提交 WAL），备份失败停止升级，迁移结构/数据/版本号在同一事务中回滚。没有版本变化时不重复备份。

启动在迁移前校验已有加密字段；密钥不匹配或密文损坏明确失败，不清空数据。没有任何加密记录的旧空库无法证明历史密钥身份。快照只包含数据库，不包含素材、配置、密钥或运行目录，不是完整灾备；仍需停机备份完整 data，并将原 `XY_VAULT_KEY` 离线分开保护。POSIX 数据目录 0700、数据库与快照 0600；Windows 需另配 ACL。备份含未加密的审计/商品等元数据，需要与原数据同等级保护。

本轮**没有恢复 CLI、自动定时备份、保留/清理策略**。不要热替换数据库或只覆盖 db 而保留旧 WAL。恢复需停机、保留现状副本、在隔离目录使用原密钥验收，人工复核旧 `approved` 待执行任务后再启动工作队列；不要将历史快照当作可自动重放的任务源。正在执行的写操作在服务重启后标记 unconfirmed，不会自动重放。

账号暂停只阻止后续操作，不能撤销已在网络上发出的请求。结果不确定时先在闲鱼确认，不要重新建一个同内容操作来碰运气。

## 8. 人工核对操作

管理员打开“操作审批”，在 `unconfirmed/submitted/blocked` 原操作上点击“记录人工核对”。表单固定显示原账号、操作 ID、演示/真实模式和原状态；选择“观察到相关平台记录 / 未观察到相关记录 / 仍无法判断”，填写必要证据摘要后保存。证据加密保存，仅管理员可读；Agent 只见人工结论/时间。

每操作仅一次不可覆盖记录，请谨慎填写；重复网络请求须用同一幂等键/内容，冲突显示错误并应刷新查看原记录，不可换键覆盖。核对不会修改原状态、重启操作、解除暂停，也不证明送达或已读。上游无可靠回执时只能记录人工证据，不能伪造自动验证。

## 2026-10-15 续开发状态更新

基线 `4d2aadc` 的 [CI run 38566392741](https://github.com/lanchenglin/xianyu/actions/runs/38566392741) 全部 7 作业成功：Ubuntu/Windows 3.11/3.12、双版本固定 live 契约及 UI。这是历史基线结果，不代表当前 Windows 支持或真实账号验收；最新 `53400f8` 的 Windows 双版本失败及暂停决定以上文支持声明和测试报告为准。

固定上游五项核实见 [静态可行性报告](UPSTREAM_FEASIBILITY.md)。真实发布因不能冻结类目/地点暂时禁用（live_publish=false）；本地草稿、演示发布和审批申请保留。禁止用默认值变化后的上游发布代替完整审批。

### P2-04 本地离线恢复增量（2026-10-15）

已提供管理员离线 `backup` / `restore --offline` CLI：一致性数据库+素材、密钥/manifest/hash 校验、受限解包、活动实例拒绝、异常回滚和中断启动保护。恢复暂停账号/监控，pending/approved 失效、running 转不确定，旧任务不重放。无 HTTP/MCP 恢复能力，Agent 不可操作任意文件。详见 [备份说明](BACKUP.md)。此前“无恢复 CLI”为历史状态；定时/保留策略仍未实现。

### P2-02 单条草稿管理（2026-10-15）

已实现单条原位编辑、revision 乐观并发保护和归档 UI；显式 v2→v3 迁移增加 revision=1 / archived=0，保留原内容。PUT `/api/drafts/{id}` 接受原 account_id、revision 和完整草稿字段；POST `/api/drafts/{id}/archive` 接受 account_id、revision。账号/旧版本/已归档冲突返回 409，不另建副本；归档非平台删除，修改不会改变已冻结审批。管理员和 Agent 均可操作安全本地草稿，无新增管理员权限或任意文件操作。未增加 MCP 编辑工具（HTTP/UI 可用），既有 MCP 保存工具保持新建语义。没有素材删除接口，所有引用图片保留。批量发布、素材回收、取消归档尚未实现。
