## Context

现有系统在 `plugins/chat_image/service.py` 中完成图片下载与落盘，并将结果写入 `data/group_images.jsonl`。该链路稳定但仅覆盖“采集”，未定义“处理”阶段。  
目标是复用 `Eagle_AItagger_byWD1.4` 的打标能力，不侵入现有消息处理主链路，避免打标耗时影响机器人响应。

## Goals / Non-Goals

**Goals:**
- 建立异步“收集后打标”流水线，采集成功后入队，按批消费。
- 打标执行失败可重试，并输出结构化审计日志，便于追踪。
- 保持与现有采集逻辑兼容：默认不启用打标功能。
- 提供手动 CLI，支持离线批量处理。

**Non-Goals:**
- 不修改外部打标项目内部代码与推理算法。
- 不在本变更中新增标签回写到 QQ 消息或回传功能。
- 不解决 GPU/模型部署问题（由外部组件与运行环境负责）。

## Decisions

1. 采用“文件队列 + 子进程调用外部工具”
- 决策：队列持久化为 JSON 文件（默认 `data/chat_image_tagger_queue.json`），执行时通过子进程调用外部 `main.py`。
- 原因：最小化接入成本，不引入额外中间件；进程边界清晰，便于隔离第三方依赖。
- 备选方案：
  - 直接 import 外部仓库模块：耦合高、升级风险大。
  - 引入 Redis/Celery：复杂度超出当前项目规模。

2. 打标执行与采集解耦，默认手动触发
- 决策：仅在采集成功后入队；默认 `CHAT_IMAGE_TAGGER_AUTO_RUN=false`，通过 CLI 消费队列。
- 原因：避免消息处理线程被推理耗时阻塞，先保证采集稳定。
- 备选方案：
  - 每次采集后同步打标：延迟不可控，影响在线处理。

3. 临时 staging 目录重组输入，规避 metadata 冲突
- 决策：每张图片映射到独立 `*.info` 目录，再生成 `image_list.txt` 供外部组件读取。
- 原因：外部工具按图片同级目录写 `metadata.json`，独立目录可避免多图覆盖。
- 备选方案：
  - 直接用原始采集目录：同目录多图时结果文件冲突风险高。

4. 审计与重试策略内建到流水线
- 决策：新增 `data/group_image_tags.jsonl` 记录 `success/retrying/failed`；按 `CHAT_IMAGE_TAGGER_MAX_ATTEMPTS` 重试。
- 原因：增强可观测性，便于排障与后续数据质量评估。
- 备选方案：
  - 仅记录最终失败：排障信息不足。

## Risks / Trade-offs

- [外部组件行为变化] 升级后参数或输出格式可能变化  
  → Mitigation: 通过环境变量配置入口脚本/配置文件，读取结果时做类型校验并记录错误。

- [队列文件并发写入风险] 多协程同时入队或消费可能产生覆盖  
  → Mitigation: 在进程内使用 `asyncio.Lock` 保护读写；写入采用临时文件替换。

- [运行资源占用] GPU 推理耗时和显存开销高  
  → Mitigation: 默认关闭自动执行，优先手动批处理，允许限制 batch size 和超时。

- [临时目录膨胀] 调试或失败场景可能堆积中间文件  
  → Mitigation: 默认处理后清理运行目录，提供 `CHAT_IMAGE_TAGGER_KEEP_RUN_ARTIFACTS` 用于排障。

## Migration Plan

1. 部署新代码，不开启打标开关（默认行为不变）。
2. 在环境中配置：
   - `CHAT_IMAGE_TAGGER_ENABLED=true`
   - `CHAT_IMAGE_TAGGER_TOOL_ROOT=<Eagle_AItagger_byWD1.4 绝对路径>`
3. 先运行采集，确认队列文件持续写入。
4. 通过 `python -m plugins.chat_image.tagger_cli --once` 小批量验证。
5. 验证审计日志后，按需要开启 `CHAT_IMAGE_TAGGER_AUTO_RUN=true`。

回滚策略：
- 关闭 `CHAT_IMAGE_TAGGER_ENABLED` 即可回退到仅采集模式；无需数据迁移。

## Open Questions

- 是否需要将标签结果同步回写到单独结构化数据集目录（除 JSONL 审计外）？
- 是否需要增加“按群/按用户”的优先级消费策略？
