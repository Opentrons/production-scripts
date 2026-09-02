# Bridge GPT Token 模块

该模块位于 `src/modules/bridge_tokens`，提供当前登录用户的实时额度、分配记录、自动续额、周分配、周中再平衡和邮件提醒。额度快照、分配记录、任务运行记录和主余额告警状态保存在业务数据库中；生产环境使用 MongoDB，Simulating 模式使用 SQLite。

## 配置

运行文件统一放在当前项目的 `apps/backend/auth-files`，文件权限为 `600`：

```env
PRODUCTION_PLATFORM_BRIDGE_ENV_FILE=apps/backend/auth-files/bridgefloods.env
PRODUCTION_PLATFORM_BRIDGE_WHITELIST_PATH=apps/backend/auth-files/bridgefloods_whitelist.csv
PRODUCTION_PLATFORM_BRIDGE_GMAIL_TOKEN_PATH=apps/backend/auth-files/bridge-gmail-token.json
PRODUCTION_PLATFORM_BRIDGE_AUTOMATION_ENABLED=false
```

启用当前模块的调度器前，必须先停用原 `bridgefloods-quota-monitor`、`bridgefloods-weekly-allocation`、`bridgefloods-weekly-reminders` 和 `bridgefloods-thursday-rebalance` 自动化，避免重复补额、分配和发信。未显式设置 `PRODUCTION_PLATFORM_BRIDGE_AUTOMATION_ENABLED=true` 时，页面余额与记录查询可用，但当前服务不会执行定时变更。

`auth-files/bridgefloods.env` 必须包含非空的 `BRIDGEFLOODS_ACCESS_TOKEN` 或 `BRIDGEFLOODS_REFRESH_TOKEN`。也可以直接设置 `PRODUCTION_PLATFORM_BRIDGE_ACCESS_TOKEN` 或 `PRODUCTION_PLATFORM_BRIDGE_REFRESH_TOKEN`。其余可用变量见 `.env.example`。生产部署时将变量写入 `/etc/production-platform.env`，敏感文件权限应设为 `600`。

MongoDB 可用时，应用首次启动会把 env 中的 Bridge 参数迁移到
`ProductionsMessage.bridge_token_configuration` 的 `active` 文档。迁移后该文档是运行配置源，管理员可在 Bridge GPT Token 页面通过编辑弹窗更新自动开关、阈值、周预算、回看天数、最小分配和邮件参数，保存后立即在当前进程生效。Access Token、Refresh Token 和 SMTP 密码只允许写入或轮换，API 不会回显原值。SQLite fallback 模式不保存自动化配置；配置读写明确要求 MongoDB。

whitelist 继续作为启用状态和邮件地址的唯一来源。优先通过 `key_id` 匹配；只有未填写 `key_id` 时才使用 `key_name`。所有已登录平台用户默认查看全部 `enabled=true` 的 Key 汇总、余额和分配记录，不做平台账号与 whitelist 账号绑定；`enabled=false` 的行不会展示或参与自动化。

## 北京时间任务

- 每 30 分钟：检查余额并按剩余额度从低到高处理，`remaining <= 50` 时增加 100。
- 周一 09:00：按最近 14 天 `actual_cost` 分配 2000，总额度写为 `quota_used + allocation`。
- 周三 10:00：同一邮箱的多个 key 合并为一封提醒。
- 周四 10:00：保持周预算，按本周用量和历史用量重新分配剩余额度。

调度任务通过数据库唯一槽去重。主账户余额无法确认时自动续额会关闭；余额低于 50 时发送主题为 `Kimmy，小桥token余额告急，记得充值。` 的一次性告警，余额恢复后才允许再次告警。

周一分配的目标值始终由累计使用量重新计算，因此失败后会间隔 5 分钟重试，最多 3 次。低余额补额与邮件提醒不自动重放，以免重复增加额度或重复发信。
