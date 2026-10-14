# 部署说明

文档导航：[仓库首页](../README.md) · [本地开发交接/未完成清单](DEVELOPMENT_HANDOFF.md) · [MCP 接入](MCP.md) · [测试记录](TEST_REPORT.md)。

## 1. 推荐落地方式

首次真实联调选 Windows 本机：工作台、Python 3.12 虚拟环境、系统 Chrome、Node.js 在同一个操作系统会话中。无需显卡。代码仍声明 >=3.11，但目前完整开发依赖尚未兼容验收 3.11，先独立使用 3.12；不要修改其他项目的 Python 环境。不要把 Windows 和 WSL 的浏览器 Cookie 数据库当作可自动互通。

仓库 README 给出 Windows / Linux 演示安装命令。`init` 仅首次运行，生成 `.env`；重复运行会拒绝覆盖，避免丢失加密密钥。服务默认绑定 `127.0.0.1:8099`，只启动一个进程。不要使用 `uvicorn --workers 2` 或多副本；单实例文件锁会拒绝第二个实例。

### 已知安装问题：Python 3.11

首轮 CI 的 Windows 和 Ubuntu 3.11 作业均在安装 `requirements-dev.lock` 时失败；Windows 日志明确显示 `pyee==14.0.0` 要求 Python >=3.12。3.12 的基础测试、固定上游契约与演示页面交互作业已通过。修复任务见交接清单 **P0-ENV**，本次文档更新没有修改锁文件或解决该兼容问题。

现有 `requirements.lock` 不含 pyee；这个结果不等于所有 3.11 基础演示都无法运行，但完整开发/live 组合不能宣称已通过。安装示例已统一为 3.12。旧虚拟环境若为 3.11，另建干净 3.12 环境并替换命令路径；不要删除 `.env` 或 data 来重建环境。

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

安装系统 Chrome 和 Node.js，并确保 Node 可在当前服务进程的 PATH 中运行。系统 Chrome 不是 Playwright 自带的测试 Chromium，两者用途不同。运行 `xianyu-workbench doctor` 只检查依赖，不访问闲鱼。Windows 上 Chrome 可能不在 PATH，doctor 也会明确提醒人工确认。

首次登录由账号主人自己在浏览器完成。导入对象应是本人闲鱼登录态的 JSON：可以是 name/value 数组，也可以是键值对象；需要 unb 与 _m_h5_tk。数组包含域名时只接受 goofish.com / taobao.com 的相关域。不要使用来历不明的登录态导出扩展。工作台不会自动扫描本机浏览器。

在设置 `XY_LIVE_ENABLED=true` 并重启后，新增真实账号并导入。验证顺序：一次搜索 → 一次商品详情 → 会话列表 → 已有会话历史 → 审批一条低风险咨询 → 人工在闲鱼核对 → 最后单条商品发布。

上游发消息目前不能证明送达。没有会话时先在闲鱼人工联系，不要使用伪造 cid。删除可能永久生效，不应拿重要商品测试。平台要求验证码/验证时立即停，不提供绕过或频繁重试逻辑。

## 4. WSL / Linux 图形环境

工作台本身可在 Ubuntu/WSL 无桌面运行演示与管理页面，但上游真实搜索默认需要可见 Chrome。WSL 需有可用 WSLg/显示环境，并在 WSL 内安装 Linux Chrome 和 Node。Linux 无桌面服务器没有显示环境时，本版不承诺真实搜索、详情可运行。

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

升级前备份，运行测试，再启动单实例。首版数据库使用 create-if-not-exists 初始化，还没有多版本迁移框架；未来改变表结构必须补显式迁移。正在执行的写操作随服务崩溃后会标记 unconfirmed，不会自动重放。

账号暂停只阻止后续操作，不能撤销已在网络上发出的请求。结果不确定时先在闲鱼确认，不要重新建一个同内容操作来碰运气。
