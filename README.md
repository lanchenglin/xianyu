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

**支持 Python 3.11 / 3.12，本地示例使用 3.12。** 已修复首轮 CI 的 pyee 兼容阻塞：锁文件明确以 3.11 为解析下限，Playwright 1.64 按 Python 版本选择 pyee。Linux 两版本干净安装、pip check、固定 live 契约及 69 项基线测试均通过；修改后的 Windows CI 尚未运行，历史失败记录保留在测试报告。

## 能力与边界

| 功能 | 本版实现 |
|---|---|
| 商品搜索、价格/地区过滤、去重 | 已实现；过滤本次返回样本，不保证全平台覆盖 |
| 商品详情、已有会话、消息历史 | 已接固定上游接口；依赖账号登录态及页面状态 |
| AI 起草询价、回复、商品文案、对比分析 | 已实现；可配置兼容 Chat Completions 的模型，也可由 Hermes 直接完成 |
| 主动向已有会话发送消息 | 已接入；核对会话与收件人后，必须经人工审批 |
| 上传图片、发布商品 | 已接入；图片本地上传、内容冻结、人工审批后执行 |
| 删除商品 | 明确标注可能不可恢复，需确认文字与归属校验；**不冒充普通下架** |
| 本地草稿和商品台账 | 已实现；台账只包含本工作台跟踪/发布的商品，不是平台全量库存 |
| 搜索监控、去重与通知 | 已实现；最低 5 分钟一次，仅工作台内通知 |
| 操作审批、幂等、单队列、审计、风控暂停 | 已实现；超时或中断的写操作不会自动重发 |
| 多账号 | 每账号独立登录态和运行目录；禁止跨账号覆盖 Cookie |
| MCP / HTTP API | 已实现；MCP 只接受 Agent 令牌，没有审批、凭据或交易工具 |
| 陌生卖家首次建会话 | **未开放**；先人工在闲鱼建立会话，再回到工作台 |
| 平台改价、普通下架/重新上架、全量库存同步 | **未实现**；只保留本地管理，不返回虚假成功 |
| 订单同步、实时自动客服、自动议价成交 | **未实现**；当前按需读取消息、起草、审批发送 |
| 支付、购买、退款、确认收货 | **不提供，永久保留人工执行** |

上游的 `message.send` 返回 `mid`，不等于已验证送达；工作台将真实发送结果记为 **unconfirmed / 结果待核实**。发布返回有效商品 ID 后记为 **submitted / 上游已接受**，不宣称已经展示给所有用户。未知状态不能靠反复点击重试解决。

## 先跑通演示

代码声明 Python 3.11+；本轮验证 3.11 和 3.12，以下安装示例统一使用 Python 3.12。使用独立虚拟环境，不覆盖其他项目的 Python 环境。

### Windows PowerShell

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

先阅读 [部署说明](docs/DEPLOYMENT.md) 和 [安全边界](docs/SECURITY.md)。真实搜索依赖**系统 Chrome 和可显示窗口的会话**，真实接口中的签名逻辑需要 Node.js。

```powershell
# Windows：与工作台使用同一个虚拟环境
.\.venv\Scripts\python.exe -m pip install -e ".[live,mcp]"
.\.venv\Scripts\python.exe -m xianyu_workbench.cli doctor
```

由你安装系统 Chrome、Node.js，完成闲鱼网页登录，导出自己账号的 Cookie JSON，再通过工作台“账号管理”导入。工作台不会扫描你所有浏览器的 Cookie，不会自动换号或尝试绕过验证码。

在 `.env` 中将 `XY_LIVE_ENABLED=false` 改为 `true`，重启服务，新增真实账号并导入。首先只验证一次搜索与商品详情，再验证已有会话，最后通过人工审批测试**单条**写操作。遇到验证或风控会暂停账号，需本人处理后恢复。

**推荐初次真实联调在 Windows 本机运行工作台、Chrome 和上游依赖。** WSL 可以运行工作台，但实际浏览器也必须位于同一 WSL 环境并有可用图形显示；不能假设 WSL 能直接使用 Windows 的浏览器登录态。首版 Docker 镜像只提供演示/管理/MCP，不承诺无头服务器真实搜索可用。

## 接入 Hermes / Claude / Codex

详细配置见 [MCP 接入](docs/MCP.md) 和 [随仓库 Skill](skills/xianyu-workbench/SKILL.md)。

```json
{
  "mcpServers": {
    "xianyu-workbench": {
      "command": "C:\\你的路径\\xianyu\\.venv\\Scripts\\xianyu-mcp.exe",
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

登录态、模型 API Key、操作内容、执行结果和本地草稿加密存储；聊天历史按需读取，不自动持久化。素材、公开商品台账、监控结果与审计元数据仍是本地文件/SQLite 数据，详见安全说明。执行期间浏览器必须使用可读登录态，临时 Cookie 与浏览器 profile 在正常结束和服务启动时清理；异常断电不能提供“从未落过明文”的保证。

`.env` 中的 `XY_VAULT_KEY` 丢失后，已有加密数据不可恢复。数据库已支持显式版本迁移、升级前一致性快照与失败事务回滚；错误密钥/未来版本拒绝启动。快照不含素材和密钥，不等于完整备份；暂无恢复 CLI、定时备份或保留策略。务必将配置和完整数据分别备份，步骤见部署说明；持有同一系统用户权限或整台机器控制权的 AI 不构成真正的权限隔离。

## 许可

本项目 MIT；上游依赖为 Apache-2.0，详见 [第三方声明](THIRD_PARTY_NOTICES.md)。遵守平台规则和账号授权边界；不保证平台接口长期稳定，也不提供验证绕过、批量骚扰或自动交易能力。
