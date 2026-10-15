# 本地管理员离线备份与恢复

此功能是**私有灾备，不是公开导出**。备份含账号标签、图片、审计、商品、加密登录态/草稿/模型配置等隐私；禁止上传 Git、发给 Agent 或放公开目录。不会收集 `.env`、管理员/Agent 令牌、vault key、浏览器 profile 或 runtime。数据库中已有机密仍保持原加密，素材不做应用层加密；请使用加密磁盘及受控离线存储。

## 操作

正常停止唯一服务，由本地管理员在进程环境安全提供原 `XY_VAULT_KEY`（不要在命令行参数/聊天中粘贴）。CLI 不自动读取任何 `.env`，不需要 API 管理员令牌，无 HTTP/MCP 备份恢复入口。

```bash
python -m xianyu_workbench.cli backup --data-dir /absolute/private/data --output /absolute/private/backup.zip
python -m xianyu_workbench.cli restore --data-dir /absolute/private/data --archive /absolute/private/backup.zip --offline
```

目标 data 目录必须已经存在（新机器可创建空私有目录）。输出文件必须不存在；不覆盖已有备份。两个命令取得同一 `server.lock`，活动服务会被拒绝；不支持在线热备份。SQLite backup API 包括已提交 WAL；只纳入数据库所登记且哈希匹配的素材，未登记孤立图片、runtime、旧迁移快照不是必需数据，不打包。配置与密钥须管理员另行保护，丢失密钥不能恢复。

## 校验与回滚

恢复先在同盘临时目录检查 manifest 格式、允许的 schema、文件清单、SHA-256、大小、SQLite integrity/foreign keys、所有加密列、素材关系及密钥证明。拒绝重复项、额外文件、目录/符号链接、绝对路径/路径穿越、反斜杠/驱动器路径；限制解压后总量 512 MiB、10000 项、manifest 2 MiB。不用 extractall。源数据路径不接受符号链接。当前支持 schema 1 到当前版本，旧 schema 在临时目录按正常迁移升级，不修改原库。散列防损坏，不替代来源认证；只恢复本人可信来源的备份。

校验成功后，旧 db/WAL/SHM/assets/runtime 移到相邻 `restore-rollback-<id>` 私有目录，保持原 server.lock 不移动；同盘 rename 分别原子替换 db/assets。不是跨文件原子事务：普通异常反向回滚；断电/强杀保留 `restore-in-progress` 标记，服务拒绝启动，管理员应离线检查该标记所指副本并重新恢复可信包，不能直接删标记后启动半恢复数据。旧副本含隐私，不能直接启动其中的历史 approved 任务；需通过恢复命令安全处理。断电持久性仍依赖文件系统，建议额外离线副本。

恢复完成：所有账号 paused=1、所有搜索监控 enabled=0；pending/approved 统一 expired（即便 pending 从未执行，也不保留其旧授权）；running→unconfirmed；原 unconfirmed/submitted/终态及核对记录保留，均不重新入队。管理员恢复账号也不会让旧申请再执行。人工先核对平台，再按当前事实创建新的必要申请，不要复制不确定写任务重试。

未实现：自动定时、保留/自动清理策略、云端备份、密钥轮换与公开脱敏导出。恢复演练全用临时目录虚构数据，不代表真实账号已验收。
