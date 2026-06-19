## Why

当前项目已经完成聊天图片的采集与落盘，但缺少统一的数据处理阶段，导致收集后的图片无法直接进入训练或检索可用的标签数据。现在需要把开源打标组件接入现有链路，形成“先收集、后打标”的可执行流水线。

## What Changes

- 在图片采集成功后，将图片路径写入待打标队列，打标与采集解耦。
- 新增打标流水线模块，支持批处理、失败重试、审计日志、可选自动执行。
- 新增手动触发 CLI，用于离线/定时批量消费打标队列。
- 接入外部组件 `Eagle_AItagger_byWD1.4`，通过子进程执行其 `main.py` 并回收 `metadata.json` 标签结果。
- 新增打标相关环境变量配置，默认关闭以保持向后兼容。
- 更新 README 与测试，覆盖配置解析与队列处理逻辑。

## Capabilities

### New Capabilities
- `chat-image-tagger-pipeline`: 提供聊天图片“收集后打标”的异步处理能力，包括入队、执行、重试和审计。

### Modified Capabilities
- 无。

## Impact

- Affected code:
  - `plugins/chat_image/config.py`
  - `plugins/chat_image/service.py`
  - `plugins/chat_image/tagger_pipeline.py`（新增）
  - `plugins/chat_image/tagger_cli.py`（新增）
  - `tests/test_chat_image_config.py`
  - `tests/test_chat_image_tagger_pipeline.py`（新增）
  - `README.md`
- External dependency:
  - 需要在运行环境提供 `Eagle_AItagger_byWD1.4` 仓库目录与模型配置（通过环境变量指定）。
- Data artifacts:
  - 队列文件：`data/chat_image_tagger_queue.json`
  - 运行临时目录：`data/chat_image_tagger_runs/`
  - 打标审计：`data/group_image_tags.jsonl`
