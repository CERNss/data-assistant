## Why

当前项目已经接入 QQ 适配器，但没有任何群消息采集能力。  
目标是让机器人进群后可稳定接收并落盘群事件，作为后续分析、审计和数据处理的基础。

## What Changes

- 新增机器人启动入口，注册 QQ 适配器并加载本地插件。
- 新增群事件记录插件，记录群消息与群接收/拒收通知到 JSONL 文件。
- 更新项目配置，启用本地 `plugins` 目录。
- 补充运行与环境变量示例文档。

## Capabilities

### New Capabilities

- `group-message-logging`: 机器人在线后，自动记录群消息事件与群通知事件到本地文件。

## Impact

- `bot.py`: 新增启动入口。
- `plugins/group_logger.py`: 新增群消息/通知记录逻辑。
- `pyproject.toml`: 启用本地插件目录。
- `README.md`: 新增能力说明与配置示例。
