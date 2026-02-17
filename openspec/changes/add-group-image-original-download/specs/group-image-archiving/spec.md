## ADDED Requirements

### Requirement: Save Chat Images To Chat-Scoped Directory

系统 MUST 在收到包含图片附件的聊天消息后，将图片文件保存到可配置目录，并按会话身份分目录。

#### Scenario: Group message includes image attachment

- **WHEN** 机器人在线并收到 `GroupAtMessageCreateEvent`，且附件 `content_type` 为图片类型
- **THEN** 系统下载该图片并写入配置目录
- **AND** 写入路径为 `.../group/<group_openid>/`

#### Scenario: Private message includes image attachment

- **WHEN** 机器人在线并收到 `C2CMessageCreateEvent`，且附件 `content_type` 为图片类型
- **THEN** 系统下载该图片并写入配置目录
- **AND** 写入路径为 `.../private/<user_openid>/`

### Requirement: Preserve Best Available Quality From Source URL

系统 MUST 以事件提供的图片 URL 作为下载源，按平台可用的最佳质量进行保存，不做主动压缩或转码。

#### Scenario: Download image from attachment url

- **WHEN** 图片附件存在可访问的 `url`
- **THEN** 系统直接下载该 URL 的二进制内容并原样写盘
- **AND** 保存文件大小与下载字节数一致

### Requirement: Record Image Download Audit Log

系统 MUST 记录图片下载结果，包含成功和失败信息，便于审计与排障。

#### Scenario: Image download succeeds

- **WHEN** 图片下载并写盘成功
- **THEN** 系统追加一条日志记录到图片日志文件
- **AND** 记录包含 `chat_type`、`chat_id`、`message_id`、`source_url`、`saved_path`、`size`

#### Scenario: Image download fails

- **WHEN** 图片 URL 无法下载或写盘失败
- **THEN** 系统追加失败日志
- **AND** 记录包含失败原因与原始附件信息

### Requirement: Retry Image Download On Transient Failure

系统 MUST 在图片下载失败时进行有限次数重试，以降低临时网络抖动导致的失败率。

#### Scenario: Retry before marking failed

- **WHEN** 图片 URL 首次下载失败
- **THEN** 系统按配置的重试次数和重试间隔继续尝试下载
- **AND** 仅在所有重试都失败后记录最终失败日志
