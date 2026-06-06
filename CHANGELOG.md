# Changelog

## v1.15

### Bug Fixes
- 修复 gamekee 活动周历接口失效问题，更新为新接口 `www.gamekee.com/v1/wiki/indexV2`，适配新数据结构
- 修复国服/国际服 `load_event` 中 `if/elif` 逻辑错误导致两者互相干扰的问题
- 修复活动缓存 `event_updated` 永远不更新的问题
- 修复 `send_calendar` 发送图片后未 `yield`，导致事件继续传递给 LLM 二次触发的问题
- 修复 `switch_off` 参数名 `sel` 拼写错误
- 修复 `switch_on` 首次执行时文件不存在导致报错的问题
- 修复 `switch_off` 禁用不存在的 umo 时报错，现在会提示"本聊天未启用日历推送"

### Changes
- 移除已停止维护的 schaledb 数据源（私服 `124.223.25.80:40000` 已 502，GitHub 数据停在 2024 年）
- 移除 `en-jp`、`db-jp`、`db-global` 等无效服务器类型
- `send_calendar` 新增服务器参数校验，传入非法参数时给出提示
- `启用日历` 新增服务器参数校验
- 定时发送新增服务器合法性过滤
- 提取公共路径/读写逻辑为独立函数，减少重复代码
