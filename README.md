# 闲鱼 AI 工作台

**搜索与比价、询价/客服草稿、商品发布审批、本地商品管理、搜索监控，以及 Hermes / Claude / Codex 的 MCP 接口。**

面向账号主人自用的本地 Web 应用。中文界面，支持桌面和手机浏览器；无需 MySQL、Redis、GPU 或 Node 前端构建。后台使用 FastAPI + SQLite，真实连接使用固定提交的 `goofish-cli-redux`。

> **这是 v0.1.0 工程首版，不是已在你的闲鱼账号验收的全自动店铺系统。** 默认关闭真实执行。演示数据明确标记，不伪装成真实商品或成功操作。付款、下单、退款、确认收货及其他交易动作没有执行接口，必须本人在闲鱼完成。

## 文档入口与本地续开发

| 你要做什么 | 文档 |
|---|---|
| 在本地继续开发未完成功能 | [开发交接与未完成清单](docs/DEVELOPMENT_HANDOFF.md)（优先级、代码入口、验收条件、给 AI 的续开发指令） |
| 安装、启动、导入真实账号、Docker / WSL | [部署说明](docs/DEPLOYMENT.md) |
| 接入 Hermes / Claude / Codex 或 HTTP API | [接入说明](docs/MCP.md) |
| 查看实际测试与 CI 状态 | [测试报告](docs/TEST_REPORT.md) |
| 让 AI 修改代码前了解约束 | [AGENTS.md](AGENTS.md) 与 [安全边界](docs/SECURITY.md) |

**默认支持 Linux / WSL，Python 3.11 / 3.12，本地示例使用 3.12；Windows 原生支持暂停。** `53400f8` 的 [CI run 38727928186](https://github.com/lanchenglin/xianyu/actions/runs/38727928186) 中 Linux 双版本、双版本 upstream-contract 和 browser-smoke 通过，Windows 3.11/3.12 失败。Windows 快照保存在独立分支 `work/windows-support-53400f8`（`53400f82f1ce4f1b1322f184b4b15e2e2c949e97`）；当前分支仅保留 Linux CI 门槛，不删除跨平台源码或回归。后续 Linux 全绿不代表 Windows 支持恢复；历史成功与失败见[测试报告](docs/TEST_REPORT.md)。

## 2026-10-16 有界页面读取

买到订单与本人发布列表支持固定任务页有界滚动、多页去重和持久进度；订单末页字符串仍未获证，保持 partial。本人发布列表仅在已证布尔末页时 complete；卖出订单、下架列表、全状态库存未实现。历史缓存不冒充完整快照。响应早于 DOM/hook 的时序改用 750ms 有界等待/滚动，加载中不滚动；真实工作台 API 修复效果待父助手复测，不扩大能力范围。迁移与取证需求见 [分页边界](docs/OPERATION_PAGINATION.md)。

## 能力与边界

| 功能 | 本版实现 |
|---|---|
| 商品搜索、价格/地区过滤、去重 | 已实现；过滤本次返回样本，不保证全平台覆盖 |
| 商品详情、已有会话、消息历史 | 已接固定上游接口；依赖账号登录态及页面状态 |
| AI 起草询价、回复、商品文案、对比分析 | 已实现；可配置兼容 Chat Completions 的模型，也可由 Hermes 直接完成 |
| 主动向已有会话发送消息 | 已接入；核对会话与收件人后，必须经人工审批 |
| 上传图片、发布申请 | 本地/演示可用；真实发布因上游无法冻结类目/地点暂不开放 |
| 删除商品 | 明确标注可能不可恢复，需确认文字与归属校验；**不冒充普通下架** |
| 本地草稿和商品台账 | 草稿原位编辑、revision 冲突保护、归档；台账不是平台全量库存 |
| 搜索监控、去重与通知 | 最低 5 分钟；站内已读/归档；管理员可启用钉钉/受限 webhook 固定摘要，默认关闭，见[通知说明](docs/NOTIFICATIONS.md) |
| 操作审批、幂等、单队列、审计、风控暂停 | 已实现；超时或中断的写操作不会自动重发 |
| 不确定操作的人工核对 | 管理员记录一次结论/时间/加密证据；保留原执行状态，不等于送达或已读，不重试 |
| 数据库迁移与离线灾备 | 显式 v0→v10（含通知、加密只读样本表及有界分页进度）；管理员 CLI 备份数据库+素材、安全暂停恢复；无定时/保留策略 |
| 多账号 | 每账号独立登录态和运行目录；禁止跨账号覆盖 Cookie |
| MCP / HTTP API | 已实现；MCP 只接受 Agent 令牌，没有审批、凭据或交易工具 |
| 陌生卖家首次建会话 | **未开放**；先人工在闲鱼建立会话，再回到工作台 |
| 平台改价、普通下架/重新上架、全量库存同步 | **未实现**；只保留本地管理，不返回虚假成功 |
| 买到订单 / 本人发布列表有界分页 | **已实现代码，工作台分页 API 真实验收未完成**；订单未知末页保持 partial；商品仅 `self_published` 页面范围可 complete，不等同全状态库存；加密缓存、API/UI/MCP，`partial_orders/partial_inventory=true`，完整同步能力仍 false；[分页契约](docs/OPERATION_PAGINATION.md) |
| 会话末条消息样本 | `partial_messages=true`；CDP 被动 WS、加密缓存、HTTP/UI/MCP；严格解码已验证普通文本，核验双方后可按需生成本地模板草稿；不提案/发送，非历史/实时聊天，真实未验收，见[消息契约](docs/MESSAGES.md) |
| 低频消息采集 / 人工接管 | 默认关闭、最短 5 分钟、同一 worker、持久去重与失败退避；只是末条样本不是完整历史。API/UI/MCP，见[观察契约](docs/MESSAGE_OBSERVATION.md) |
| 管理员有限 FAQ 策略 | 默认关闭；加密商品+会话范围、固定模板、期限、频率与撤销；发送适配未接入，策略永不触发发送，`autonomous_reply=false` |
| 完整订单同步、实时自动客服、自动议价成交 | **未实现**；样本不等于完整订单/全状态库存；消息仍按需读取、起草、审批发送 |
| 支付、购买、退款、确认收货 | **不提供，永久保留人工执行** |

上游的 `message.send` 返回 `mid`，不等于已验证送达；工作台将真实发送结果记为 **unconfirmed / 结果待核实**。发布返回有效商品 ID 后记为 **submitted / 上游已接受**，不宣称已经展示给所有用户。未知状态不能靠反复点击重试解决。管理员可在“操作审批”中对 `unconfirmed/submitted/blocked` 记录人工核对；结论只表示人工观察，原执行状态/结果不会被覆盖。每操作仅一次不可覆盖记录，相同请求幂等、冲突 409；Agent 只能查看结论/时间，不能核对或读取证据正文。

## 先跑通演示

代码声明 Python 3.11+；本轮验证 3.11 和 3.12，以下安装示例统一使用 Python 3.12。使用独立虚拟环境，不覆盖其他项目的 Python 环境。

### Windows PowerShell（历史参考，支持暂停）

以下命令仅保留作独立 Windows 分支的参考，不是当前推荐部署路径；新安装请使用下方 Linux / WSL 步骤。

```powershell
git clone https://github.com/lanchenglin/xianyu.git
cd xianyu
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install --no-deps -e .
.\.venv\Scripts\python.exe -m xianyu_workbench.cli init
.\.venv\Scripts\python.exe -m xianyu_workbench.cli serve
```

在本机打开 `http://127.0.0.1:8099`。自行打开本地 `.env`，复制 `XY_ADMIN_TOKEN` 登录工作台；不要把整个 `.env` 发给 AI、提交 Git 或贴进聊天。

在“账号管理”添加**演示账号**，随后可搜索、上传一张图片、保存草稿、提交发布审批、批准并观察“演示完成”。这些动作都不会访问闲鱼。

### Linux / WSL

```bash
git clone https://github.com/lanchenglin/xianyu.git
cd xianyu
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps -e .
.venv/bin/python -m xianyu_workbench.cli init
.venv/bin/python -m xianyu_workbench.cli serve
```

也可以不使用锁文件，直接安装 `pip install -e '.[mcp]'`；但依赖可能随时间变化。锁文件记录本次验证的依赖版本。

## 接入真实闲鱼

先阅读 [部署说明](docs/DEPLOYMENT.md) 和 [安全边界](docs/SECURITY.md)。真实搜索支持**系统 Google Chrome 或 Chromium 和可显示窗口的会话**，由项目 bridge 适配自动发现或管理员显式指定；可选固定账号 loopback CDP 仅允许 search、orders 买到订单有界分页、inventory 本人发布列表有界分页、messages 会话末条样本（非完整历史）；item/chats/history 与所有写操作拒绝，详见 [浏览器设计与配置](docs/BROWSER.md)。真实接口中的签名逻辑需要 Node.js。

```bash
# Linux / WSL：与工作台使用同一个虚拟环境
.venv/bin/python -m pip install -e '.[live,mcp]'
.venv/bin/python -m xianyu_workbench.cli doctor
```

由你安装系统 Google Chrome 或 Chromium、Node.js，完成闲鱼网页登录，导出自己账号的 Cookie JSON，再通过工作台“账号管理”导入。工作台不会扫描你所有浏览器的 Cookie，不会自动换号或尝试绕过验证码。

在 `.env` 中将 `XY_LIVE_ENABLED=false` 改为 `true`，重启服务，新增真实账号并导入。CDP 模式仅验证上述白名单只读范围，不测试详情、完整会话历史或任何写操作；隔离模式的既有接口须另行逐项验收，写操作仍需人工审批，真实发布继续禁用。遇到验证或风控会暂停账号，需本人处理后恢复。

**推荐在 Linux / WSL 同一环境运行工作台、Chrome/Chromium 和上游依赖；Windows 原生联调暂停。** WSL 的实际浏览器也必须位于同一 WSL 环境并有可用图形显示；不能假设 WSL 能直接使用 Windows 的浏览器登录态。首版 Docker 镜像只提供演示/管理/MCP，不承诺无头服务器真实搜索可用。

## 接入 Hermes / Claude / Codex

详细配置见 [MCP 接入](docs/MCP.md) 和 [随仓库 Skill](skills/xianyu-workbench/SKILL.md)。

```json
{
  "mcpServers": {
    "xianyu-workbench": {
      "command": "/你的路径/xianyu/.venv/bin/xianyu-mcp",
      "env": {
        "XY_API_URL": "http://127.0.0.1:8099",
        "XY_AGENT_TOKEN": "只填本地生成的 Agent 令牌，不是管理员令牌"
      }
    }
  }
}
```

这里是通用 stdio MCP 客户端配置示例，不代表某个 Hermes Desktop 版本的配置文件位置或字段已实测。远程 Hermes 网关应在**对应远程机器**上启动 MCP，并明确工作台地址。不会自动切到其他网关。

你可以对 AI 说：

> 使用 xianyu-workbench，先查看账号和能力。帮我找福州 2000 元以内的显卡，列出候选和需要核实的问题。询价只提交草稿审批，不承诺成交，不付款；演示结果必须注明是模拟数据。

## 开发与测试

从 [本地开发交接](docs/DEVELOPMENT_HANDOFF.md) 开始；其中明确区分未实现、代码已接入但未实测、以及永久保留人工的交易操作。以下使用已激活的 Python 3.12 虚拟环境。

```bash
python -m pip install -e '.[dev,mcp,live]'
ruff check .
pytest -q
```

上游依赖固定在 `E-R-Butch/goofish-cli-redux@c2d5a02ad83b18863514389cedf7afbd993b683d`。`tests/test_upstream_contract.py` 检查该版本函数契约，**不登录、不请求闲鱼、不执行真实写操作**。基础测试不安装 live 依赖时会跳过上游契约测试。

页面交互烟雾测试及 CI 见 `scripts/smoke_ui.py`、`.github/workflows/ci.yml`；运行前需按脚本说明安装测试浏览器。测试报告见 [验收记录](docs/TEST_REPORT.md)。

## 工程结构

```text
xianyu_workbench/
  app.py              HTTP API、鉴权和上传
  service.py          审批、队列、幂等、搜索监控、AI 草稿
  provider.py         账号隔离、上游子进程、限流与错误处理
  bridge.py           固定白名单的上游函数桥，不开放通用命令执行
  security.py         凭据加密、摘要、日志脱敏
  db.py               SQLite 持久化
  mcp_server.py       Agent-only stdio MCP
  static/             中文响应式前端，无 CDN 和第三方脚本
scripts/              环境与页面测试
skills/               给 AI 使用的操作规范
```

本项目不把第三方项目捆成多个竞争账号控制权的进程；采用“一个工作台、一套审批、一条执行队列、一个固定上游适配器”。未来接入其他运营后台时也必须服从同一个写队列，而不是同时启用多个自动回复程序。

## 数据与凭据

登录态、模型 API Key、操作内容、执行结果和本地草稿加密存储；完整聊天历史按需读取，不自动持久化；messages 会话末条样本及按需本地模板草稿加密缓存，低频末条采集默认关闭。素材、公开商品台账、监控结果与审计元数据仍是本地文件/SQLite 数据，详见安全说明。执行期间浏览器必须使用可读登录态，临时 Cookie 与浏览器 profile 在正常结束和服务启动时清理；异常断电不能提供“从未落过明文”的保证。

`.env` 中的 `XY_VAULT_KEY` 丢失后，已有加密数据不可恢复。数据库已支持显式版本迁移、升级前一致性快照与失败事务回滚；错误密钥/未来版本拒绝启动。快照不含素材和密钥，不等于完整备份；已有管理员离线 backup / restore CLI，恢复会暂停账号并使旧待执行授权失效；暂无定时备份或保留策略。务必将配置和完整数据分别备份，步骤见部署说明；持有同一系统用户权限或整台机器控制权的 AI 不构成真正的权限隔离。

## 许可

本项目 MIT；上游依赖为 Apache-2.0，详见 [第三方声明](THIRD_PARTY_NOTICES.md)。遵守平台规则和账号授权边界；不保证平台接口长期稳定，也不提供验证绕过、批量骚扰或自动交易能力。

## 2026-10-15 续开发状态更新

基线 `4d2aadc` 的 [CI run 38566392741](https://github.com/lanchenglin/xianyu/actions/runs/38566392741) 全部 7 作业成功：Ubuntu/Windows 3.11/3.12、双版本固定 live 契约及 UI。这是历史基线结果，不代表当前 Windows 支持或真实账号验收；最新 `53400f8` 的 Windows 双版本失败及暂停决定以上文支持声明和测试报告为准。

固定上游五项核实见 [静态可行性报告](docs/UPSTREAM_FEASIBILITY.md)。真实发布因不能冻结类目/地点暂时禁用（live_publish=false）；本地草稿、演示发布和审批申请保留。禁止用默认值变化后的上游发布代替完整审批。

### P2-04 本地离线恢复增量（2026-10-15）

已提供管理员离线 `backup` / `restore --offline` CLI：一致性数据库+素材、密钥/manifest/hash 校验、受限解包、活动实例拒绝、异常回滚和中断启动保护。恢复暂停账号/监控，pending/approved 失效、running 转不确定，旧任务不重放。无 HTTP/MCP 恢复能力，Agent 不可操作任意文件。详见 [备份说明](docs/BACKUP.md)。此前“无恢复 CLI”为历史状态；定时/保留策略仍未实现。

### P2-02 单条草稿管理（2026-10-15）

已实现单条原位编辑、revision 乐观并发保护和归档 UI；显式 v2→v3 迁移增加 revision=1 / archived=0，保留原内容。PUT `/api/drafts/{id}` 接受原 account_id、revision 和完整草稿字段；POST `/api/drafts/{id}/archive` 接受 account_id、revision。账号/旧版本/已归档冲突返回 409，不另建副本；归档非平台删除，修改不会改变已冻结审批。管理员和 Agent 均可操作安全本地草稿，无新增管理员权限或任意文件操作。未增加 MCP 编辑工具（HTTP/UI 可用），既有 MCP 保存工具保持新建语义。没有素材删除接口，所有引用图片保留。批量发布、素材回收、取消归档尚未实现。
