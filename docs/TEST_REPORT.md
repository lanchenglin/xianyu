# v0.1.0 开发验收记录

日期：2026-10-14。此文件只记录实际执行的检查，不把待部署步骤写成已验收。

以下“已执行”为首次 Linux 开发环境的历史记录；上传后的 GitHub CI 结果另列于下一节，不混为本地主人电脑验收。未完成功能与续开发步骤见 [开发交接清单](DEVELOPMENT_HANDOFF.md)。

## 2026-10-19 定向复审 FAIL：摘要允许字段值未限型

父助手进一步定向复审发现允许key内dict/list或任意字符串可穿透；此前819通过不抵消此缺口，保留FAIL。仅按公开privacy-types-fix说明修正结果投影，不改平台字段转换或daily。

先 RED **44 failed, 3 passed /16.27s**，日志 `/home/lan/.hermes/cache/scratch/xianyu-privacy-types-red.log`。逐个七允许key覆盖dict/list/嵌套私密标记/畸形字符串/null，HTTP列表及详情、真实MCP stdio→临时API的submitted/unconfirmed/failed。补错型bool/int、错目标ID/Unicode数字/换行、未知stage/notice；NaN/Infinity/负Infinity通过解密边界替身测试，未发送非法JSON。合法摘要和admin原始审计兼容检查保留。

新增edit_result.public_edit_result有限标量投影：stage仅实际submitting/verifying/verified；item_id仅ASCII数字字符串且匹配action目标；三验证字段严格bool；verified_at仅有限非负int/float且排除bool（巨大整数转float溢出也丢弃）；notice仅现有固定生产中文文案。坏值/容器/未知字段丢弃，不str()隐式回显。管理员原始结果不经过该投影。隐私类型+既有隐私+投影专项 **84 passed /29.09s**，ruff通过。最终全量 **866 passed, 1 warning /323.42s，退出0，无skip**，日志 `/home/lan/.hermes/cache/scratch/xianyu-privacy-types-final.log`；启用专用Chromium与固定scratch TMPDIR、env -u PYTHONPATH。独立UI smoke、ruff、pip check、node --check、git diff --check全部通过。唯一warning为既有Starlette/httpx弃用提醒；本轮Python3.12。本地修复通过不等于父助手独立复审PASS。日志及临时数据均在指定scratch，无生产访问/真实CDP/部署/commit/push。

## 2026-10-19 投影复审 FAIL：Agent 原始审计泄漏修复

父助手复审 **FAIL**：action_view 非admin只删除 item.edit result.after，新增 preflight_snapshots 两轮完整原始detail/edit仍暴露于Agent HTTP/MCP。此前813通过与只读审查未发现问题不能抵消该FAIL。仅按指定公开privacy-fix说明修复，不加入真实字段转换。

先 RED **6 failed, 1 warning /5.58s**，日志 `/home/lan/.hermes/cache/scratch/xianyu-projection-privacy-red.log`：HTTP列表/单条详情的submitted、unconfirmed、failed、running，真实投影执行链生成preflight，以及真实MCP stdio→临时API多状态list_actions均泄漏私密标记。非admin item.edit结果改为显式白名单：stage/item_id/ownership_verified/status_verified/content_verified/verified_at/notice；未列字段（含before/after/preflight/协议/hash和未知未来字段）默认不返回。管理员完整解密审计和数据库原值不变，新增测试逐项验证。

关联检查：发布执行结果当前保留uploads私有回执（既有投影去除）及固定摘要，无preflight原始detail；消息结果为固定验证摘要，人工核对证据仍admin-only。本批不扩大重构其他action路径。隐私+投影+snapshot专项 **59 passed /19.41s**。ruff首次新增测试多余空行已修正。最终全量 **819 passed, 1 warning /306.22s，退出0，无skip**，日志 `/home/lan/.hermes/cache/scratch/xianyu-projection-privacy-final.log`；使用env -u PYTHONPATH、固定scratch TMPDIR、XY_TEST_CHROMIUM=/snap/bin/chromium与专用浏览器缓存。独立UI smoke、ruff、pip check、node --check、git diff --check全部通过。唯一warning仍为Starlette/httpx弃用提醒。此次为本地修复证据，未冒充父助手独立复审PASS。所有本轮日志与临时数据在指定scratch，未访问真实数据/服务/CDP，未改daily，未commit/push/部署。

## 2026-10-19 三叶 observational_projection 增量

仅读取父助手指定公开 stability-evidence/differences 两文件；不读取私有快照。显式 v3 comparison_mode=observational_projection + 三个有限枚举子集；旧协议默认 full_snapshot。只允许普通detail的 browseCnt(int)、serverTime(str)、商业浮层指定text(str)值变化，逐次验证存在/类型/依赖不重叠。完整原始before、两轮preflight及after保留，稳定投影hash不是版本/CAS。保存与提案事务、执行历史、双读和after一致使用投影；历史过渡同时匹配新旧契约，未知锁止不变。

先 RED **17 failed, 12 passed /6.14s**（缺显式投影字段导致HTTP422），日志 `/home/lan/.hermes/cache/scratch/xianyu-projection-red.log`。事务保存重编门槛另 RED **2 failed**（旧稳定内容仍返回200），加新旧投影历史检查后安全专项 **120 passed /30.53s**。三种协议模式的隔离Chromium UI **4 passed /13.25s**。ruff首次两项空行排序错误已修复。独立只读源码审查未发现具体缺陷；审查者未运行测试，此结论不冒充平台验收。

最终全量 **813 passed, 1 warning /300.42s，退出0，无skip**（Python3.12，专用Chromium），日志 `/home/lan/.hermes/cache/scratch/xianyu-projection-final.log`；唯一warning为既有Starlette/httpx弃用提醒。独立UI smoke、ruff、pip check、node --check、git diff --check全部通过。所有新日志/临时数据使用 `/home/lan/.hermes/cache/scratch`，无全局PYTHONPATH设置，无生产数据/CDP/8099/9235访问，无daily/部署/commit/push。完整真实协议其他映射仍待父助手，编辑默认关闭。

## 2026-10-19 独立 Chromium fixture 启动竞争修复

父助手独立全量 **766 passed, 1 error**：`test_page_state_probe.py:32` 在 DevToolsActivePort 刚创建但内容仍为空时 `splitlines()[0]` 抛 IndexError。该失败确证并保留，不被此前本地767通过抵消。本批仅修改 tests 启动等待及本记录，不修改 bounded_snapshot 或其他业务代码。

可控临时文件分阶段回归先 RED **8 failed /0.17s**：空文件、空行、非数字、0、越界65536、未结束数字行、非ASCII数字以及子进程退出；确实复现原 IndexError。测试不启动浏览器、不访问 CDP。修复后相同8项 **8 passed /0.10s**；追加无文件/无效文件 deadline、读期间退出、文件后出现回归。三个相同缺陷入口（page_state_probe/browser_real/operations_real）均使用 tests/cdp_startup.py：原15秒上限、monotonic deadline、完整ASCII端口行与1～65535、读前及就绪前poll存活验证，不增加sleep、不以文件exists作为就绪。各入口原临时profile/随机端口/清理逻辑不变；源码搜索无其他直接读取路径。

中间真实浏览器专项误用 `TMPDIR=/tmp`，Snap 隔离下端口文件不可见，记录 **2 failed, 15 passed, 5 errors /108.62s**（均为有界deadline而非IndexError）；改用文档已有Snap可见固定目录后，全部专项 **22 passed /52.39s**。统一环境：`env -u PYTHONPATH TMPDIR=/home/lan/.hermes/cache/scratch XY_TEST_CHROMIUM=/snap/bin/chromium PLAYWRIGHT_BROWSERS_PATH=/home/lan/projects/xianyu/.test-browsers PLAYWRIGHT_SKIP_BROWSER_GC=1`，独立虚构数据，不访问真实CDP。

最终全量 **781 passed, 1 warning /289.89s，退出0，无skip**（Python3.12），日志 `/tmp/xianyu-cdp-fixture-final.log`；唯一warning仍为既有Starlette/httpx弃用提醒。上述固定环境下独立 UI smoke 通过（含审批、人工核对、XSS、Agent隔离、移动端）；ruff All checks passed、pip No broken requirements found、node --check 和 git diff --check 全部通过。没有commit/push/部署/线上配置变更。

## 2026-10-19 bounded_snapshot 本地实现与独立审查

读取指定三份脱敏公开证据，未读其私有原件。Request-stage 捕获请求已取消发送：无版本/CAS、web_combined、普通 detail seller 独立归属。实现默认不启用的 v3 bounded_snapshot 与 v2 version_required 并存，未改 SQL schema/daily/生产配置、未重启/部署/commit/push。

TDD：修正测试账号 fixture 后，首轮 **5 failed, 9 passed**（缺 v3 支持，HTTP422）；实现后 snapshot+legacy **40 passed**。UI 双模式先 **1 failed, 2 passed**（风险警告缺失），后隔离 Chromium snapshot/UI/transport **26 passed**。独立审查初次发现两个缺陷：组合模式未编码独立标题变化却接受申请、空身份路径抛 IndexError；再现 **3 failed**，修复为独立标题变化提交前409、空路径422。不发明标题截断转换。uniqueCode 历史碰撞先 **1 failed**，增加 IMMEDIATE 事务内碰撞拒绝；明确 status_path 缺失先 **1 failed**，增加普通 detail 状态严格类型/非空/路径不重叠门槛。

独立只读 reviewer 两轮复审确认以上缺陷已修复、完整双快照/逐叶覆盖/独立seller/未知阻断未降低，未发现新的具体阻断缺陷；最终 status guard 复审 **22 passed**。reviewer 自己的 UI 因无浏览器环境跳过，不冒充 UI 验收；主会话已指定独立 Chromium 实测两种模式。verified 后精确新快照重审、旧快照拒绝、default-off、实际提交 code 等于冻结值均有回归；后补的这些回归首次即通过，不称其先 RED。

首轮全量在追加 status_path 门槛期间运行，旧进程 fixture 与新启动服务契约不一致：**1 failed, 765 passed /313.05s**（snapshot UI 保存协议422）；记录保留 `/tmp/xianyu-snapshot-pytest.log`，不作最终结果。稳定代码后 snapshot/UI **25 passed /16.92s**，安全/恢复专项 **71 passed /21.76s**，ruff、pip check、node --check、diff --check、独立 Chromium UI smoke 全部通过。稳定代码最终全量 **767 passed, 1 warning /307.83s，退出0，无skip**，日志 `/tmp/xianyu-snapshot-final.log`（包含两种模式的隔离 Chromium UI）。唯一 warning 为既有 Starlette/httpx 弃用提醒；本轮 Python 3.12，不宣称已跑3.11。真实工作台编辑/改价仍未验收；图片转换仅完整 identity、独立短标题编辑缺证拒绝，父助手最小补充结构已列 ITEM_EDIT。full data 的动态字段不提供任意忽略规则；具体真实协议可能仍因不匹配被拒绝，不能拿 fixture 启用。

## 2026-10-19 最终复审外部 JSON 遗漏 P1 修复

父助手最终复审报告 item.edit 事务阻断已通过，NO-GO剩上传/LLM/MCP/CLI外部 response.json 遗漏；此前703通过不能抵消遗漏。逐入口原始响应 RED **25 failed, 3 passed /4.96s**（NaN/Infinity/-Infinity/1e999/重复键/超限及上传未启用stream），日志 `/tmp/xianyu-json-red.log`。改为请求本身stream=True或httpx.Client.stream，逐块限额读取后共用bounded_json→strict_json，校验根结构与消费字段，固定脱敏错误且不重试。上传/LLM/CLI上限1MiB，MCP身份64KiB、业务4MiB，8192字节解码块，finally/context关闭响应。上传原始HTTP测试只调用一次；上游上传fixture改为真实requests.Response字节流以检查新契约，没有削弱异常输入。MCP管理员令牌拒绝固定文案回归曾1 failed，已保留原权限契约并修复。

专项含结构/身份探测阻断/超限停止读取/既有CLI与MCP：**49 passed, 1 warning /11.72s**。最终全量 **743 passed, 1 warning /280.05s，退出0，无skip**，日志 `/tmp/xianyu-json-final-full.log`。独立Chromium UI smoke通过；ruff All checks passed、pip No broken requirements found、node --check及git diff --check通过。唯一warning仍为既有Starlette/httpx弃用提醒。上述为本地修复证据，不替代父助手独立复审或真实平台验收。

剩余读取边界扫描：项目Python仅security.strict_json和message_text已带duplicate/constant钩子的json.loads；message_text原始文本另有18KB/深度/节点限制，非业务写协议。浏览器app.js的response.json是同源工作台响应展示，不是服务端外部信任入口，未盲改前端。固定上游SDK内部MTOP/其他解析未改造，不声明整个SDK全部严格；项目provider对子进程原始输出仍strict_json。模型生成content若不是合法JSON仍按原契约作为普通草稿文本返回，不当结构化协议执行。未访问真实数据/凭据/浏览器，未重启/部署/commit/push，未改daily。

## 2026-10-19 第二轮独立复审 FAIL 修复

第二轮复审 **FAIL**：unknown后协议PUT和新key提案仍接受，但执行层已阻断，不能称已发生重复外写；JSON入口接受非有限数及重复键。已有684通过不能抵消FAIL。本轮不接触真实配置/数据/浏览器/私有快照，不部署/提交/推送，不改daily。

HTTP及canonical先RED：**11 failed /2.89s**，包含unknown后200、NaN/Infinity/-Infinity/1e999、顶层/嵌套重复键、canonical非有限及嵌套Cookie JSON重复键。事务内unknown_guard、申请协议复核、原始HTTP流限额严格解析、共用strict_json和canonical allow_nan=False后同组 **11 passed /2.93s**。新增并发执行期间保存/申请、prepare后历史竞争、事务内检查与账号商品隔离；最新复审专项 **19 passed /4.97s**。编辑全专项含独立Chromium **75 passed /22.39s**（最后增加的事务作用域用例另计）。旧回归中4项原先期待unknown后保存成功，按新需求改为入口409；不删除执行阻断覆盖。

同类JSON路径检查：复用message_text已有duplicate/constant规则；HTTP所有JSON路由、cookies_json、CLI配置、备份manifest、Vault与本地JSON读取、bridge输入/provider输出、外部browser/CDP/通知JSON改用strict_json。multipart与form不预解析，GET/static保持；UI smoke通过。JSON字符串作为普通商品正文不递归解释成协议。历史坏数据不静默修改，固定脱敏错误。全量 **702 passed, 1 warning /277.41s，退出0，无skip**，日志 `/tmp/xianyu-edit-rereview-final.log`；全量收集后补充1项事务作用域/账号商品隔离测试，已在19项专项通过，不计入702。ruff/pip/node/diff最终通过（中途导入排序及EOF空行已修复）。唯一warning仍为Starlette/httpx弃用提醒。保留两轮FAIL；本地修复不等于独立复审PASS，更不等于平台验收。父助手报告editDetail userId语义尚未核对，未猜UID/版本映射，继续默认关闭。

## 2026-10-19 同 ID 编辑独立审查 FAIL 修复

父助手独立审查 **FAIL**：原模板仅校验三个可变叶子，可夹带 OFFLINE/未知字段；旧实现成功后永久锁商品不符合需求。此前通过数（含父助手报告662）不能抵消此 FAIL。本轮依据指定脱敏修复要求，未访问生产端口/凭据/私有快照、未改 daily、未提交部署。

先 RED：`test_item_edit_review.py` **5 failed /2.16s**（状态/未知/嵌套数组/未映射字段被200接受、成功后再次编辑failed）；另旧协议提交前失败被误记unknown的 RED **1 failed /1.16s**。修复协议 v2 全覆盖映射、原始请求递归绑定、固定元数据无免检例外；持久化 verified after，允许新版本/新revision/重新审批，unknown仍锁止。旧v1不自动迁移授权；明确提交前失败不占未知锁。并发、恢复、Agent隐藏after、数组/嵌套/类型/未知字段等回归已补。

阶段性专项含编辑Chromium UI **56 passed /18.53s**，再补旧协议用例后审查专项 **22 passed /6.40s**。全量 **684 passed, 1 warning /275.01s，退出0，无skip**，日志 `/tmp/xianyu-edit-review-final.log`。随后更新的API能力说明/UI文案亦通过编辑+MCP专项 **59 passed /26.41s**；UI smoke通过。ruff/pip/node/diff通过，唯一warning仍为既有Starlette/httpx弃用提醒。不将本地修复等同独立复审PASS或真实平台验收，当前禁止部署/启用直到父助手复审及完整真实证据满足门槛。

## 2026-10-19 管理员单条同 ID 编辑（隔离实现，后续独立审查 FAIL）

仅读取指定脱敏证据与仓库文件，不读取真实 .env/data/profile，不连接生产/平台或现有浏览器，不改每日生产配置，不 commit/push/deploy。父助手已验证的发布/每日部署状态以 LIVE_PUBLISH_ACCEPTANCE 为准，本批不重验。新增默认关闭管理员编辑证据控制面及固定 editDetail/edit 适配器，详见 ITEM_EDIT；真实完整编辑 payload 未采集、工作台编辑/改价未验收。

RED 首轮 14 failed（缺失 edit_enabled）；恢复测试先失败于协议未撤销；UI 结构测试先失败于表单缺失；新幂等键绕过一次提交限制先复现第二次 unconfirmed 后封堵。开发期间修复 FastAPI 局部前向类型注解导致 body 被识别为 query（13 failed）、测试虚构 Cookie 缺字段（6 failed），ruff unused import/排序；这些失败不隐去。后补安全/固定传输/UI/MCP 回归中首次通过的部分不称先 RED。

当前新增专项 **33 passed, 1 warning /13.37s**，包含独立 Chromium 随机本地端口的新表单保存/申请/文本 XSS/Agent 隐藏测试；真实 MCP stdio **2 passed, 1 warning /6.09s**。独立 UI smoke 已通过（登录/账号/搜索/监控/消息/审批/人工核对/Agent 隔离/图片/发布/移动端/退出）。ruff All checks passed、pip No broken requirements found、node --check、git diff --check 均通过。全量第一轮 **659 passed, 1 warning /262.29s**；加入编辑 Chromium UI 与 MCP 断言后最终全量 **660 passed, 1 warning /263.24s，退出0，无 skipped**，日志 `/tmp/xianyu-edit-final-pytest.log`。最终全量收集后另扩展恢复参数覆盖 running/submitted，专项 **3 passed /2.27s**（原 approved 加两种状态）；这两个新增参数未计入 660，不冒称已纳入该全量。唯一 warning 为既有 Starlette/httpx 弃用提醒。最后 ruff/pip/node/diff 再次通过。未做真实平台验收或独立第三方审查，留父助手审查后决定提交部署。

## 2026-10-19 GPS 纬度/经度方向修复

父助手报告bc605b3部署后publish-defaults返回422 location.gps string_pattern_mismatch，已证网页格式为纬度在前、经度在后。仅用虚构坐标复现，未读取私有GPS、来源快照、.env/data/profile或真实实例，未部署/重启/commit/push。

原正则前3位后2位方向错误且没有数值范围检查，Model还会自动strip空白。新增before字段验证：ASCII十进制格式，纬度[-90,90]前1～2位，经度[-180,180]后1～3位；拒绝非有限数/指数/空白/加号/超范围/错误位数。Decimal只用于校验，返回原字符串，不交换或归一；旧持久化Location也在预览/执行前复验，拒绝非法旧配置并要求重录审批。未添加lonlat兼容猜测。

RED **12 failed,12 passed**，覆盖真实形状虚构坐标被拒、反向/超范围/空白/Unicode数字被错误接受、旧存储未复验；修复后相关 **61 passed,1 warning /14.41s**。另补API冻结原串与旧配置上传前阻断回归。共享fixture和文档示例改为虚构latlon，其他地点路径没有独立GPS正则。

最终全量 **627 passed,1 warning in 254.71s，退出0，无skipped**，完整日志 `/home/lan/.hermes/cache/scratch/xianyu-gps-final.log`。唯一warning仍为Starlette/httpx弃用提醒。UI smoke通过；ruff首次发现新增测试导入排序错误，修正后All checks passed；pip check No broken requirements found、node --check及git diff --check通过。使用指定.venv、env -u PYTHONPATH、临时TMPDIR、独立Chromium缓存与profile；未做真实API/平台验收。

## 2026-10-19 网页组合文本契约最小增量

父助手报告53df5c3已部署且线上只读通过；本编码端未访问、读取或重启线上。仅读取指定脱敏publish-observed-contract及用户补充精确构造，不读真实.env/data/profile/私有快照、不发帖、不commit/push。

新增管理员defaults/protocol text_mode枚举separate/web_combined；默认旧模式兼容但不称已证。web_combined按冻结完整desc构造请求title/desc且false分离标志；回读仍比较冻结payload短标题与完整desc。模式随revision/digest/每日快照冻结，旧审批/每日授权变化阻断，严格candidate比较保留。

RED **4 failed, 1 passed**（缺少text_mode配置支持）；实现后双模式/多行与原执行器26 passed，新增模式不匹配/未知/请求短标题拒绝、每日生成新码仍保持网页文本及模式变化阻断专项9 passed。发布ACK仍缺，不以编辑ACK或fixture代替。最终全量 **601 passed, 1 warning in 252.34s，退出0，无skipped**，日志 `/home/lan/.hermes/cache/scratch/xianyu-text-mode-final.log`。唯一warning为既有Starlette/httpx弃用提示。隔离UI smoke通过；ruff All checks passed、pip check No broken requirements found、node --check与git diff --check均退出0。全部使用指定.venv、env -u PYTHONPATH、TMPDIR及独立Chromium缓存/profile。

## 2026-10-19 独立审查P1：历史账本阻断一致性

读取父助手指定审查摘要，未访问真实实例/凭据，未commit/push。P0生成方式保持不变。最小修复将配置/tick共用LEFT JOIN历史检查：任一非submitted或缺失action均阻止enabled配置（409 daily_unresolved）与tick；状态增加effective/blocked_reason，避免已存enabled显示成有效授权。关闭配置不清除日期账本，不允许重放。

参数化RED **10 failed**：failed/blocked/rejected/expired与缺失action曾允许启用，其他状态及submitted对照缺effective状态。修复后历史/生成/实际CLI子进程→临时API/隔离Chromium状态与tick专项 **18 passed, 1 warning in 18.19s**。原生成重启三例仅阻塞原因由date_used/previous_not_verified统一成daily_unresolved，冻结码/抽取次数/不重发断言保留。没有扩大重构、schema变化或新平台能力。

最终全量 **592 passed, 1 warning in 243.13s，退出0，无skipped**；日志 `/home/lan/.hermes/cache/scratch/xianyu-p1-final.log`。warning为既有Starlette/httpx弃用提醒。隔离UI smoke通过；ruff All checks passed、pip check No broken requirements found、node --check、git diff --check均退出0。使用指定.venv、env -u PYTHONPATH、TMPDIR、独立浏览器缓存与临时profile；真实平台默认关闭，未验收声明不变。

## 2026-10-19 uniqueCode 官方生成规则修正

父助手提供指定公开JS证据及脱敏同ID网页编辑记录，仅读取这两份授权文件。原 unique_code_reuse_verified 控制面错误，已删除；改显式 generation_mode（disabled/timestamp_random_v1），默认关闭，旧授权不自动升级。新每日action在事务内按毫秒拼接0～999整数生成一次，冻结payload/digest并保存加密占用；碰撞拒绝且不重抽、不外部写。仅受证动态字段可归一比较，其余整个payload严格相等。schema仍v13，无自动新增授权迁移。

先修改每日模式/冻结断言，RED **11 failed, 2 passed**（缺generation_mode）；实现后 **13 passed**。补充生成0/7/999不补位、进程重启不换码、已有日期不重抽、非uniqueCode篡改拒绝、码篡改拒绝、旧reuse策略撤销、占用碰撞与离线恢复回归，专项23 passed。历史action碰撞补充测试首轮误选不含executor的预览夹具导致KeyError，已修正为明确源action，不是生产缺陷。

真实网页编辑证据只写入OPERATIONS_NEXT，不新增编辑接口、不把edit ACK当publish ACK。未部署、未commit/push、未访问真实账号；最终全量 **582 passed, 1 warning in 239.96s，退出0，无skipped**，日志 `/home/lan/.hermes/cache/scratch/xianyu-generation-final.log`；中间全量581 passed/1 warning/247.54s。唯一warning仍为Starlette/httpx弃用提示。隔离UI smoke通过；ruff All checks passed、pip check No broken requirements found、node --check、git diff --check均退出0。继续使用指定 .venv、env -u PYTHONPATH、临时TMPDIR、独立Chromium profile及浏览器缓存，不运行真实实例。

## 2026-10-18 8df62e7 后发布内容与每日授权（隔离编码）

未 commit/push/部署，未读真实 .env/data/profile/私有快照，未访问真实8099/9235或真实平台，原 scratch 未动。父助手提供的真实请求/详情结构用于构造虚构 fixture；不把父助手网页发布成功写成工作台 API 验收。发布 ACK 仍缺，真实启用关闭。

RED 实测：结构/内容首轮2 failed（强加顶层 onlyTakeSelf、内容不同仍 submitted）；每日授权首轮6 failed（无路由/模块）；UI/CLI入口1 failed；严格数字/配送2 failed；详情整数身份2 failed；暂停/接管持久撤销2 failed；重复已有itemId1 failed；回读金额与冻结金额不同1 failed。对应修复后专项通过。并发、恢复、CLI临时服务与新增内容反例为补充回归，部分首次即通过，不冒称 RED。

首轮发布专项84 passed/1 failed：UI旧fixture缺新增 readback_content，补齐虚构协议后通过。首轮全量565 passed/3 failed/1 warning，226.52s：历史v2恢复fixture残留新v13表、两处旧schema12断言；修正fixture和断言，没有放宽生产迁移。修复后相关49 passed/1 warning，16.34s。真实 CLI子进程→临时API及隔离Chromium每日状态/tick/撤销/Agent隐藏2 passed/1 warning，8.40s。

中间完整修复轮570 passed/1 warning，238.55s；后追加CLI集成与内容反例，最终全量 **576 passed, 1 warning in 238.65s，退出0，无 skipped**，完整日志 `/home/lan/.hermes/cache/scratch/xianyu-daily-final-all.log`。唯一 warning 为既有 Starlette/httpx 弃用提醒。最终页面UI smoke输出 `UI smoke passed`，退出0；ruff `All checks passed!`、pip check `No broken requirements found.`、node --check 和 git diff --check 均退出0。所有测试使用项目 .venv、env -u PYTHONPATH、TMPDIR=/home/lan/.hermes/cache/scratch、XY_TEST_CHROMIUM=/snap/bin/chromium、独立PLAYWRIGHT_BROWSERS_PATH和PLAYWRIGHT_SKIP_BROWSER_GC=1。尚未运行Python3.11、Windows、远端CI或本批Docker，不借用历史通过结果。

## 2026-10-18 a9cbb50 后 Docker 隔离演示与恢复修复

基线 `a9cbb50`，保留工作树交父助手审查，未 commit/push。未读真实 .env/data/profile，未连接宿主8099/9235，不动仓库 scratch，不改宿主配置/镜像源，不真实发送/上传/发布，不改变 FAQ 授权。所有应用数据、令牌/密钥均本批虚构。

### Docker 实测与 RED/GREEN

- Docker Engine client/server **29.8.0**、Compose **v5.5.1**，default context 可用。预先只读核实既有镜像源配置及缓存：`python:3.12-slim` Linux amd64，digest `sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea`（本地同时有 python 与 harbor 标签）。使用缓存基础镜像、`build --pull=false`，未更换源；容器构建 pip 依赖下载成功，无外部下载阻塞。
- 项目外 allowlist 构建上下文仅复制 Dockerfile、requirements.lock、pyproject.toml、README 和已跟踪 xianyu_workbench；未把仓库根/scratch/data 传给 Docker。独立 Compose 项目 `xyaccept-b874adc72c`，临时 env_file，专属命名卷，`127.0.0.1::8099`，保留 UID10001/cap_drop/no-new-privileges/健康检查；live/message_send/publish/worker 全 false。首次上下文的私有 umask 导致临时复制源码不可被 UID10001 的 `python -c` 导入，诊断改在 /tmp 使用已安装包，复建时仅规范临时公开源码文件/目录权限644/755；不是生产权限修复。
- 首次构建成功，健康启动、未认证401、账号/图片/加密草稿/已批准演示动作、运行中备份拒绝、重启持久化、停机备份通过；**恢复失败**。实际 traceback：`backup.py:189` 在 `/app/.restore-*` 创建目录 PermissionError。父目录 /app 不可写，且它与 data 命名卷不在同一文件系统；不能靠放宽 /app 或 root 规避。
- 新增 `test_restore_data_volume_with_unwritable_parent`，非 root POSIX 实际只读父目录：修复前 **1 failed**，同一 PermissionError；改为 data 内暂存与回滚，专项 **36 passed, 1 warning / 9.59s**。覆盖原数据回滚副本、恢复暂停、暂存/marker 清理，既有中断标记、回滚注入、错误密钥、资源/关系校验及发布阶段恢复仍通过。无 schema/依赖/协议变更。
- 修复后重新构建并从新空卷重跑完整流程，实际端口 **32770 → 32771 → 32772**（重启重新查询端口）。备份后主动修改虚构账号标签、删除草稿、损坏图片，再通过真实 CLI 恢复：标签/图片字节/schema12/草稿恢复、账号暂停、旧 approved→expired；恢复账号后真实 Service.run_once 返回 false，无旧动作重放。默认关闭 schedule CLI 输出 disabled。镜像内 pip check 无冲突、运行 UID10001、data 权限0700。
- 最终演练输出 **ALL DOCKER ACCEPTANCE CHECKS PASSED，退出0**。`down --volumes --remove-orphans` 仅指定本批项目；容器/卷/网络 label 查询均空。测试镜像 `54630728f2e5…` 已精确删除；首次构建旧ID查询已不存在，无其他镜像/容器/卷清理、无 prune。构建缓存未全局清理。

### 修复后最终全量验证

项目 `.venv` Python **3.12.14**，`env -u PYTHONPATH`，稳定 `TMPDIR=/home/lan/.hermes/cache/scratch`，`XY_TEST_CHROMIUM=/snap/bin/chromium`，独立 `PLAYWRIGHT_BROWSERS_PATH=<本批证据目录>/browsers`、`PLAYWRIGHT_SKIP_BROWSER_GC=1`，所有浏览器新临时 profile。实际顺序运行：

- `python -m pytest -q`：**549 passed, 1 warning in 246.69s，退出0，无 skipped**，日志 `pytest-fixed.log`。唯一 warning 为既有 Starlette/httpx 弃用提醒；含既有真实 MCP stdio 与隔离浏览器回归。
- `python scripts/smoke_ui.py`：**UI smoke passed，退出0**，日志 `ui.log`；登录/账号/搜索/监控/聊天/审批/人工核对/XSS/Agent隔离/图片/演示发布/移动端/退出通过。
- `python -m ruff check .`：All checks passed；`python -m pip check`：No broken requirements found；`node --check xianyu_workbench/static/app.js`、`git diff --check` 与变更 Markdown 本地链接存在性检查通过。
- 本批未运行 Python3.11/Windows/远端CI，不借用历史结果宣称本轮通过。Docker/恢复及全量本地验证完成，仍交父助手独立审查，不宣称独立复审已通过。

### 其他离线验收核查与剩余边界

已有真实 MCP SDK stdio→临时 API 回归直接复用全量测试，没有重造客户端。离线本地管理/草稿导入/价格样本/调度/权限/恢复测试继续覆盖；修正 DEPLOYMENT 过期的 schema v10 与“无调度”声明，当前为 v12、默认关闭离线调度。Docker 演示验收不等于生产部署或容器内真实浏览器支持。

剩余平台事项仍按 OPERATIONS_NEXT 的取证表阻塞：发布完整协议/图片/配送/uniqueCode/真实状态、消息ACK/历史cursor、买到真实末页/卖出订单、全状态库存、改价/上下架、首次联系CID；未猜接口或制造平台证据。FAQ自动发送需独立授权与限额账本设计；实际客户端配置、真实模型/通知目标、生产部署、云备份/密钥轮换均不由本次隔离演练代替。付款等永久人工不变。

证据目录（项目外，不提交）：`/home/lan/.hermes/cache/scratch/xy-docker-accept-3d7xn1bh/`；`build.log` / `accept.log` 保留首次失败，`restore-red.log` 为回归 RED，`build-fixed.log` / `accept-fixed.log` 为修复后 Docker 实测，`accept.py` 为本次临时驱动。原基线全量 `pytest.log`：548 passed, 1 warning /225.18s，不冒充修复后结果。

## 2026-10-18 35914be 后离线运营纵向增量

本轮保留工作树供父助手统一审查提交，未 commit/push/部署，scratch 原有未跟踪内容未动。未读取真实 .env/data/profile/私有快照、未连接8099/9235、未访问平台或真实通知目标。四项：取消归档与管理员引用保护素材回收；默认关闭离线备份调度及保留；搜索样本价格历史/降价通知；批量本地草稿预览/幂等导入/逐条申请进度。schema v11/v12 显式迁移。

测试先行记录：最初本地管理3 failed、调度2 failed、价格1 failed、导入2 failed（缺模块/路由）；实现后核心8 passed。追加并发申请回归发现 revision 检查不在 action 写事务中（1 failed），修复为事务内 draft_guard 后通过；追加符号链接回收反例1 failed，增加路径/重复登记拒绝后通过。并发素材引用/离线恢复/MCP补充回归首次通过，不能称为修复前RED。

首轮全量 **540 passed, 3 failed, 1 warning / 219.97s**：旧v2备份夹具未移除新表，两个消息测试仍断言schema10。修正历史夹具与版本断言，针对性8 passed。没有放宽生产迁移或删除旧安全断言。

最终全量已等待实际 summary：**548 passed, 1 warning in 218.77s，退出0，无 skipped**。新增功能集合13 passed；真实 MCP SDK stdio临时API回归包含新工具发现、导入预览不落库、素材候选，无删除/备份/批量批准工具。备份恢复增加v12价格和批次关系保留、监控关闭/账号暂停/无action重放。

命令环境：`env -u PYTHONPATH`、项目 `.venv`、`TMPDIR=/home/lan/.hermes/cache/scratch`、`XY_TEST_CHROMIUM=/snap/bin/chromium`、`PLAYWRIGHT_BROWSERS_PATH=/home/lan/.hermes/cache/scratch/xianyu-offline-browsers`、`PLAYWRIGHT_SKIP_BROWSER_GC=1`。实际运行 `python -m pytest -q`、`python scripts/smoke_ui.py`、`python -m pip check`、`python -m ruff check .`、`node --check xianyu_workbench/static/app.js`、`git diff --check`。

UI冒烟实际退出0，增加取消归档、引用素材不可删除、JSON批量预览/确认、逐条进度，保留原登录/搜索/通知/审批/人工核对/XSS/Agent隔离/演示发布/移动端。pip check 无冲突；ruff初检1项导入排序问题，修复后 All checks passed；node/diff通过。唯一warning是既有Starlette/httpx弃用提醒，不升级依赖。CLI默认关闭实测输出disabled且未访问虚构路径。

日志在项目外隔离目录：`/home/lan/.hermes/cache/scratch/xianyu-offline-pytest-final.log`、`xianyu-offline-ui-final.log`；首轮失败日志 `xianyu-offline-pytest.log` 保留。仅本机项目Python3.12，未重跑3.11/Windows/CI。

边界：未真实上传/发布/发送/删除，未修改FAQ自动发送、live默认关闭、唯一审批队列、账号隔离、管理员单action、不确定不重试及永久人工交易。离线调度不在线备份、不安装宿主任务；素材中断可能留未登记文件，不自动清理任意文件；价格仅搜索样本，批量仅本地草稿。平台结构/类型/验收需求清单在 OPERATIONS_NEXT，不声明整个产品全部完成。

## 2026-10-18 f8d1ad8 执行器复核、文档整理与灾备回归

本批在 feat/local-next / f8d1ad8 原地修改，未 commit/push/部署。仅项目 `.venv` Python 3.12.14；未重跑 3.11/Windows/远端 CI。未读取真实 .env/data/profile/私有快照，未连接8099/9235或真实平台，不动现有未跟踪 scratch。

- 审查范围：publish_executor/publish_preview/service/provider/bridge 的审批、传输、阶段、回读及角色投影，复跑 f8d1ad8 的精确 ret、状态类型与双开关矩阵。既有实现仍默认关闭、管理员指定单条、worker 不领取 live；未知不重试。未将本次自审称为独立第三方复审。
- 新问题：模板与 candidate 使用 Python `!=`，`0 == False` / `1 == True` / `1.0 == True` 让不同 JSON 类型误通过。修复前四个 HTTP 反例均返回201而非409（4 failed / 22 deselected）；改为现有 canonical JSON 比较，全部通过。首次测试编写有一项取错 bool 值及错误响应键，先修测试再重跑确认四项真实 RED，不将夹具错误当生产问题。
- 独立可靠性补充：`test_publish_backup.py` 五阶段 prepared/uploading/submitting/verifying/verified 的离线归档恢复；保留加密 payload/result/协议，旧授权失效、账号暂停、恢复后不重放、Agent 不见 URL/地点/模板/指纹。初次5项因 TestClient 尚未退出、跨线程 close 未释放生命周期锁而失败，改为正常退出 TestClient 后离线恢复，未改生产锁。这是补充回归，不冒称发现生产恢复缺陷。
- 当前能力正文已整理：交接2.2、Windows暂停、外部通知、离线灾备、消息观察、有界分页与默认关闭发布执行器；建立 [能力矩阵](CAPABILITY_MATRIX.md)，旧测试 FAIL 和以下历史证据保留。

实际命令（仓库根目录，浏览器脚本已核实支持 XY_TEST_CHROMIUM；无安装升级）：

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

全量已等待完整 summary：**535 passed, 1 warning in 229.52s，退出0，无 skipped**；包含12项固定上游契约、真实 MCP SDK stdio→临时 API 与隔离 Chromium。pip check 无冲突，ruff 通过。独立 smoke_ui 实际输出 UI smoke passed（登录、账号、搜索、监控、聊天、审批、人工核对/XSS/Agent隔离、图片、演示发布、移动端、退出）；node 检查通过。唯一 warning 为既有 Starlette/httpx TestClient 弃用提示。diff 初检发现三份文档尾部多空行，已清理后复检。

**真实边界：** 所有协议/状态/账号均虚构测试数据，不是平台证据。未验证真实上传、发布、消息 ACK、图片/配送/uniqueCode/完整 schema/状态语义、钉钉/webhook、实际客户端或 Docker。历史用户报告的分页结果不冒充本批复测。仍需管理员真实协议证据与单次授权验收；本批不代表全部需求完成。

## 2026-10-16 发布执行器独立审查 FAIL 与三项有界修复（历史）

独立审查对原 ac4e991 后增量判定 **FAIL**。本轮核对 HEAD 为 `4520f5e`：P0 回读仅比较 SUCCESS 代码，`SUCCESS::different-contract` 仍被接受；P1 缺失审核/在售状态契约；P1 顶层 live_publish 固定 false，与启用执行不符（嵌套 live_executor_enabled 在此 HEAD 已动态计算）。历史 504 项通过没有覆盖这些问题，不撤销或掩盖 FAIL。

- TDD RED：`scratch/publish-review-red.log` **6 failed / 3 passed**，精确 ret 反例、状态缺失/未知/字符串类型错误/bool、双开关 true 的能力声明均复现。最小修复后首轮 targeted GREEN；后补协议变化/历史缺契约阻断、允许审核中/在售虚构值和严格整数类型回归。
- 新增必填 `readback_success_ret` 独立精确数组；`readback_status.path/value_type/allowed_values` 由管理员取证输入，与完整协议一起加密冻结到 payload/digest。不推断真实字段或状态枚举。缺契约在上传前停止，已有审批不自动补默认值；回读缺失/未知/类型不符/ret 不符一律 verifying + unconfirmed，禁止重试。
- `live_publish` 与 `publish_policy.live_executor_enabled` 精确对应 Settings 的 live_enabled AND publish_enabled，四种组合已测；executor_implemented=true 表示代码支持，platform_verified=false 表示平台未验收，不把开启开关当验收。
- 最终双 Python 全量（前台等待 summary）：**3.12：526 passed / 194.07s；3.11：526 passed / 196.97s**，均退出码0，无 skipped；各1条既有 Starlette/httpx 弃用警告。日志 `scratch/publish-review-full312.log` / `publish-review-full311.log`。包含 opt-in 隔离 Chromium UI、固定上游契约和 MCP stdio 权限回归。
- 两版本 `scripts/smoke_ui.py` 成功，`scratch/publish-review-smoke312.log` / `publish-review-smoke311.log`；两版本 pip check 无依赖冲突，ruff / node --check / git diff --check 通过。命令使用 env -u PYTHONPATH；浏览器 `/snap/bin/chromium`，临时 profile，不接真实浏览器。
- 本轮只修上述三项，保留默认关闭、管理员指定单 action、持久阶段、unknown 不重试和隐私投影。未读真实 .env/data/profile，未连8099/9235，未真实上传发布；commit 不 push、不部署。**修复已本地验证，独立复审尚未进行，平台仍未验收**。

## 2026-10-16 受控发布执行器隔离验收（历史，后续独立审查 FAIL）

- 最终前台等待完整 summary：Python 3.12 **504 passed / 183.93s**，Python 3.11 **504 passed / 185.85s**，无 skipped，退出码均 0；各有 1 条既有 Starlette/httpx 弃用警告。日志 `scratch/publish-final312.log`、`scratch/publish-final311.log`。
- 双 Python 各自运行 `scripts/smoke_ui.py` 成功，日志 `scratch/publish-smoke312.log`、`scratch/publish-smoke311.log`。隔离 Chromium `/snap/bin/chromium` 使用临时 profile/API，不是平台浏览器。
- 双 Python pip check 均 No broken requirements；ruff、node --check、git diff --check 通过。命令均 `env -u PYTHONPATH`；日志稳定保存在 scratch，不提交私有目录或日志。
- 全量包含真实 MCP stdio→临时 API 的权限/预览回归；本批新增协议管理员 UI/Agent 隐藏、单条执行权限/并发领取、默认关闭/凭据和配置变化阻断、upload/submit/readback 异常 unknown 不重试、错误 ACK/归属/ID/ret、上传阶段回执加密保存、重启保留阶段、Provider 子进程凭据清理边界。传输用虚构模块/响应隔离，不声称真实平台 ACK 已验证。
- RED 证据：`publish-red.log`（readback 错误 ret 被接受、上传回执未保存）；`publish-ui-red.log`（协议表单缺失）；`publish-hash-red.log`（上传字节 hash 未重验）；`publish-readback-red.log`（回读期间 UID 变化未阻断）。修复后全量通过。其余并发/恢复/权限矩阵为补充回归，不冒称均经历 RED。
- [执行器契约](PUBLISH_EXECUTOR.md)：默认关闭、单 action 单次授权，实际 HTTP 上传/显式发布/本人 itemId 回读实现。**未真实平台验收**，没有 push/部署，没有读真实 .env/data/profile 或私有 source snapshot，没有连接8099/9235或真实写。平台 schema/类别层级/uniqueCode/配送/图片语义与 ACK 仍由父助手取证；自动回读只证本人 ID，不证明在售或价格内容等价。

## 2026-10-16 本地发布冻结预览最终验收（历史）

本批交付本地冻结预览、角色投影、审批和指定单条执行前校验，不代表真实发布或平台自动回验实现。类目/地点为管理员本地未验证输入；真实执行器保持关闭。所有 live action 排除 worker 自动领取，旧 live delete 直通关闭，不以删除替代普通下架。契约与取证清单见 [PUBLISH_PREVIEW](PUBLISH_PREVIEW.md)。用户报告独立发布预览审查 PASS、父助手35项预览/P0测试通过；这是外部报告，不冒充本轮亲自运行结果。

- 早期 `final312.log`、`final-verified312.log`、`final-verified311.log` 只有部分输出，无 summary，**不计为通过**。收尾时 `pgrep -af '[p]ython.*pytest'` 未发现残留 pytest；改为前台等待，双版本完整重跑。
- **Python 3.12.14：477 passed，182.49s；Python 3.11.16：477 passed，182.07s**。均无 skipped，各1条既有 Starlette/httpx 弃用警告，退出码均0。
- 全量包含隔离系统 Chromium `/snap/bin/chromium` 的预览 UI/Agent 隐私投影与既有单条 UI，真实 MCP stdio 连接临时本地 API（包含成功预览、缺素材拒绝、管理员令牌拒绝），以及既有隔离 transport/固定上游契约。不是平台浏览器或真实账号验收。本轮没有另跑 `scripts/smoke_ui.py`，不复用历史 smoke 结果声称本轮通过。
- 两版本 `ruff check .`、`pip check`，`node --check xianyu_workbench/static/app.js`、`git diff --check` 全部通过。
- 日志在仓库外 `/home/lan/.hermes/cache/scratch/xianyu-publish-evidence/complete312.log` 与 `complete311.log`。命令使用 `env -u PYTHONPATH TMPDIR=/home/lan/.hermes/cache/scratch`；解释器 `.venv/bin/python` 与 `/home/lan/.hermes/cache/scratch/xianyu-venv311/bin/python`，独立 `PLAYWRIGHT_BROWSERS_PATH=/home/lan/.hermes/cache/scratch/xianyu-test-browsers`、`PLAYWRIGHT_SKIP_BROWSER_GC=1`。
- RED/GREEN 证据：初始预览6项因路由/worker边界缺失失败；UI/MCP入口2项失败后实现；旧delete直接调用边界先失败后关闭。收尾 UI 复现旧申请与预览幂等键碰撞（`resume-ui-red.log`），隔离命名空间后通过。默认类目/地点变化、变回原值、素材/UID/模式/审批内容篡改与真实MCP成功投影为后补集成回归，不冒称全部先RED。
- 不读真实 `.env/data/profile`，不连8099/9235，不真实平台操作，不push/部署；保留原未跟踪 scratch，不提交运行日志。无schema迁移，使用已有加密settings/actions字段。真实发布协议/ACK、自动只读回验、改价/非删除上下架仍未实现。

## 2026-10-16 P0 FAIL 修复验收（历史：当时禁止上线，待独立复审）

独立审查确认 `75b6f98` **FAIL / P0**：仅 live+CDP 走新绑定，旧无CDP live 可绕过 XY_MESSAGE_SEND_ENABLED=false，worker 可领取历史approved并 chats→message.send。上一节/下方历史441项通过不证明该安全边界正确，保留原记录而非抹去失败。修复沿用部署基线 b8ea112，不改分页、不扩展发送机制。

- TDD 参数矩阵首次 **9 failed / 8 passed**：无CDP开关false/true、历史approved worker、直接Provider（含提供正确binding但无队列授权）复现；`scratch/xianyu-send-evidence/p0-red.txt` 保留。补齐指定execute缺绑定的CDP对照后共19项。相关回归 **112 passed**，ruff通过。
- 初次全量未启用浏览器为 **3 failed / 440 passed / 15 skipped**：旧live测试期待默认关闭时仍可提案、模式改变时期待worker领取，以及transport测试直接调用Provider。均保留测试并按新语义更新：提案立即拒绝、worker不领取且指定execute仍验证模式、transport经真实统一队列执行，不删测试隐藏语义变更。
- 修复：所有live消息提案和execute统一开关/强绑定检查，无CDP拒绝；worker排除action或account任一live的消息，历史approved不回放。Provider在锁内独立检查绑定和一次性指定动作作用域、running记录、批准/时效、账号/模式/kind、完整payload/digest；直接call不授权。旧无CDP真实直发关闭，演示自动流程保留。接管revision/限速/unknown不重发回归保留。
- 最终 **Python 3.12.14：460 passed，186.41s；Python 3.11.16：460 passed，191.68s**；均无skip，各1条既有Starlette/httpx弃用警告。含opt-in隔离Chromium、真实MCP stdio、单条UI及虚构transport。日志在仓库外 `/home/lan/.hermes/cache/scratch/xianyu-p0-final{312,311}.log`。
- 两版本独立 `scripts/smoke_ui.py` 均通过；日志同目录 `xianyu-p0-ui{312,311}.log`。两版本pip check/ruff、JS node --check及git diff --check通过。
- 命令统一 `env -u PYTHONPATH TMPDIR=/home/lan/.hermes/cache/scratch`；解释器/专用chromium-1248及独立缓存设置沿用下方记录。未读真实.env/data/profile、未连8099/9235、未真实发送、不push不部署。修复只完成本地验收，仍须独立复审；ACK accepted判定/真实Hermes/商品/FAQ/首次联系未交付。

## 2026-10-16 安全单条消息与中断后最终回归（P0 修复前历史）

基线 b8ea112，既有分页不改。新增默认关闭管理员开关、独立同 UID Cookie/WS 来源、CDP 当次 peer/CID 复核、冻结凭据/接管 revision/正文 digest、管理员指定单条领取与只读事后核对。无 schema 迁移。完整限制见 [MESSAGE_SEND](MESSAGE_SEND.md)。用户提供的基线真实 inventory2页40条 self_published complete、orders13页130条 time_limit partial 与 CI38857758684 五绿，不冒充本批验收。

- TDD 阶段日志保留于未跟踪 `scratch/xianyu-send-evidence/`：开关/指定领取、绑定/来源、严格 bridge payload、Cookie/token 清理、操作锁绑定、接管 revision、只读限速、单条 UI 与样本选择均有失败及修复回归。首次全量 `full312-first.txt` 为 416 passed / 1 failed / 14 skipped；失败是旧断言仍期待 recipient_unverified，新默认开关先返回 message_send_disabled，已同步契约。初次 UI worker-off 测试阻断原监控通知，因此恢复完整 smoke 的 worker 设置，另建独立 worker-off 单条 UI 测试；未改生产监控逻辑。
- 中断前 `final312.txt` / `final311.txt` 各441 passed；本次恢复先确认无遗留测试进程，未触碰运行中的真实服务，然后重新验证当前文件，非复用旧绿灯。
- **最终 Python 3.12.14：441 passed，166.77s；Python 3.11.16：441 passed，170.26s；均无 skip。** 各1条既有 Starlette/httpx 弃用警告。日志 `resume312.txt` / `resume311.txt`。
- 两版本额外运行 `tests/test_mcp_stdio.py tests/test_message_send_transport.py tests/test_message_send_bridge.py`：各 **7 passed**（6.37s / 6.28s），真实 MCP stdio 连接临时演示 API；发送 subprocess 契约使用虚构 Session/transport 替身，**不是向真实 WS 发送的验收**。日志 `resume-boundary{312,311}.txt`。
- 全量含独立真实 Chromium 单条 UI（worker关闭、只执行指定一条、历史approved不动、样本选择起草）；另运行 `scripts/smoke_ui.py` 双版本均通过，覆盖既有登录/搜索/监控/审批/人工核对/XSS/Agent隔离/图片/演示发布/移动端。日志 `resume-ui{312,311}.txt`。
- 双环境 `pip check`、`ruff check .`，`node --check xianyu_workbench/static/app.js`、`git diff --check` 均通过。命令统一 `env -u PYTHONPATH TMPDIR=/home/lan/.hermes/cache/scratch`。解释器为项目 `.venv/bin/python` 和 `/home/lan/.hermes/cache/scratch/xianyu-venv311/bin/python`；测试浏览器为专用 `xianyu-completion-evidence/browsers/chromium-1248/chrome-linux64/chrome`，独立临时 profile，`PLAYWRIGHT_BROWSERS_PATH` 指向项目 `.test-browsers` 且 `PLAYWRIGHT_SKIP_BROWSER_GC=1`。
- 未读取真实 .env/data/profile，未连接8099/9235，不启用真实发送、不push、不部署。测试仅临时虚构数据；不提交 scratch。发送 ACK 关联缺证，accepted/unconfirmed 自动区分仍未完成，始终保守 unconfirmed，不声称接受/送达。实际 Hermes 接入、真实消息、商品写、FAQ、首次联系及订单全量仍未完成，取证留给父助手/Hermes。

## 2026-10-16 仅任务 target focus emulation

基线 `3bb8734`，保留并提交已有未提交诊断脚本/文档/tests，scratch 原有文件不覆盖、不提交。父助手真实控制实验原件已读取：`/home/lan/.hermes/cache/scratch/xianyu-layout-probe.json`。同一 no_defaults=True `/personal` 页 baseline/置前均 height1241，只对任务页启用 focus emulation 后3729；hidden=false/hasFocus=true、图片93/93decoded与媒体布尔值不变，列表父容器 maxHeight480→3060px。此为真实几何恢复证据，**不是仅 document.hidden 原因，也不是工作台分页 API 验收**。具体阶段/限制见 CDP_DEFAULTS_DIAGNOSIS。

- TDD：先写 task target/session 生命周期用例，8项因缺少参数 RED；实现后32项CDP测试通过。再扩展真实 collect→adapter 边界，orders/inventory 两项因未发 focus 命令 RED（45 passed），仅这两种操作显式启用后 GREEN。保留正常前后 UID 校验；覆盖 attach/send失败、send/body取消、任务异常、后置身份改变、detach失败仍关闭page，默认关闭以及不关闭借用context/browser/原页。
- 专用 Chromium 回归补充：真实 task_page session目标记录、原页仍background/未导航未关闭、正常/真实task.cancel退出后仅剩原页、session已detach。该两项为后补集成回归，不冒称先RED。初轮只读probe和focus characterization原样保留（虚构visibility布局不是站点实现）。双Python专项各 **52 passed**（3.12 8.78s；3.11 9.01s）。既有root几何/延迟hook/750ms节流/loading/预算回归沿用。
- 首次双版本全量各 **415 passed / 1 failed / 1 warning**（3.12 156.88s；3.11 156.41s）：旧消息测试boundary替身未接受新增参数，TypeError。更新替身签名并断言focus_emulation=False，不改生产消息行为。失败日志 `/tmp/xianyu-focus-full{311,312}.log` 保留。
- 最终串行全量启用隔离浏览器、无skip：**Python 3.12.14：416 passed / 149.39s；Python 3.11.16：416 passed / 151.06s**，各1条既有Starlette/httpx弃用警告。日志 `/tmp/xianyu-focus-final{311,312}.log`。双版本独立 `scripts/smoke_ui.py` 均通过，日志 `/tmp/xianyu-focus-ui{311,312}.log`。
- 双环境pip check、ruff通过；probe和UI JS的node --check、git diff --check通过。浏览器为专用chromium-1248下载包，新临时profile、随机loopback端口、虚构数据；PLAYWRIGHT_BROWSERS_PATH为项目独立目录，SKIP_BROWSER_GC=1，清除PYTHONPATH。
- 未读取真实.env/data/profile，未连接9235/8099，无部署/push，无能力/schema扩展。session清理遵循既有取消宽限机制，断线/强杀仍不能承诺远端tab消失（见BROWSER）。**本地实现及回归完成，真实应用orders/inventory分页待父助手验收。**

## 2026-10-16 横向滚动条 / scroll root 几何修复

基线 `27298e5`。父助手报告 API inventory20/orders10、均页1/time_limit；相同 guarded_websocket/no_defaults/task_page/capture 路径下 body/root.scrollHeight=1241、innerHeight=931、root.clientHeight=916。旧算法目标310，但真实最大scrollY=325，导致回退246/到底310循环。父助手一次 scrollTo(body.scrollHeight) 达到325后2.5秒仍20卡，故本轮仅修确证几何缺陷，**不宣称唯一根因或真实 API 已恢复**。

- 严格 TDD：先在隔离 Chromium HTML 加 standards mode、200vw 横向溢出和15px可见滚动条，保留延迟渲染/hook；fixture 按真实 scroll root 到底才翻页。几何断言通过后 inventory/orders 均在 `pages_read 1 != 2` 失败。Python 3.12 RED：2 failed / 1 passed / 2 deselected（23.28s；额外通过的是原无横向溢出 late-hook 用例）；Python 3.11 RED：2 failed / 3 deselected（18.78s）。日志 `/tmp/xianyu-geometry-red{311,312}.log`。
- 最小生产修复：高度稳定检测使用 document.scrollingElement.scrollHeight；bottom 使用同一 root 的 scrollHeight - clientHeight，当前位置使用 scrollTop。不增加 selector，不改750ms节流、loading/pending暂停、64px跨tick回退、资源/总deadline、身份核验或清理；无能力/schema扩展。
- 双版本相关31项通过：3.11 87.01s，3.12 82.55s。包含新增横向滚动条、延迟hook、五页读取、loading/失败释放、资源限制、身份/原页保留/cleanup。首次并行运行3.12为30 passed / 1 failed：既有 CDP 集成 provider→bridge 的3秒超时；不改timeout或生产逻辑，原样复跑31 passed。保留失败日志 `/tmp/xianyu-geometry-related312.log`，成功日志 `related312-rerun.log` / `related311.log`（同前缀）。
- 最终串行全量启用隔离 Chromium，无 skip：Python **3.12.14：399 passed, 1 warning / 142.30s**；Python **3.11.16：399 passed, 1 warning / 141.54s**。各1条既有 Starlette/httpx 弃用警告。日志 `/tmp/xianyu-geometry-full{311,312}.log`。双环境 pip check / ruff、git diff --check 均通过。本轮未另跑独立 smoke_ui.py（全量包含浏览器/UI回归）。
- 本轮使用专用下载版 Chromium、新临时 profile、拦截 HTML/虚构数据，不读取真实 .env/data/profile，不连接8099/9235；scratch未跟踪内容不动，不push、不部署。真实API仍由父助手再测。

## 2026-10-16 页面响应 / DOM / hook 时序修复

基线 `1ef2c3f`。父助手报告部署服务 8099/worker=false，inventory API 20 条/1 页、orders 10 条/1 页，均 time_limit；直接页面延后滚动能读 personal 40 条/2 页/bool false、bought 50 条/5 页/仍 true。本轮不连接该服务/CDP、不部署，不将父助手直接页面证据写成工作台 API 通过。

- 根因：响应完成后立即只滚一次，再无限等队列至总 deadline；DOM 高度或 scroll hook 尚未就绪时错过触发，已到底时重复 scrollTo 同位置也没有事件。
- TDD RED：新增隔离 Chromium + 真实 CDP Network 的 HTML fixture，响应后延迟 2.7 秒渲染/注册 hook，两例均 `pages_read: 1 != 2`，**2 failed / 18.91s**，日志 `/tmp/xianyu-timing-red.log`。随后最小修复后相关 23 项通过。额外五页/true、loading 暂停、失败加载释放、无 self 不滚动、无响应节流测试通过（后补边界为回归，不冒称全部先 RED）。
- 改动仅页面时序：750ms tick、allowlisted loading/pending 时不滚动、高度跨 tick 稳定后滚动，已到底以分 tick 回退 64px/到底恢复事件。队列优先处理，总 deadline 不重置；原页数/items/bytes、self/UID、重复页/游标和未知订单末页边界不变。不请求重放、不点写操作、不新增 scope/schema/capability。
- Python **3.12.14：396 passed, 1 warning, 133.80s**；Python **3.11.16：396 passed, 1 warning, 136.15s**。均全量启用隔离 Chromium，无 skip；含原 CDP 所有权/UID/cleanup、相关 browser、MCP 与 UI 回归。各 1 条既有 Starlette/httpx 弃用警告。
- 双环境 pip check / ruff 通过；node --check / git diff --check 通过。双环境独立 `scripts/smoke_ui.py` 通过。日志 `/tmp/xianyu-timing-full{311,312}.log`、`/tmp/xianyu-timing-ui{311,312}.log`；额外最终等待/预算回归 17 passed。
- 浏览器为专用 `/home/lan/.hermes/cache/scratch/xianyu-completion-evidence/browsers/chromium-1248/chrome-linux64/chrome`；`PLAYWRIGHT_BROWSERS_PATH` 指向项目 `.test-browsers`，`PLAYWRIGHT_SKIP_BROWSER_GC=1`，清除 PYTHONPATH。测试仅新临时 profile/演示数据/拦截页面，不读取真实 .env/data/profile，不连 8099/9235，不重启服务；scratch 未跟踪内容保持不动。
- **本地代码回归完成，真实 API 修复效果待父助手验收。** 建议同账号再测 inventory/sync 的 count/pages_read/stop_reason/partial（40/2/end_reached/false 仅在相同页面数据且 self/末页条件满足时），orders 继续保持 partial，不预设终页 false。无 push/部署。

## 2026-10-16 本人发布列表有界分页

订单提交 8401eea 后继续商品纵向，不 push/部署。商品多页 stable ID 去重、bool false 范围末页、空末页、unknown partial、self 缺失/不符拒绝、完整读取不清历史、item/page/byte/time 限制均覆盖。安全复核发现累计字节上限可能遮蔽后续 head.self 响应，双版本 RED 重现后修复为失败，不返回可采纳部分结果。

- 本地真实 Chromium 假 personal 页面 scroll→第二页→complete，UID 改变/self=false 拒绝，原页保留。没有真实平台 I/O。
- API 缓存完整/部分/失败状态、v9→v10 历史同步保留测试；真 MCP stdio 回读范围/末页，UI 显示 self_published/页数/停止原因及非快照警示。
- 双版本 `scripts/smoke_ui.py` 通过，日志 `/home/lan/.hermes/cache/scratch/pagination-smoke-ui{311,312}.log`；只使用新临时演示配置/数据，不读取宿主项目 .env/data/profile。
- 双版本 pip check、ruff、node --check、git diff --check 通过。最终含全部浏览器 opt-in 的全量：Python 3.12 **389 passed / 86.98s**，Python 3.11 **389 passed / 82.31s**，无 skip，各 1 条既有 Starlette 弃用警告。日志 `/home/lan/.hermes/cache/scratch/pagination-verified312.log`、`pagination-verified311.log`。
- 初始 RED：`/home/lan/.hermes/cache/scratch/pagination-inventory-red{311,312}.log`；设计及父助手字段需求：`/home/lan/.hermes/cache/scratch/xianyu-pagination-plan.md` 与 OPERATION_PAGINATION.md。
- 卖出订单、下架列表、全状态库存、订单真实末页、实际平台滚动验收、实际 Hermes 注册仍未交付/未验收。FAQ 仍仅策略存储无执行，未增加任何平台写入。

## 2026-10-16 买到订单有界分页

起点 0f766ab，未 push/部署。双 Python RED 覆盖 known true、去重/重复游标、真实 capture 滚动、累计响应预算、缓存进度；UI 新进度断言先 RED 再 GREEN。首次全量失败（SQL 占位符数量、旧测试 schema v9）已修复，保留 scratch 日志。

- Python 3.12 / 3.11 全量各 **377 passed, 4 skipped**（浏览器 opt-in），各 1 条既有 Starlette warning；含 stdio MCP 与固定上游契约。
- Python 3.12 隔离 Chromium + UI + stdio MCP + 状态/缓存专项 **33 passed**（随后新增预算测试双版本各 7 passed）。假 bought 页真实 scroll→第二响应验证；订单字符串 false 仍 partial。
- 双 Python pip check、ruff、node --check、git diff --check 通过。
- 证据绝对路径：`/home/lan/.hermes/cache/scratch/pagination-{red311,red312,ui-red2,focused-green,orders-full312-final,orders-full311-final}.log`。真实平台与实际 Hermes 未验收。

## 2026-10-16 低频消息观察与有限 FAQ 策略

基线 4d5db8e；用户报告基线已部署 43 条/32 文本、350 tests / CI 五项绿。本增量未 push、未部署、未运行远端 CI，也未连接真实平台。

- 逐行为 RED→GREEN：默认关闭/管理员配置、调度到期/持久去重、退避、接管/解除权限、恢复延后、同 worker、异常失败缓存标记、capability、有限 FAQ 范围/期限/模板/加密/撤销、备份恢复撤销授权；日志 01–22。
- 真 MCP stdio：新增状态/接管工具发现和调用成功，接管后 sync 拒绝，禁止管理员令牌/授权工具。隔离 Chromium UI：配置→接管→解除、FAQ 保存→撤销通过。
- 独立审查发现旧审批接管后快速解除可能执行、FAQ 表单跨账号残留；两项均先 RED 后修复（23–26 日志）。接管事务立即阻止 pending/approved 消息，UI 切换清空并加载当前账号策略。复审未发现这两项修复的剩余实质问题；审查者独立执行相关测试 23 passed，未独立重跑 UI。
- timeout 接续后的最终完整回归：Python **3.12.14：373 passed, 1 warning, 97.68s**；Python **3.11.16：373 passed, 1 warning, 96.76s**，均无跳过，包含真实 MCP stdio 与隔离浏览器测试。唯一警告为既有 Starlette/httpx 弃用提示。双版本独立 `scripts/smoke_ui.py` 均通过，包含观察配置/接管/解除及 FAQ 保存/撤销/切账号清理。
- 最终命令均使用 `env -u PYTHONPATH TMPDIR=/home/lan/.hermes/cache/scratch`；已核对两个解释器导入的包均为 `/home/lan/projects/xianyu/xianyu_workbench`，未使用全局 PYTHONPATH 旧快照。Python 路径分别为项目 `.venv/bin/python`、`/home/lan/.hermes/cache/scratch/xianyu-venv311/bin/python`。`XY_TEST_CHROMIUM=/home/lan/.hermes/cache/scratch/xianyu-completion-evidence/browsers/chromium-1248/chrome-linux64/chrome`，这是专用下载版，**不是系统 Chromium**。
- 最终证据：`resume-verified311.log` / `resume-verified312.log`、`resume-ui311.log` / `resume-ui312.log`、`resume-checks.log`。旧 `review-final311/312.log` 被原进程 timeout 截断，不算通过；接续首次 `resume-final312.log` 使用了不存在的 chrome-linux 路径，主动停止后改用已核对的 chrome-linux64 路径重新全量验证，不把该次尝试计为通过。
- `ruff check .`、`node --check xianyu_workbench/static/app.js`、`git diff --check` 与双环境 `pip check` 通过。测试均用临时虚构数据、随机端口、新 profile；浏览器专用路径 `/home/lan/.hermes/cache/scratch/xianyu-completion-evidence/browsers`，`PLAYWRIGHT_SKIP_BROWSER_GC=1`。
- 全部证据绝对路径 `/home/lan/.hermes/cache/scratch/xianyu-completion-evidence/`。未读取真实 .env/data/profile、未连接 8099/9235；未跟踪 repo scratch 保留。无真实自动回复；autonomous_reply=false。完整分页/商品写/首次联系/实际 Hermes 注册仍未交付。

## 2026-10-15 严格 JSON 常量审查修复（历史）

用户报告精确快照 `24aa585e9cb18aafb26e3f7d0cfcc645b1c9c796` 独立审查 **FAIL**：`json.loads` 默认接受 `NaN`、`Infinity`、`-Infinity`，即使出现在未使用字段中，正文仍被标为 available。此前本地全绿不代表严格 JSON 契约成立，也不覆盖本次独立审查失败。

- TDD：完整 `normalize_messages` 路径参数化三常量 × 顶层 ignored / 嵌套对象与数组，共 **6 failed**（实际返回 ordinary 而非 None）→最小修复后消息相关 **47 passed**。不是绕过未使用字段，而是在 JSON 解码时通过显式 `parse_constant` 全局拒绝三常量，沿原 ValueError 路径返回 body=None / unavailable。
- 保留 duplicate key、字节/深度/节点/正文资源限制与 opaque ID 逻辑；pair 独立核验语义不变，正文不可用不伪造收件人核验失败。回归同时检查原始 message_id 与 peer_uid。
- Python **3.12.14：350 passed, 1 warning, 71.98s**；Python **3.11.16：350 passed, 1 warning, 72.25s**，均无跳过。双环境 `pip check` / `ruff check .` 通过；唯一警告为既有 Starlette/httpx 弃用提示。
- 全量启用独立 Chromium，含本地随机端口 CDP/WS、MCP stdio 与 UI 回归；另执行完整 `scripts/smoke_ui.py` 通过，`node --check xianyu_workbench/static/app.js` / `git diff --check` 通过。仅临时虚构数据/新 profile，不是平台或真实账号验收。
- 环境：`TMPDIR=/home/lan/.hermes/cache/scratch`、`PLAYWRIGHT_BROWSERS_PATH=/home/lan/projects/xianyu/.test-browsers`、`PLAYWRIGHT_SKIP_BROWSER_GC=1`、`XY_TEST_CHROMIUM=/snap/bin/chromium`。证据 `red.log` / `green.log` / `full311.log` / `full312.log` / `ui.log` 在 `/home/lan/.hermes/cache/scratch/xianyu-strict-json-evidence/`，不入库。
- 本次仅提交 `xianyu_workbench/message_text.py`、`tests/test_message_text.py` 和本报告，提交主题 `fix: reject nonstandard JSON constants in message text`。无能力扩展、无迁移，不改真实 .env/data/profile，不连接 8099/9235，不部署、不 push。独立复审尚未执行，不宣称审查 PASS 或可上线；既往 FAIL 历史保留如下。

## 2026-10-15 独立审查反馈修复（历史）

用户报告精确快照 da3e2ad 独立审查 FAIL，不可上线。问题一（数字 messageId）已于 433a1be 修复并保留原始 opaque ID 回归；该 ID/text 增量不因本地测试通过而视为独立审查通过。

问题二在 433a1be 仍存在：operations_cache 未保留 response_limit/page_redirected/cid_mismatch。新增明确白名单，同时将 HTTP 错误改为相同安全 code + 固定提示，禁止裸 raise 转出任意 Problem.message。未知 code 仍统一 collection_failed，不存储/返回异常原文。

参数化 3 类样本 × 5 类错误（含未知秘密字符串）共 15 项 RED→GREEN，断言 HTTP 失败、旧记录/密文不变、last_sync 准确安全码，以及 HTTP/缓存/同步记录无假 secret/电话/地址。另复跑 opaque ID 原样保留测试。

最终 Python 3.12：**344 passed, 1 warning, 67.05s**；Python 3.11：**344 passed, 1 warning, 67.35s**，启用独立 Chromium、包含 MCP stdio/UI/本地 WS，无跳过；双 pip check/ruff 通过。唯一警告为既有 Starlette/httpx 弃用。证据 safe-code-red/green、review-final311/312.log 在 `/home/lan/.hermes/cache/scratch/xianyu-messages-evidence`，TMPDIR 保持 scratch 根目录。无真实访问、部署或 push；本修复及 433a1be 均需父助手独立复审，未宣称可上线。

## 2026-10-15 编码与草稿增量（历史）

基线 da3e2ad。父助手新增脱敏证据只读读取，未连接真实平台。opaque ID RED：`1234567890123.AbC` 被纯数字拒绝→原样通过；路径/控制/超长拒绝。普通文本/peer RED→GREEN；未知/恶意编码保持 unavailable。选定样本草稿缺 sample_id/路由 RED→GREEN；MCP 缺工具 RED→GREEN；UI 正文不可见 RED→GREEN；失败采集旧缓存草稿 RED→409。未将既有保护首次即通过写成 RED。

- Python 3.12 **329 passed, 1 warning, 64.09s**；3.11 **329 passed, 1 warning, 65.41s**（含追加毫秒 13 位校验 RED/GREEN）。均启用独立 `/snap/bin/chromium`、无跳过；唯一既有 Starlette/httpx 弃用警告。
- 双环境 pip check/ruff、node check、diff check、完整 smoke_ui 通过。真实 MCP stdio 的本地草稿调用与无 actions 副作用通过；Agent UI 可读正文 textContent/XSS、按需生成、账号切换通过。
- 隔离 TLS WebSocket→真实 Chromium→bridge 子进程使用新 opaque ID 与 base64 普通文本 fixture，通过；不发送 IM 协议，真实平台未验收。
- v8 加密草稿表、错误密钥验证、备份恢复不重放回归通过。中途 3.12 全量 2 failed/320 passed：旧 v2 fixture 未删除新增表、UI 并发刷新导致草稿输出被覆盖；修复 fixture 表降级和等待按钮异步完成后双版本全绿。
- TMPDIR 始终 `/home/lan/.hermes/cache/scratch`；日志在其 `xianyu-messages-evidence` 子目录，不入库。无部署/push、无 8099/9235 或真实 .env/data/profile 读取。
- 仅 local_template 本地建议，不调用模型、不创建发送提案；CDP 写仍拒绝。自动监听/FAQ/分页/真实发送、首次聊天、发布改价上下架及 Hermes 实际接入未完成。详细契约见 MESSAGES。

## 2026-10-15 第三批：末条消息元数据样本（历史）

基线 b0e84fe；实现范围和证据需求见 [MESSAGES](MESSAGES.md)。本批只交付 partial_messages 元数据，不把正文未知伪装成可回复；无后台监听/自动回复，无部署/push，无真实账号访问。用户提供前批真实订单/商品 10/20 条与 CI 38744034233 五作业成功，本批未重新连接验证。

- TDD：parser 12 项缺函数 RED→GREEN；collector 6 项缺函数 RED→GREEN；HTTP/capabilities 缺路由/能力 RED→GREEN；CDP propose 201→409 RED/GREEN；真实 MCP stdio 缺两工具→GREEN；UI 缺按钮→GREEN；深度限制及 collector 安全错误码 RED→GREEN；v7 迁移断言 6→7。迁移/恢复额外验收首跑即通过，不冒称全部为新增 RED。
- 全量 Python 3.12：**294 passed, 1 warning, 62.45s**；3.11：**294 passed, 1 warning, 63.67s**，均启用 `XY_TEST_CHROMIUM=/snap/bin/chromium`，无跳过。双环境 pip check/ruff、node --check、git diff --check 通过。唯一警告为既有 Starlette/httpx 弃用。
- 完整 smoke_ui 通过；Agent UI 样本读取/切账号清空/无提案按钮、原 XSS/移动端回归通过。真实 MCP SDK stdio→临时 API 新工具与管理员令牌拒绝通过。
- 实际 Chromium 全新 profile + 随机 CDP + 本地 TLS WebSocket：provider→真实 bridge→Network.webSocketFrameReceived→元数据输出通过；本地 WS 接收列表为空（未发 IM 协议）。已有页/浏览器保留；原超时取消/UID 切换回归通过。fixture 首用 Playwright WS 拦截未产生真实 CDP 网络帧，改成本地 TLS server；Chromium LocalNetworkAccessChecks 拦截 localhost 映射，测试专用禁用该特性后通过，不修改生产参数。
- 中途全量曾因 UI 登录异步结束后覆盖导航导致双环境各 1 failed/293 passed；fixture 改为等待登录按钮恢复 enabled（而非默认可见 overview），后双版本全绿。保留失败日志，不把中途结果抹除。
- v6→v7 一致性备份、密文保留、错误密钥与 0600 权限；离线恢复包含消息缓存但旧任务不重放；多账号 HMAC、重复稳定 ID、失败不清库验证通过。
- 日志绝对目录 `/home/lan/.hermes/cache/scratch/xianyu-messages-evidence`，不入库。实际闲鱼消息、正文编码、收件人、真实模型与 Hermes connector 未验收。首次聊天、发布冻结、改价上下架、分页/后台消息/无人值守 FAQ 仍未完成。

## 2026-10-15 运营第二批：只读单页样本（历史）

基线 465f898，完成 orders/inventory 的受限 CDP 网络监听 → 最小字段 → v6 加密缓存 → API/UI/MCP。契约见 [OPERATIONS_SAMPLES](OPERATIONS_SAMPLES.md)。真实 bought/personal 的结构证据来自已授权父助手；开发测试仅虚构数据，不连接真实平台或 8099/9235，不读取真实 .env/data/profile。未 push/部署，Windows 暂停不变。

- TDD RED/GREEN：parser（17 项缺模块→通过）、listener（8 项缺模块→通过）、cache/API（缺路由/白名单→通过）、surfaces（真实 stdio 缺工具、Chromium 缺页面按钮→通过）、cursor（3 项类型错误未审计→通过）、audit（持久 has_more/reported_total 缺失→通过）。日志在 `/home/lan/.hermes/cache/scratch/xianyu-operations2-evidence/`，不入 Git。
- 缓存首次 GREEN 尝试发现重启测试错误地同时开启两实例，被既有锁正确拒绝；测试改为顺序关闭/重启，未放宽单实例保护。首次全回归 2 failed / 260 passed / 4 skipped：旧 v2 恢复 fixture 未移除新增表、旧 CDP capability 断言只允许 search；修正历史 fixture/契约，生产迁移不使用 IF NOT EXISTS 掩盖错误。
- 实际隔离 Chromium：新 profile、随机 CDP 端口、fixture 假 unb、所有页面请求拦截成本地虚构响应；真实 Network.responseReceived/loadingFinished/getResponseBody 链路通过。Provider→真实 bridge 子进程→CDP 正常输出及超时取消通过；self=false、前后 UID 变化拒绝，原页/浏览器存活，自建任务页关闭。这不是闲鱼真实账号验收。
- 真实 MCP SDK stdio + 随机端口 Uvicorn：新增四工具发现/调用、partial 标记；既有管理员令牌拒绝回归保留。临时 Chromium 新样本页同步、切账号清空、XSS textContent、移动端通过。完整 `scripts/smoke_ui.py` 同时通过原审批/草稿/通知/人工核对回归。
- 最终 Python **3.12.14：271 passed, 1 warning in 58.26s**；Python **3.11.16：271 passed, 1 warning in 58.64s**。两环境 pip check、ruff 全部通过；全量启用 XY_TEST_CHROMIUM，含固定上游契约，无跳过。唯一警告是既有 Starlette/httpx 弃用提示。node --check / git diff --check 通过。
- 单页始终 partial；订单字符串 nextPage 语义未知记录错误，不猜值或执行翻页。商品 false 也不等于全状态库存。空页/失败不清库、账号隔离、重启幂等、错误密钥、v5 迁移与权限测试通过。
- 未完成/未验收：实际平台采集与实际 Hermes connector、分页遍历和全状态集合、消息解析/编码/按需采集/增量监听。消息稳定 ID 结构已有证据，不能再否定其存在；本批没有用 stub 冒充 listener。首次联系、真实发布/改价/上下架和所有交易执行均未新增。

复现环境：`TMPDIR=/home/lan/.hermes/cache/scratch/xianyu-operations2-evidence PLAYWRIGHT_BROWSERS_PATH=/home/lan/projects/xianyu/.test-browsers PLAYWRIGHT_SKIP_BROWSER_GC=1 XY_TEST_CHROMIUM=/snap/bin/chromium`；分别使用 `.venv/bin/python` 和 `/home/lan/.hermes/cache/scratch/xianyu-venv311/bin/python` 执行 `-m pip check`、`-m ruff check .`、`-m pytest -q`。

## 2026-10-15 Linux / WSL 优先收尾（历史）

默认支持 Linux / WSL（Python 3.11/3.12），**Windows 原生支持暂停**。用户提供的 [CI run 38727928186](https://github.com/lanchenglin/xianyu/actions/runs/38727928186) 对应 `53400f82f1ce4f1b1322f184b4b15e2e2c949e97`，整体失败，不能记为全绿：

| 作业 | 结果 |
|---|---|
| tests：ubuntu-latest，Python 3.11 / 3.12 | 两项通过 |
| upstream-contract：Ubuntu，Python 3.11 / 3.12 | 两项通过 |
| browser-smoke：Ubuntu | 通过 |
| tests：windows-latest，Python 3.11 / 3.12 | 两项失败，未继续修复 |

独立分支 `work/windows-support-53400f8` 已由父助手创建并 push 保存上述快照；本轮本地分支及 origin 追踪引用均核对为该 SHA。本机无 `gh` 命令，本轮未重新获取 CI 日志，不推断 Windows 失败原因。此前 run 38708963492 / 38679746659 等失败及更早基线成功记录仍保留在下文。

当前 `feat/local-next` 仅将 CI tests 的 OS 矩阵改为 `ubuntu-latest`，保留 Python 3.11/3.12、双版本 upstream-contract、browser-smoke 和所有原检查步骤；跨平台源码及回归未删除或跳过。Windows 后续工作留在独立分支，**新的 Linux 全绿不代表 Windows 已修复或恢复支持**，也不代表真实平台验收。本轮不 push，新矩阵尚未远端运行。

本轮配置/文档验证：

- YAML 实际解析并与 HEAD 配置深比较：唯一变化为 tests OS 矩阵移除 windows-latest；Ubuntu Python 3.11/3.12 及其他 Linux 门槛、步骤保持不变。
- 本机 Python 3.12：`ruff check .`、`pip check`、`git diff --check` 通过；`TMPDIR="$PWD/scratch" PLAYWRIGHT_BROWSERS_PATH="$PWD/.test-browsers" PLAYWRIGHT_SKIP_BROWSER_GC=1 XY_TEST_CHROMIUM=/snap/bin/chromium .venv/bin/python -m pytest -q`：**232 passed, 1 warning in 41.38s**，唯一警告为既有 Starlette/httpx 弃用提示。
- 本轮未重跑 Python 3.11 或 UI smoke；`53400f8` 双版本 232 passed 及 UI smoke 属此前验证，不冒称本轮结果。没有访问真实平台、修改 .env/data/已有 profile、重启服务或修改 Hermes 配置；scratch 测试临时文件/日志不提交。

## 2026-10-15 运营增量第一批（历史）

起点 121f3c8；实现站内通知状态、管理员显式授权的外部固定摘要通知和 MCP stdio 真协议测试。schema v4/v5 增量迁移；备份恢复关闭外部通知并取消待发任务。完整需求尚未完成，矩阵与下一断点见 [OPERATIONS_NEXT](OPERATIONS_NEXT.md)。

- RED 证据：notices-red（4 个缺路由失败）、notices-ui-red（缺已读按钮）、external-red（缺模块/配置路由）、transport-red（缺 send）、worker-red（重启状态/worker 未接通）、disable-red、external-ui-red、restore-red、mcp-red（缺新工具；既有管理员令牌拒绝首次通过）、dns-red、deadline-red、detached-deadline-red、capabilities-red。
- GREEN 与集成：本批新增 23 项；真实本地 TLS 接收端完成 API 配置→持久通知→真实 HTTPS/证书/SNI/签名→已投递→不重复；仅网络边界将验证地址映射随机 loopback，生产无放宽开关。此集成首次通过，未冒称其单独有 RED。钉钉/真实外部 webhook 未发送、未验收。
- 首次完整回归 221 passed / 1 failed：旧 v2 备份夹具仍携带新增通知表；修夹具以真实重建旧结构，未放宽生产迁移。DNS/连接/响应上限、退避三次、配置取消、恢复关闭、Agent 拒绝配置、凭据隐藏均有测试；HTTP 2xx 不是人已读，超时重试可能重复通知。
- MCP 使用真实 SDK ClientSession + stdio 子进程 + 随机端口临时 Uvicorn，initialize/list_tools/call_tool、通知归档、固定目标参数边界、管理员令牌拒绝通过；不等于实际 Hermes connector 已安装联调。
- 最终 Linux Python 3.12：**231 passed, 1 warning in 41.73s**；Python 3.11：**231 passed, 1 warning in 43.32s**。双版本 pip check / ruff 均通过，固定 live 契约及隔离浏览器测试包含在全量中。
- 系统 Chromium 临时 profile UI smoke 通过，新增关闭状态通知配置（未启用）、密钥输入清空、已读/归档控件；原审批/草稿/移动端回归保持。node --check / git diff --check 通过。警告仍是既有 Starlette/httpx 弃用提示。
- 证据目录 `scratch/xianyu-operations-evidence/`，不入 Git。未读取真实 .env/data/profile、未连接 8099/9235、未执行平台操作/真实通知、未部署/push。Windows 新 CI、真实账号/钉钉/Hermes 均未验收。

### 通知传输自审修复

功能提交 `07fb1a2` 后发现 HTTPConnection 在 Connection: close 响应时可能解除 socket 引用；截止计时已保留传输 socket，但拒绝/超限响应还应显式关闭 HTTPResponse。`response-close-red.log` 实际断言失败（close 未调用），补 finally 关闭后完整双版本重跑：3.12 **232 passed, 1 warning in 42.82s**；3.11 **232 passed, 1 warning in 41.85s**。ruff / node --check / git diff --check 通过。证据 `review-final312.log` / `review-final311.log`。没有新增平台/外部联网验收。

## 2026-10-15 Windows 浏览器测试夹具修复（历史）

基线 `161968e` 已由 Hermes push。[CI run 38708963492](https://github.com/lanchenglin/xianyu/actions/runs/38708963492) 的 Windows Python 3.11/3.12 失败，其余 5 作业通过（用户提供的运行状态）。已核对本地 `scratch/xianyu-browser-ci/311.log`：3.11 为 2 failed、191 passed、3 skipped；两条失败如下，保留失败记录，不宣称原 CI 全绿。

1. 浏览器测试 runtime 只设置 HOME，Windows Path.home 使用 USERPROFILE，测试 profile 落到 runneradmin 目录。核对生产 provider：已经同时将 HOME/USERPROFILE 设置为账号独立 runtime，不存在同一遗漏。本次仅修测试夹具同时设置两者；增加 HOME/USERPROFILE 选择的参数化回归和精确 profile 父目录断言，并在 provider 测试中注入不同的假宿主 home，确认两个子进程变量都被覆盖。
2. Windows 上模拟 POSIX 的测试仅替换 os.name，仍使用宿主 signal，缺少 SIGKILL。生产 Windows 走 taskkill，不访问 SIGKILL。本次使用测试局部 signal 模拟：POSIX 提供独立 SIGKILL 标记并核对 killpg 的精确参数；NT 刻意没有 SIGKILL，验证 taskkill 且不调用 killpg。不修改全局 signal，不删除/跳过 Windows 测试。

RED/GREEN：在 Linux 临时目录模拟 USERPROFILE home 选择和缺少 SIGKILL，修复前实际得到 2 failed、2 passed，分别为错误 profile 父目录与 AttributeError；最小修复后目标测试通过。未访问真实 profile，失败复现中的所有路径也在临时目录内。

最终本地验证（均设置 TMPDIR、独立 Playwright 缓存和 XY_TEST_CHROMIUM=/snap/bin/chromium）：

- Python 3.12：**208 passed, 1 warning in 34.69s**；pip check / ruff 通过。
- Python 3.11：**208 passed, 1 warning in 35.67s**；pip check / ruff 通过。
- 包含固定上游契约、真实隔离 Chromium/about:blank、本地 HTML、随机端口 CDP 和正常 operation timeout 页清理；仅既有 Starlette 弃用警告。
- 本次仅修改测试与本文档，生产浏览器/取消/凭据行为不变。新 Windows CI 尚未运行，必须由 Hermes 验收后 push 验证，不以 Linux 模拟冒充 Windows 实测。
- 未读真实 .env/data/profile、未连接 9235、未访问或重启 8099。用户报告 Hermes 已启用绑定账号 CDP search 并真实成功、worker=false；本轮未独立重复该线上验证，保持线上不动。

## 2026-10-15 独立审查修复（历史）

核对 `19ffe7e` 后确认两条源码问题仍存在，实现修复提交 `4732162`：CDP provider 曾解密并写入导入 Cookie；operation timeout 曾直接强杀，绕过任务页 finally。

- TDD：Cookie 禁止解密、取消通知/有界等待、不把超时当成功、协程清理共 4 项先 RED 后 GREEN；固定上游 Session 回读保护另行 RED/GREEN。
- 真实 Chromium 超时反证：在独立随机端口/假 uid fixture 中临时移除 cancellation_scope，5 秒 operation timeout 后页数为 2（预期 1），测试确实失败；恢复后通过。测试走真实 provider、bridge.main、适配与 Playwright，只将平台业务替换成本地 HTML + 等待，未访问闲鱼。超时后任务页消失，原页标题、浏览器进程和 Cookie 保留。没有连接 9235。
- Linux/Windows 强杀兜底分支有模拟测试：先等 8 秒协作清理，再 SIGKILL 进程组 / taskkill，回收最多 5 秒；超时始终 timeout/uncertain，不重放。Windows 未本机实测，不宣称实测。
- 项目 `.venv` Python 3.12：**207 passed, 1 warning in 32.46s**；独立 Python 3.11：**207 passed, 1 warning in 33.95s**。两者 pip check、ruff 均通过，含 12 项固定上游契约及真实隔离浏览器测试。此前其他审查环境缺包不代表本项目 venv 缺包。
- 隔离演示 UI smoke、node --check、git diff --check 通过。仅既有 Starlette 弃用警告。
- 未读真实 .env/data/profile、不重启现有服务、不连接真实 CDP、不 push。强杀/断线/事件循环阻塞仍不能保证关闭自建页，兜底边界见 [BROWSER.md](BROWSER.md)。未扩展 CDP 功能，仍仅 search。

## 2026-10-15 浏览器适配增量（历史）

基线 HEAD `1fc1a7d`，实现提交 `07c930b`，分支 `feat/local-next`。未读取实际 .env/data/profile，未连接现有 8099 或 9235，未重启服务。仅源码、假数据临时目录和随机端口独立进程。未 push/merge。

- 分组 RED/GREEN：发现 6 项、CDP 初始 22 项、页面适配初始 9 项、配置/provider/doctor 初始 7 项均先观察缺功能失败再实现；后续 WebSocket 重定向、可操作错误提示、no_defaults 均记录 RED 后 GREEN。实测生命周期与契约增补是集成验收，不冒称每条均先 RED。
- 最终 Python 3.12：199 passed, 1 warning in 29.21s；Python 3.11：199 passed, 1 warning in 29.52s。两者均启用 `XY_TEST_CHROMIUM=/snap/bin/chromium`，各 pip check / ruff 通过；包含 11 项固定上游契约及 2 项系统 Chromium 隔离实测。固定 commit 不变、未改 site-packages。
- doctor 在显式干净环境中实际输出 discovered=[chromium]、selected=chromium、mode=isolated、reason=null、connection_checked=false；没有发现 Chrome，不声称 Chrome 实测。
- 系统 Chromium 真实隔离测试：全新临时 HOME/profile，headless about:blank/本地 HTML；随机 CDP 端口，假 uid=12345；任务页正常/异常退出后关闭，Cookie 未被适配替换，原页标题/数量及浏览器进程保持，两次 Playwright 断开后再次连接确认存活。snap HOME 隔离在本机 scratch 路径实际成功。
- 演示 UI smoke 通过：登录、账号、搜索、监控、消息草稿/审批、人工核对、证据 XSS 与 Agent 隔离、图片上传、演示发布、移动端、退出。服务与数据库均临时，未使用现有服务。
- node --check、git diff --check 通过。测试有 1 条既有 Starlette httpx 弃用警告。
- **未实测 Google Chrome、Windows GUI、WSLg 用户窗口、真实闲鱼、真实登录 CDP、真实客户端与新远端 CI**。Windows 安装路径和 Chrome 选择仅模拟单测。CDP 实现只支持 search，item/消息/所有写操作明确拒绝。

复现（Python 3.11 用独立 venv 路径替换）：

```bash
export TMPDIR=/home/lan/.hermes/cache/scratch
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.test-browsers"
export PLAYWRIGHT_SKIP_BROWSER_GC=1
export XY_TEST_CHROMIUM=/snap/bin/chromium
.venv/bin/python -m pip check
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest -q
.venv/bin/python scripts/smoke_ui.py
node --check xianyu_workbench/static/app.js
```

路径为本次测试环境示例，不是生产默认。设计、配置与剩余限制见 [BROWSER.md](BROWSER.md)，由 Hermes 独立审查后负责真实只读验证。

## 已执行

开发测试环境：Linux，独立 Python 3.12.14 虚拟环境。真实闲鱼登录态未提供，测试没有登录闲鱼，没有实际发送消息、发布商品、删除商品或进行交易。

| 检查 | 结果 |
|---|---|
| `ruff check .` | 通过 |
| Python 模块编译检查 | 通过 |
| `pytest -q`（含固定上游依赖） | **69 passed** |
| 前端 JavaScript `node --check` | 通过 |
| 固定上游 Git 提交核验 | c2d5a02ad83b18863514389cedf7afbd993b683d |

69 项测试由 59 项工作台测试与 10 项上游契约测试组成。覆盖：

- 未认证访问、管理员/Agent 权限分离；Agent 不能审批、导入账号或读取模型配置。
- 幂等、内容摘要、重复领取、并发领取、审批过期、拒绝、崩溃恢复。
- 演示消息和发布完整流程；真实执行默认关闭；演示结果不含真实商品链接。
- 超时不重发、暂停后不重放旧任务、收件人与会话核验。
- 商品删除确认文字与归属校验；付款、退款、下单、确认收货等操作不存在。
- 图片类型、任意本地路径拒绝、跨账号素材拒绝、素材修改后停止执行。
- 登录态加密、禁止跨账号覆盖、请求/结果不回显凭据；模型密钥加密与不回读。
- 搜索过滤、无效价格处理、去重、监控最低间隔和通知去重。
- MCP 工具发现和危险工具缺席；不是某款 Hermes Desktop 的实际接入测试。
- 上游函数签名、禁用认证重试的参数、固定提交与 Decimal 金额分单位计算。

测试过程中发现：直接导入上游会修改全局 `subprocess.Popen`，导致 MCP SDK 类型声明异常。工作台实际连接原本就采用独立子进程；契约测试也已改为子进程运行，之后完整测试通过。禁止未来把上游业务模块导入 FastAPI/MCP 主进程。

当前依赖测试过程中出现 1 条 Starlette 关于 httpx TestClient 的弃用警告，不是测试失败；后续可按依赖更新统一处理。

## 上传后 GitHub CI 核对（2026-10-14）

代码基线：`64556d84c7eed63222dd1352daff69293b8b98c0`。实查 [CI #1 / run 38535793804](https://github.com/lanchenglin/xianyu/actions/runs/38535793804)，总结果为 **failure**，不是全绿。分作业如下：

| 作业 | 结果 |
|---|---|
| tests (ubuntu-latest, 3.12) | 安装、ruff 与 pytest 通过 |
| tests (windows-latest, 3.12) | 安装、ruff 与 pytest 通过 |
| upstream-contract（Ubuntu / Python 3.12） | 通过；不是登录闲鱼的业务测试 |
| browser-smoke（Ubuntu / Python 3.12） | 演示页面交互通过；补上本地浏览器下载失败后未执行的这部分 CI 验证 |
| tests (ubuntu-latest, 3.11) | 安装 requirements-dev.lock 失败；后续测试跳过 |
| tests (windows-latest, 3.11) | 安装 requirements-dev.lock 失败；后续测试跳过 |

已读取 [Windows 3.11 作业日志](https://github.com/lanchenglin/xianyu/actions/runs/38535793804/job/115758224434)：`pyee==14.0.0` 需要 Python >=3.12，当前开发锁文件无条件固定该版本。运行锁文件不包含 pyee；不能直接据此推断所有 3.11 基础演示安装失败。完整开发/live 环境先使用 3.12，修复依赖和重跑兼容矩阵列为 [交接清单 P0-ENV](DEVELOPMENT_HANDOFF.md)。本次仅更新文档，不改变源码、锁文件或 CI 配置。

基础测试矩阵不安装 live 可选依赖；其成功不能代替上游契约作业，更不能代替真实平台操作。Windows CI 使用托管 Windows Server 环境，不是主人 Windows 桌面的 Chrome/登录态环境。这里的记录绑定上述历史提交，不表示以后所有提交或文档提交后的 CI 也通过。

## 首次验收状态与仍需本地确认的项目（2026-10-14 历史）

| 项目 | 当前状态 |
|---|---|
| Playwright 页面交互烟雾测试 | 首次本地下载超时未执行；上传后 Ubuntu CI 已通过演示页面测试，主人本地环境仍需验证 |
| Windows 3.11/3.12 | Windows CI 3.12 基础测试通过；3.11 开发依赖安装失败；主人电脑真实部署未验收 |
| Docker 镜像构建与运行 | 配置已提供，未在本次环境构建验收 |
| Hermes / Claude / Codex 客户端联调 | 通用 MCP 配置已提供，未在你的实际客户端运行 |
| 真实商品搜索和消息 | 未提供账号登录态，未测试 |
| 真实发布、删除、送达状态 | 未执行；必须人工审批后逐条验收 |
| 模型服务实际联网生成 | 未提供 API 配置；仅完成配置/错误边界测试 |

## 本次文档交接检查（2026-10-14）

本次只修改 README、AGENTS 和 docs 下的 Markdown，源码、依赖锁、CI 配置与部署配置未改动。

| 检查 | 结果 |
|---|---|
| 6 份变更文档的 UTF-8、代码围栏、64 个本地文档链接 | 通过 |
| `git diff --check` | 通过 |
| Linux / Python 3.12.14，当前工作副本 `ruff check --no-cache .` | 通过 |
| 当前工作副本完整 `pytest -q -p no:cacheprovider` | 69 passed，1 条已有 TestClient 弃用警告 |

此轮没有重新运行真实平台操作或本地浏览器页面测试，也没有修复/重新验收 Python 3.11 依赖。CI 分环境结论仍以绑定具体提交的记录为准。

## P0-ENV 本轮本地修复验收（2026-10-14）

原始 HEAD `2ea8d3b`，分支 `feat/local-next`，WSL/Linux。原始 3.12 基线：`59 passed, 1 skipped, 1 warning`；跳过的是未安装 live 的契约模块。3.11 原锁真实安装退出 1：`No matching distribution found for pyee==14.0.0`。

修复：Playwright 1.64 条件依赖，由明确 3.11 下限的 uv universal 解析生成；3.11 为 pyee 13.0.1，3.12 为 14.0.0。运行锁同步生成（包版本未变）。固定上游提交未变。

实际命令：

```bash
uv pip compile pyproject.toml --extra mcp --extra dev --universal --python-version 3.11 --output-file requirements-dev.lock
uv pip compile pyproject.toml --extra mcp --universal --python-version 3.11 --output-file requirements.lock
# 各独立环境中执行
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps -e .
python -m pip check
ruff check .
pytest -q
python -m pip install -e '.[live]'
python -m pip check
pytest -q
```

| 本轮环境 | 实际结果 |
|---|---|
| Python 3.12.14 `.venv` | pip check: No broken requirements found；ruff: All checks passed；含 live：69 passed, 1 warning in 9.48s |
| Python 3.11.16 scratch 独立环境 | pip check/ruff 通过；基础 59 passed, 1 skipped；含 live：69 passed, 1 warning in 9.71s |
| Windows | 未执行新 CI，不声称修复后 Windows 已通过 |

警告为已有 Starlette TestClient 弃用警告。安装 RED/GREEN 日志保存在 `/home/lan/.hermes/cache/scratch/xianyu-next-evidence/`。没有登录或请求闲鱼；契约仅子进程导入与函数检查。

## P2-04 必要迁移基础验收

本轮增加 5 项迁移测试和 1 项错误密钥测试。版本升级、未来版本、WAL 备份、迁移锁、错误密钥各自先运行单个失败测试，再最小实现通过；失败回滚为已实现事务的附加回归，首次即通过，不伪称 RED。日志为 scratch 证据目录中 `migration-*`、`future-*`、`backup-*`、`wrong-key-*`。

`TMPDIR=/home/lan/.hermes/cache/scratch .venv/bin/pytest -q`：**75 passed, 1 warning in 8.97s**。已有 TestClient 警告。完整回归包括领取并发、超时不重试、重启不重放、错误收件人和交易/未知操作拒绝。发现旧初始化发生于服务锁之前，新增 RED 测试后将迁移置于同一个实例锁下。

范围：无恢复 CLI、无自动备份/保留策略；未做真实数据恢复或账号验证。

## P1-02 人工核对与最终回归（2026-10-14）

本节是本轮最终结果；上面的 69 / 75 项及历史 CI 记录为各阶段真实结果，不覆盖、不冒充当前数量。交付分支 `feat/local-next`，起点 `2ea8d3b`；依赖修复提交 `80afd54`，迁移基础提交 `8ab9533`；第三项源码/测试/文档在本节同一提交中（`feat: add admin-only manual reconciliation without replay`）。

### 实际完成与测试范围

- 管理员核对 API 与中文 UI；原操作/账号绑定，仅 `unconfirmed/submitted/blocked` 可核对；原执行状态、结果、错误原样保留。
- 每操作一次不可覆盖记录；同键同内容幂等，修改内容、换键覆盖或跨操作复用键 409；并发相同请求仅落库/审计一次，不同请求仅一方成功。
- 核对与审计同事务；证据正文加密，审计不含正文；Agent 不可核对或审批，仅能读取核对结论/时间等概要，不能读证据。MCP 无新增核对/审批工具。
- schema v2 独立核对表；旧库和 v1 无损升级，备份含 WAL，失败回滚、备份失败停止升级、未来版本拒绝、单实例锁及错误密钥保护。
- 自审发现 SQLite connection context manager 不负责 close；先跑 `migration-close-red.log` 确认失败，再用 `closing` 显式关闭 probe/source/target，`migration-close-green.log`：`1 passed in 0.23s`。这只是本地连接生命周期验证，不是 Windows 实测。
- 完整回归仍覆盖 Agent 不可审批、跨账号拒绝、幂等冲突、并发领取/核对、超时/重启不重放、错误收件人不发送及未知/交易动作拒绝。

### 最终实际输出

| 环境 / 检查 | 结果 |
|---|---|
| WSL/Linux Python 3.12.14：pip check | `No broken requirements found.` |
| Python 3.12.14：ruff check . | `All checks passed!` |
| Python 3.12.14：pytest -q | **107 passed, 1 warning in 12.94s** |
| WSL/Linux Python 3.11.16：pip check | `No broken requirements found.` |
| Python 3.11.16：ruff check . | `All checks passed!` |
| Python 3.11.16：pytest -q | **107 passed, 1 warning in 13.40s** |
| `node --check xianyu_workbench/static/app.js` | 退出 0 |
| `git diff --check` | 退出 0 |
| 系统 Chromium 155.0.8059.39 + Playwright 1.64 | 完整演示 UI 冒烟通过，独立临时 profile |

两个 Python 环境均已安装固定 live `c2d5a02ad83b18863514389cedf7afbd993b683d`，107 项包含 10 项子进程上游契约，没有跳过。唯一警告是已有 Starlette/httpx TestClient 弃用警告。

实际最终命令（在仓库目录）：

```bash
export TMPDIR=/home/lan/.hermes/cache/scratch
.venv/bin/python -m pip check
.venv/bin/ruff check .
.venv/bin/pytest -q
"$TMPDIR/xianyu-venv311/bin/python" -m pip check
"$TMPDIR/xianyu-venv311/bin/ruff" check .
"$TMPDIR/xianyu-venv311/bin/pytest" -q
export PLAYWRIGHT_BROWSERS_PATH="$PWD/.test-browsers"
export PLAYWRIGHT_SKIP_BROWSER_GC=1
export XY_TEST_CHROMIUM=/snap/bin/chromium
export XY_TEST_SCREENSHOT="$TMPDIR/xianyu-next-evidence/ui-agent-mobile.png"
.venv/bin/python scripts/smoke_ui.py
node --check xianyu_workbench/static/app.js
git diff --check
```

UI 实际输出：

```text
UI smoke passed: login, account, search, monitor, chat, approvals, manual reconciliation, evidence XSS safety, agent isolation, image upload, publish, mobile, logout
```

UI 不确定状态由脚本仅在临时演示数据库注入；没有开启 live，没有请求闲鱼。验证原执行结果未变、证据中的 HTML 作为文字展示、移动端不横向溢出、Agent 无证据/核对/审批按钮。系统 Chromium 由 Playwright 创建全新临时 profile，未读取主人 profile。

### RED/GREEN 证据与环境限制

证据目录：`/home/lan/.hermes/cache/scratch/xianyu-next-evidence/`（不提交 Git）。包括 `reconcile-*-red.log`、`reconcile-red.log`、`reconcile-green.log`、`capabilities-red.log`、`migration-close-{red,green}.log`、最终 `final-py312.log` / `final-py311.log` / `ui-final.log` 和 `ui-agent-mobile.png`。单测试 GREEN 曾实际运行；并发/原子回滚等附加回归首次通过，不伪称每个附加测试均有 RED。

官方 Playwright 浏览器包下载缓慢，已停止未完成的安装；直接下载官方包 240 秒超时，退出 28。首次 `ui-red.log` 因缺少浏览器失败，属于环境失败，不算功能 RED。改用系统 Chromium 后 `ui-feature-red.log` 实际因缺少“记录人工核对”按钮失败；实现 UI 后冒烟通过。未删除或清理任何共享浏览器缓存。

**代码完成与真实验收必须分开：** 本轮 P0-ENV 本地兼容修复、P2-04 必要迁移基础、P1-02 人工核对闭环代码与本地自动测试完成。修改后 Windows CI 尚未运行；真实账号、平台送达/已读、Docker、实际 MCP 客户端均未新增验收。无恢复 CLI、自动定时备份或保留策略；无可靠自动平台回执。其余首次联系卖家、全量库存、改价、普通上下架、实时客服、发布完整冻结、订单、外部通知不在本轮实现范围。没有真实发送/发布/删除/交易，没有部署、没有 push。

## 真实账号上线前步骤

由主人先在 Linux / WSL 运行演示，确认界面（Windows 原生支持已暂停）；安装系统 Chrome / Node 与 live 依赖；导入本人登录态；启用真实模式后仅验证一次搜索和一次详情；再验证既有会话；最后审批单条低风险咨询，亲自在闲鱼核实。

发布需真实图片、准确价格与描述，审批后核验商品 ID 和页面。删除不适合作为冒烟测试，避免拿重要商品验证。遇到登录/安全验证/不确定状态立即停止，由主人处理。未支持的改价、重新上架、首次会话或订单功能不能靠假返回代替实现。

## 2026-10-15 续开发状态更新

基线 `4d2aadc` 的 [CI run 38566392741](https://github.com/lanchenglin/xianyu/actions/runs/38566392741) 全部 7 作业成功：Ubuntu/Windows 3.11/3.12、双版本固定 live 契约及 UI。上文“新 CI 待验证”为此前历史状态，现已解决；不代表真实账号验收。本轮新增提交尚未 push，CI 待 Hermes 审查后验证。

固定上游五项核实见 [静态可行性报告](UPSTREAM_FEASIBILITY.md)。真实发布因不能冻结类目/地点暂时禁用（live_publish=false）；本地草稿、演示发布和审批申请保留。禁止用默认值变化后的上游发布代替完整审批。

A 安全保护 TDD：a-red.log 实际失败（此前进入真实处理），a-green.log 全量 108 passed / 1 既有弃用警告；证据目录 `/home/lan/.hermes/cache/scratch/xianyu-next2-evidence`。

### P2-04 本地离线恢复增量（2026-10-15）

已提供管理员离线 `backup` / `restore --offline` CLI：一致性数据库+素材、密钥/manifest/hash 校验、受限解包、活动实例拒绝、异常回滚和中断启动保护。恢复暂停账号/监控，pending/approved 失效、running 转不确定，旧任务不重放。无 HTTP/MCP 恢复能力，Agent 不可操作任意文件。详见 [备份说明](BACKUP.md)。此前“无恢复 CLI”为历史状态；定时/保留策略仍未实现。

B 阶段：15 项备份恢复测试通过；全量 123 passed / 1 既有弃用警告。实际临时数据备份→破坏副本→恢复、错误 key 拒绝、重新打开数据库并运行队列不重放、活动锁/路径穿越/符号链接/大小限制/哈希/未来 schema/回滚注入均覆盖。b1～b6-red.log 记录逐行为失败，b-green.log 为全量回归。

### P2-02 单条草稿管理（2026-10-15）

已实现单条原位编辑、revision 乐观并发保护和归档 UI；显式 v2→v3 迁移增加 revision=1 / archived=0，保留原内容。PUT `/api/drafts/{id}` 接受原 account_id、revision 和完整草稿字段；POST `/api/drafts/{id}/archive` 接受 account_id、revision。账号/旧版本/已归档冲突返回 409，不另建副本；归档非平台删除，修改不会改变已冻结审批。管理员和 Agent 均可操作安全本地草稿，无新增管理员权限或任意文件操作。未增加 MCP 编辑工具（HTTP/UI 可用），既有 MCP 保存工具保持新建语义。没有素材删除接口，所有引用图片保留。批量发布、素材回收、取消归档尚未实现。

C 阶段：全量 127 passed / 1 既有弃用警告；c1/c2-red.log 为编辑和归档缺失 RED，c-ui-red.log 实际浏览器因缺少归档按钮失败，c-ui-green.log 真实系统 Chromium 临时 profile 冒烟通过。覆盖跨账号/素材、旧 revision 并发、加密、审批原文冻结、归档非平台删除与图片保留；v2 旧草稿迁移保留测试通过。

### 安全自审增量

发现并以 RED/GREEN 修复：备份创建允许超过恢复上限的大包；中断后的恢复重试若安装失败会丢失此前启动阻断标记。现创建/恢复限制一致，失败重试保留原标记。review-limit-red.log / review-marker-red.log 实际失败，18 项备份恢复回归通过（含 v2 备份→v3 迁移与服务重新启动不重放）。review-ui.log 通过：额外验证另一窗口更新后的旧 revision 保存被拒绝且用户编辑文本保留。

## 2026-10-15 最终验证

| 检查 | 实际结果 |
|---|---|
| Python 3.12.14 pip check / ruff | 均通过 |
| Python 3.12.14 pytest -q | 131 passed, 1 warning in 17.13s |
| Python 3.11.16 pip check / ruff | 均通过 |
| Python 3.11.16 pytest -q | 131 passed, 1 warning in 17.75s |
| 双版本固定上游契约 | 各 10 项通过，亦包含于全量 |
| node --check / git diff --check | 通过 |
| Playwright 系统 Chromium，独立缓存+临时 profile | 通过；新增草稿编辑/旧 revision 拒绝/归档/冻结审批验证 |

证据目录 `/home/lan/.hermes/cache/scratch/xianyu-next2-evidence`，final-py312.log、final-py311.log、final-contract312.log、final-contract311.log、final-ui.log。使用 `PLAYWRIGHT_BROWSERS_PATH=$PWD/.test-browsers PLAYWRIGHT_SKIP_BROWSER_GC=1 XY_TEST_CHROMIUM=/snap/bin/chromium`，未下载新浏览器或读取已有 profile。警告为既有 Starlette TestClient/httpx 弃用提示。

实际完成 4 个本地功能/修复提交后继续安全审查与最终验证，没有停止在 A。没有真实登录/平台请求，没有启用 live，没有部署/推送/合并。真实账号未验收。基线已有 CI 成功不外推到新增提交；新增 CI 等 Hermes 审查推送。

最终另以 review-start-red.log 复现并修复“Service 已构造但 lifespan 尚未启动时恢复中断”的竞态；Service.start 在锁内再次检查恢复标记。备份恢复专项现 19 项，最终双版本全量已重新运行至 131 passed（上表），UI 亦重新通过。

## 独立审查 FAIL 后的修复验证（2026-10-15）

审查对象 `4d2aadc..ad524eb` 的 FAIL 结论保留；此前自审仅补最终限额检查，仍未解决读取前资源拒绝和外键校验。本轮在 `5c463cd` 上修复，不新增功能，不 push，等待 Hermes 复核。

- 资源 RED：`review2-resource-red.log` 实际 6 failed，触发禁止整文件读取断言。新增 DB/素材/合计/manifest/MAX_FILES 小常量测试；最终测试还禁止超限时复制 SQLite 快照。
- GREEN：创建/恢复共用限制；stat 和 WAL 逻辑页大小预检，manifest 精确大小计入总量，全部早于复制和读取内容；数据库与素材使用有界流式哈希，写包再次核验大小/哈希。成功生成包实际通过 validate_archive。
- 外键 RED：`review2-fk-red.log` 实际 1 failed（DID NOT RAISE）。测试以 foreign_keys=OFF 插入孤立草稿，integrity_check 仍为 ok。补 foreign_key_check 后拒绝且无输出，源库字节与孤立记录保持不变。
- 原中断 marker 失败重试保留测试未删除；备份专项合计 26 项通过，日志 `review2-green.log`。

| 最终检查 | 结果 |
|---|---|
| Python 3.12.14 pip check / ruff / 全量 pytest | 全通过；138 passed, 1 warning in 17.46s |
| Python 3.11.16 pip check / ruff / 全量 pytest | 全通过；138 passed, 1 warning in 17.92s |
| 固定上游契约 | 两版本全量均含 10 项，无跳过 |
| node --check / git diff --check | 通过 |
| 系统 Chromium 全新临时 profile UI 冒烟 | 通过，独立缓存设置不变 |

最终证据：原证据目录下 `review2-final312.log`、`review2-final311.log`、`review2-final-ui.log`。警告仍为既有 Starlette/httpx 弃用提示。全程临时虚构数据，未读取真实配置/账号、未启用 live；真实账号未验收，新提交 CI 未运行。

## Windows CI 重定向输出编码修复（2026-10-15）

基线 `6893442` 已推送 PR #1；[run 38679746659](https://github.com/lanchenglin/xianyu/actions/runs/38679746659) **失败**：Windows 3.11/3.12 的 `test_admin_cli_backup_restore_without_env_file` 在备份子进程返回 1；Ubuntu 基础、双版本契约与 UI 共 5 作业成功（用户提供的 CI 状态）。实际读取的 Windows 3.12 日志为 `/home/lan/.hermes/cache/scratch/xianyu-ci-failure/8_Run pytest -q.txt`，结果 1 failed, 127 passed, 1 skipped, 1 warning。

根因与实验：在 Linux 临时假数据上，只改变子进程 `PYTHONIOENCODING`，UTF-8 返回 0，cp1252 返回 1，但两者生成的包均通过 validate_archive。备份成功后的中文 print 无法编码，被既有 except Exception 当成备份失败；stderr 的转义错误与 CI 日志一致。恢复同样会在数据已安装后因成功提示编码失败而误报。本次未发现需要修改 SQLite URI/路径逻辑的证据。

最小修复：仅 backup/restore CLI 将 stdout/stderr 的 errors 设置为 backslashreplace，保留调用方编码；UTF-8 正常中文，cp1252/ASCII 不支持的字符转义输出。未移除备份异常捕获，错误 key 仍返回 1、仅输出脱敏固定提示，不输出密钥或原始异常。未改 Windows CI 矩阵或用测试环境强制 UTF-8 绕过问题。

TDD：`ci-encoding-red.log` 实际 4 failed / 5 passed：cp1252/ASCII 下 backup 和 restore 预期失败，UTF-8 与失败保密路径通过。新增回归均使用真实子进程，含中文临时数据目录、成功归档完整校验、破坏后恢复与暂停检查，以及错误 key 不修改数据/不泄密。修复后编码+全部备份安全测试 35 passed，见 `ci-encoding-green.log`；原 marker/限额/外键测试均保留。

| 最终本地验证 | 结果 |
|---|---|
| Python 3.12.14 pip check / ruff / pytest | 全通过；147 passed, 1 warning in 19.43s |
| Python 3.11.16 pip check / ruff / pytest | 全通过；147 passed, 1 warning in 20.43s |
| 固定 live 契约 | 两版本全量均含 10 项，无跳过 |
| node --check / git diff --check | 通过 |
| 系统 Chromium 隔离临时 profile UI | 通过 |

证据仍在 `/home/lan/.hermes/cache/scratch/xianyu-next2-evidence`：`ci-encoding-final312.log`、`ci-encoding-final311.log`、`ci-encoding-final-ui.log`。既有 Starlette/httpx 弃用警告各 1 条。浏览器使用项目独立缓存、SKIP_BROWSER_GC=1 与 `/snap/bin/chromium`，未读取已有 profile。

**本地编码复现及修复验证通过，不代表 Windows 新 CI 已绿。** 本轮不 push，待 Hermes 复核推送后核验 Windows 两作业。未访问真实账号、未读取真实 .env、未启用 live、未部署；真实账号仍未验收。
