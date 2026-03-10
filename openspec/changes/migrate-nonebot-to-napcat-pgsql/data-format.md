## NapCat OneBot11 Data Contract (for `data-logger`)

This document consolidates the real payload samples and official NapCat OneBot11 basic event docs.

Reference: `https://napneko.github.io/onebot/basic_event`

Related docs:

- `https://napneko.github.io/onebot/sement`
- `https://napneko.github.io/develop/file`
- `https://napneko.github.io/onebot/event`

## 1. Event Envelope (all events)

Required top-level fields:

- `time` (number): Unix timestamp in seconds
- `self_id` (number): bot QQ id
- `post_type` (string): one of `message`, `message_sent`, `notice`, `request`, `meta_event`

## 2. Message Event Canonical Fields

For `post_type` in `message` / `message_sent`:

- `message_type`: `private` or `group`
- `sub_type`: private(`friend`/`group`/`other`), group(`normal`/`anonymous`/`notice`)
- `message_id` (number)
- `user_id` (number)
- `message` (array or string)
- `raw_message` (string)
- `sender` (object)
- Group-only: `group_id` (number), optional `group_name` (string in NapCat payload)

Observed additional fields in real samples (persist from `raw`):

- `message_seq`, `real_id`, `real_seq`, `message_format`, `target_id`, `font`

## 3. Segment Parsing Rules

Primary parsing source:

1. If `message` is array, parse by segment `type`:
   - `text` => `data.text`
   - `face` => `data.id`, plus keep `data.raw`
   - `image` => `data.url`, `data.file`, `data.sub_type`, `data.file_size`, `data.summary`
2. If array missing/unusable, fallback to `raw_message` CQ parsing.

Image URL rule:

- Prefer `message[].data.url` (already decoded URL in samples)
- Fallback to CQ `raw_message` extraction
- Preserve both raw and decoded URL values for audit

## 4. Meta Event Contract

- Lifecycle example: `meta_event_type=lifecycle`, `sub_type=connect`
- Heartbeat example: `meta_event_type=heartbeat`, `status.online`, `status.good`, `interval`

Time semantics:

- `time` is seconds
- `heartbeat.interval` is milliseconds

## 5. Persistence Mapping (PostgreSQL)

### `onebot_events`

Store every inbound payload:

- Parsed columns: `post_type`, `message_type`, `self_id`, `user_id`, `group_id`, `group_name`, `message_id`, `raw_message`, `event_time`
- Raw payload: `raw jsonb`

### `onebot_message_images`

One row per extracted image segment:

- `event_id`, `seq`, `url_raw`, `url_decoded`, `file_name`, `sub_type`, `file_size`, `summary`
- Download status fields: `local_path`, `download_status`, `download_error`, `downloaded_at`
- Binary metadata fields: `hash_sha256`, `format`, `width`, `height`, `is_animated`, `frame_count`
- HTTP evidence fields: `http_content_type`, `http_content_length`, `download_attempt`
- Optional stream fields: `transfer_mode` (`normal`/`stream`), `stream_phase`, `stream_data_type`

### `onebot_nats_dispatches`

Track downstream continuity:

- `image_id`, `subject`, `payload jsonb`, `status`, `error`, `created_at`

## 6. URL Expiration And Refresh Contract

- NapCat image URL may expire (doc note: about 2 hours).
- On URL-expired error, collector should attempt refresh/retrieval via protocol-compatible APIs:
  - `nc_get_rkey`
  - `get_image`
  - `get_file`
  - `get_msg`
- Persist refresh attempts and final outcome for observability.

## 7. Chunk/Stream Transfer Contract

- For large-file/cross-device scenarios, NapCat Stream API may emit chunk-state payloads.
- Stream transfer states of interest:
  - `data.type=stream` + `data.data_type=data_chunk` (in progress)
  - `data.type=response` + `data.data_type=data_complete` (completed)
  - `data.type=error` (failed)
- Collector must preserve enough fields to reconstruct transfer progress and terminal state.

## 8. Sample-Validated Message Cases

Validated from provided raw payloads:

- Private text (`message_type=private`, `message[0].type=text`)
- Private face (`message[0].type=face`)
- Private image (`message[0].type=image`)
- Group text (`message_type=group`, `sub_type=normal`)
- Group face (`message[0].type=face`)
- Group image (`message[0].type=image`, with `group_id`/`group_name`)

## 9. Segment Field Compatibility Notes

- `image.data.sub_type` uses snake_case in protocol examples.
- Some custom scripts may emit/expect camelCase aliases (for example `subType`); parser should not lose raw data when field alias appears.
- `message` can be array or CQ string; parser should preserve original representation in raw payload.
