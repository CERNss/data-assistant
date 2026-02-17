## 1. 实现

- [x] 1.1 在 `plugins/group_logger.py` 中识别群消息图片附件
- [x] 1.2 增加图片下载与原样写盘逻辑（无压缩/无转码）
- [x] 1.3 增加可配置保存目录与下载超时配置
- [x] 1.4 增加图片下载审计日志文件 `data/group_images.jsonl`
- [x] 1.5 更新 `README.md` 的图片配置与限制说明

## 2. 验证

- [x] 2.1 通过 `python -m py_compile bot.py plugins/group_logger.py`
- [ ] 2.2 在真实群消息图片场景下验证文件写入指定目录并检查日志
