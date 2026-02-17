## Context

现有插件仅做事件 JSONL 记录，未下载附件实体。图片保存需要兼顾稳定性、可追踪性和可配置性。

## Goals

- 自动抓取群消息中的图片附件并落盘。
- 目录可配置，支持指定存储路径。
- 不改变图片内容（不压缩、不转码），尽可能保留原始质量。
- 成功/失败都有结构化日志。

## Non-Goals

- 不做图片去重（基于 hash）与二级存储（对象存储/数据库）。
- 不实现历史消息回溯下载。
- 不承诺超越平台 URL 本身质量上限。

## Approach

1. 在 `GroupAtMessageCreateEvent` 与 `C2CMessageCreateEvent` 处理器内遍历 `attachments`。
2. 识别图片附件（`content_type` 以 `image/` 开头，或文件名后缀为常见图片格式）。
3. 使用异步 HTTP 客户端下载附件 URL 二进制数据。
4. 保存路径规则：
   - 群聊：`<CHAT_IMAGE_SAVE_DIR>/group/<group_openid>/`
   - 私聊：`<CHAT_IMAGE_SAVE_DIR>/private/<user_openid>/`
5. 文件名规则：`<event_timestamp>_<message_id>_<index>_<safe_filename>`，避免冲突。
6. 写入 `data/group_images.jsonl` 审计日志（成功与失败都记录）。

## Config

- `CHAT_IMAGE_SAVE_DIR`：图片保存根目录，默认 `data/chat_images`。
- `GROUP_IMAGE_SAVE_DIR`：兼容旧变量名，若未配置 `CHAT_IMAGE_SAVE_DIR` 则使用它。
- `GROUP_IMAGE_TIMEOUT_SEC`：下载超时秒数，默认 `20`。

## Risks

- URL 可用性受平台策略影响（过期、鉴权）。
- 高并发下本地磁盘 I/O 可能成为瓶颈（当前先用简单串行写入）。
