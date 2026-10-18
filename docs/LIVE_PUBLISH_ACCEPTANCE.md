# 真实发布与每日部署验收

2026-10-19，运行代码 c28717f，Linux/WSL Python 3.12。父助手实际操作，非隔离 fixture。

## 已验证

- 数据库 v10→v13 升级；停机后完整私有备份，备份与线上 SQLite integrity_check 均为 ok。
- 工作台实际 inventory/sync：live、非demo，self_published范围3页、41条、end_reached/complete；不是全状态库存。
- 专用本人浏览器单次发布已取得精确ret `["SUCCESS::调用成功"]`，data.itemId 为字符串；详情回读itemId/sellerId为整数，itemStatus=0对应在线。
- 真实上传success=true/status=0，object包含url/pix等字段。已证完整请求采用纬度,经度字符串和web_combined文字模式。
- 工作台管理员单条action实际经历素材上传、发布、详情回读，最终submitted、stage=verified，ownership_verified/status_verified/content_verified全true；价格2200、包邮、1图、短标题及完整描述按原文匹配。图片有EXIF清理与JPEG重编码，不声明像素等价。
- 单条静态请求uniqueCode使用已证时间戳+随机整数生成；每日策略的独立动态生成模式隔离测试通过，首次计划分钟真实执行尚待发生。
- 管理员每日策略已配置enabled=true/effective=true，Asia/Shanghai 09:00、固定验收快照、每日最多1条、错过不补发。非计划分钟tick实测outside_minute，无外部业务写。
- systemd用户服务xianyu-workbench.service与xianyu-daily-publish.timer均enabled/active；timer每分钟05秒触发，业务API负责只在09:00分钟执行。启动就绪等待修复首次连接竞争；之后oneshot实际退出0。未配置WSL宿主关机自动唤醒，机器及专用登录浏览器需运行。
- 服务保持XY_WORKER_ENABLED=false、XY_MESSAGE_SEND_ENABLED=false，仅指定发布执行器启用；不消费历史审批队列。

## 本轮回归

父助手独立全量627 passed、1条既有Starlette/httpx弃用提醒、无skip；Ruff及diff检查通过。源码已推送feat/local-next。

## 未完成边界

每日策略首次09:00实际执行/新ID回读尚未发生，不冒称定时发布已跑过。消息发送ACK、同ID重新上架、全状态库存、完整订单和工作台改价/编辑仍未验收。浏览器同ID正文编辑已成功，但不等于工作台编辑API存在。支付退款确认收货仍人工。

私有配置、完整素材、操作记录、实际账号/商品/action标识只留本机私有数据；不提交凭据或精确地点。生产回滚须停服务并配套恢复升级前数据与密钥，不能用旧程序直接打开v13。
