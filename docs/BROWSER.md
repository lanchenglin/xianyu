# 项目浏览器适配与 CDP 安全约束

## 范围与架构

固定上游仍为 `c2d5a02ad83b18863514389cedf7afbd993b683d`，不修改 site-packages。API/MCP 进程只使用配置与发现代码；bridge 在导入上游命令前显式替换 `core.browser.goofish_page`。所有操作保留既有 live 开关、账号暂停、审批、单实例队列、限流、幂等和不确定结果不重放。真实发布继续禁用。

- **隔离启动（默认）**：系统 Google Chrome 或 Chromium，可用于既有上游路径；不是平台业务已验收声明。
- **CDP（可选）**：新增 `messages` 末条元数据样本，固定自建 `/im` 页被动 server-frame 观察，普通文本严格受限解码、pair 核验，按需本地草稿但禁止样本提案/发送，见 [MESSAGES](MESSAGES.md)。保留 `search`、`orders`、`inventory`；后两项仅本人单页部分样本（见 [只读样本契约](OPERATIONS_SAMPLES.md)），不遍历分页。`item`、chats、history 和所有写操作均 fail closed，不回退 mtop、其他浏览器或其他账号。详情当前走独立 mtop 契约，本版不冒充 CDP item 支持。
- 不提供通用 URL、JS、命令、浏览器路径、端点或 profile 的 HTTP/MCP 参数。只有可信本机部署管理员配置环境。

## 管理员配置

| 变量 | 默认 / 含义 |
|---|---|
| `XY_BROWSER` | `auto`；只允许 auto/chrome/chromium |
| `XY_BROWSER_EXECUTABLE` | 空；管理员指定绝对可执行文件路径，优先于发现；无效立即失败 |
| `XY_BROWSER_CDP_ENDPOINT` | 空（关闭）；仅 `http://127.0.0.1:端口` 或 `http://[::1]:端口` |
| `XY_BROWSER_CDP_ACCOUNT_ID` | 空；启用 CDP 必填，工作台账号 id，不是平台 uid |
| `XY_BROWSER_CDP_UID` | 空；启用 CDP 必填，必须与操作账号 uid 和平台 Cookie unb 相等 |

隔离模式示例（不是要求修改现有部署）：

```dotenv
XY_LIVE_ENABLED=false
XY_BROWSER=auto
XY_BROWSER_EXECUTABLE=
XY_BROWSER_CDP_ENDPOINT=
XY_BROWSER_CDP_ACCOUNT_ID=
XY_BROWSER_CDP_UID=
```

CDP 管理员配置示例（端口及账号均为占位示例，不能直接用于真实验证）：

```dotenv
XY_LIVE_ENABLED=false
XY_BROWSER=auto
XY_BROWSER_CDP_ENDPOINT=http://127.0.0.1:9222
XY_BROWSER_CDP_ACCOUNT_ID=workbench-account-id
XY_BROWSER_CDP_UID=12345
```

真实执行必须另由主人批准启用 live。现有账号仍需通过原有管理员导入流程建立 uid/登录态；CDP search 的 provider 不解密导入 secret、不写 cookies.json、不传 GOOFISH_COOKIES_PATH；bridge 在导入命令前禁止 Session.load，阻止默认 profile/Cookie 回读。浏览器现有 unb 是该次操作唯一登录来源，仅用工作台保存的 uid 做绑定校验。CDP 不注入导入的 Cookie，也不从浏览器导出凭据到工作台。非 CDP 模式保持原有临时 Cookie 流程。一个部署只配置一个绑定，其他真实账号在 CDP 模式下不能使用该浏览器。切换配置是管理员部署行为，不是 Agent 重试策略。

## 发现规则与平台

auto 启动前依次发现 Chrome、Chromium；有 Chrome 优先 Chrome，仅 Chromium 则选 Chromium。Linux/WSL 查 PATH 与标准安装位置（包括 snap Chromium），Windows 查 PATH 和 Program Files / LocalAppData 标准安装目录。WSL 使用 Linux 浏览器，不自动寻找 Windows 盘或借用 Windows profile。显式 chrome/chromium 不向另一种回退，显式路径无效也不回退。路径是可信管理员执行权限，不能给模型任意控制。

选定后启动失败、站点失败、登录失效、验证或风控均不启动第二浏览器重试。不修改上游固定依赖，不伪装 chrome 路径，不增加反检测脚本。

每次创建账号隔离 HOME 下 `.goofish-cli/profiles/browser-随机值`，正常退出清理；父进程结束/超时及原有启动恢复继续清理残留。仅加载父进程传入的临时 Cookie 文件，不调用上游浏览器自动提取。不可传个人默认 profile。Windows HOME/USERPROFILE 与 profile 均隔离，部署需保护目录 ACL。

子进程仅白名单继承 PATH、系统程序目录、临时目录、语言、WSLg DISPLAY/WAYLAND_DISPLAY/XDG_RUNTIME_DIR/XAUTHORITY 等运行所需环境；新增浏览器配置由 Settings 显式传入，操作账号 id/uid 由 provider 生成，不继承模型密钥、访问令牌、任意代理配置。

snap 的文件权限/隐藏目录/HOME 限制可能因发行版而异。本次使用 scratch 下全新 HOME 的系统 `/snap/bin/chromium` 隔离测试成功，不代表任意数据目录均可用。失败时管理员应检查权限/显示环境，选用可执行的系统包或独立管理员 CDP 浏览器，不能改用个人 profile、取消账号隔离或自动回退。真实搜索仍默认可见窗口；headless 本地测试不证明平台允许 headless。

## CDP 连接与所有权

1. 配置端点必须是明确 loopback IP、有效端口、可选末尾 `/`。拒绝 localhost 别名、远程、credentials、query、fragment、任意路径及非 http scheme。
2. `/json/version` 使用关闭环境代理、关闭重定向的 HTTP 客户端，5 秒超时、64 KiB 上限；WebSocket 地址必须同协议对应、同 IP、同端口、固定 `/devtools/browser/标识` 路径。
3. Playwright 1.64 内部 WebSocket 连接默认跟随重定向，因此使用短生命周期 loopback TCP 转发门：只连接预先验证的目标，只有 HTTP 101 升级响应才传回；302 等不传给 Playwright。该门不是通用代理，无用户参数，不支持任意目标，退出即关闭。
4. `connect_over_cdp(..., no_defaults=True)`；只接受唯一 context，读取适用于 `https://www.goofish.com/` 的 Cookie 并检查平台域 unb。操作前及成功返回前均校验 uid；缺失、冲突、多 context 都拒绝。不调用 add_cookies，不刷新/替换现有登录态。
5. 创建新任务页，不导航/关闭已有页。结束只关闭任务页。**不调用 browser.close 或 context.close**。退出 Playwright context manager 停止 driver 连接；已对当前固定 Playwright 实测原浏览器与 tab 存活。连接/站点异常无浏览器重试。
6. 正常 operation timeout 先在账号私有运行目录创建单次随机取消标记，bridge CDP 协程每 50ms 检查并只取消一次当前任务，让 task_page finally 关闭自建页、再断开传输。Linux/Windows 共用文件通知，不依赖控制台信号；`XY_BRIDGE_CANCEL_FILE` 由 provider 内部生成，不是管理员/Agent 配置。父进程最多等待 8 秒清理，随后 Linux SIGKILL 进程组或 Windows taskkill /T /F（该命令最多 10 秒），最后回收等待最多 5 秒。超时始终返回 timeout，写操作 uncertain，不接受清理期间的成功结果、不重放。
7. 若事件循环阻塞、浏览器/CDP 断线、清理超过宽限时间、外部强杀或系统断电，不能保证任务 tab 消失；此时只强杀 bridge 进程树，不扫描/关闭可能属于用户的页，管理员人工检查残留。不会向用户浏览器发送 Browser.close。正常超时路径已用独立系统 Chromium 实测，不把强杀兜底宣称为可靠清理。

CDP 端口相当于浏览器控制权限，必须由管理员在专用非默认 profile 启动的浏览器上启用，仅本机监听，禁止公网暴露/远程隧道/不可信本机进程。此程序校验连接目的地，不能证明目标浏览器没有同时监听外网。管理员必须自行检查监听配置。浏览器已有扩展、service worker、用户并发切换账号并非事务隔离；前后 uid 校验不能保证操作中间无切换，验证时不要同时手动操作该账号。只读指本项目不发起写命令，网页加载仍可能更新网站自身会话 Cookie/遥测。

## doctor 与失败诊断

`python -m xianyu_workbench.cli doctor` 不读 `.env`/数据/profile、不连接 CDP。管理员须先在进程环境显式提供需要诊断的配置。输出发现的浏览器种类、选择结果、模式、reason 和 `connection_checked=false`；不输出路径、端点、uid 或 Cookie。CDP 的 existing_browser 表示配置选择而非已验证在线；隔离 selected 表示启动前选择，不承诺启动成功。Chrome/Chromium 缺失和显式路径失效有明确脱敏提示。

## 验收边界

单元模拟覆盖发现、Windows 路径、配置、账号绑定、端点拒绝、重定向和对象所有权。`tests/test_browser_real.py` 是 opt-in：只启动独立 headless Chromium、随机 CDP 端口、假 unb、本地 HTML/about:blank，不访问闲鱼；fixture 可注入假 Cookie，生产 CDP 适配不得注入。Google Chrome、Windows 可见窗口、真实网站/登录态和真实 CDP 均由 Hermes 后续独立验证，不以模拟测试冒充实测。
