## Why

当前实现主要记录文本类群事件，图片仅保留在原始事件字段中，无法用于后续训练、审计与离线处理。  
核心目标是把群聊中的图片文件按尽可能高画质下载并稳定保存到指定目录。

## What Changes

- 在群消息处理链路中识别图片附件并执行下载。
- 新增图片下载与落盘策略：按群与日期分目录、生成稳定文件名、避免覆盖冲突。
- 新增可配置保存目录，支持将图片写入用户指定路径。
- 新增图片下载日志，记录来源 URL、保存路径、尺寸与失败原因。
- 文档补充配置项和限制说明（“尽可能高画质”受平台返回 URL 约束）。

## Capabilities

### New Capabilities
- `group-image-archiving`: 自动提取群消息中的图片附件并落盘到可配置目录，附带下载审计日志。

### Modified Capabilities
- `group-message-logging`: 在既有群消息记录能力上扩展图片保存行为与图片元数据记录。

## Impact

- `plugins/group_logger.py`: 新增图片识别、下载与落盘逻辑。
- `README.md`: 新增图片存储配置和使用说明。
- `openspec/changes/add-group-image-original-download/specs/group-image-archiving/spec.md`: 新增能力规格。
