# Viewpoint detail 空响应导致任务失败问题总结

## 问题概述

在批处理任务中，单个观点详情生成可能因为模型返回空内容而失败。例如：

```text
output/batch-20260619T064225Z/bilibili-BV1HrrjB9EUj-20260619T064225Z
```

对应日志：

```text
Stage 5/11: generating viewpoint details
Viewpoint generation failed: model returned empty content for V3.
Exit code: 1
```

该任务的 `insights/outline.json` 中存在 V3：

```text
V3 被迫放弃追赶光线的拍摄，反而迎来罕见的深度放松
importance_score=4
evidence_segment_indexes=[5, 6]
```

但实际输出目录只有：

```text
insights/viewpoint_V1.json
insights/viewpoint_V2.json
insights/viewpoint_V4.json
insights/viewpoint_V5.json
insights/viewpoint_V6.json
```

没有：

```text
insights/viewpoint_V3.json
insights/viewpoints.json
insights/summary.json
reports/report.md
```

这说明不是 V3 被 outline 阶段跳过，而是 V3 的详情生成失败导致整个任务中断。

## 准确问题位置

当前链路：

```text
podcast_agent.cli.stages.full(...)
  -> generate_viewpoints(...)
  -> _generate_and_save_viewpoint_detail(...)
  -> generate_viewpoint_detail(...)
  -> model_writer(prompt).strip()
```

精确代码位置：

```text
src/podcast_agent/insights/viewpoint.py
```

原始失败条件：

```python
response = model_writer(prompt).strip()
if not response:
    raise EvidenceExtractionError(
        f"Viewpoint generation failed: model returned empty content for {viewpoint_id}."
    )
```

`generate_viewpoints()` 会并发生成多个 viewpoint。并发执行时，其他 viewpoint 可能已经成功写盘，但只要一个 selected viewpoint 抛错，整个阶段就失败退出，因此不会写最终聚合文件 `viewpoints.json`。

## 直接原因

直接原因是模型在 V3 详情生成调用中返回了空字符串。

这类问题通常属于瞬时 LLM 输出异常：

- 模型返回空内容。
- 模型返回非 JSON。
- 模型返回 JSON 片段但不是 object。
- 模型返回 object 但缺少 `sub_theses`。

这些情况不代表 V3 没有证据或不该生成，而是模型调用结果没有满足 viewpoint detail 的 JSON contract。

## 参考实现

VideoChat workflow-v2 在：

```text
/share/project/chenchen/code/videochat/.worktrees/workflow-v2/src/workflow/report/viewpoint.py
```

已经有更稳的处理方式：

- `VIEWPOINT_DETAIL_MAX_ATTEMPTS = 3`
- `_classify_viewpoint_detail_failure(...)`
- `_build_viewpoint_retry_prompt(...)`
- `_truncate_response_preview(...)`
- `viewpoint_detail_parse_failed`
- `viewpoint_detail_retrying`
- `viewpoint_detail_abandoned`
- `viewpoint_detail_succeeded`

核心思想：

1. 首次响应为空或格式错误时不立刻失败。
2. 分类失败原因，例如 `empty_response`、`invalid_json`、`non_object_json`、`missing_sub_theses`。
3. 后续尝试追加纠正提示，要求模型只返回一个 JSON object。
4. 最多重试 3 次。
5. 重试耗尽后再失败。

## 最小修复方案

在 Podcast-Agent 中做最小优化：

1. 保持现有 artifact schema 不变。
2. 保持现有 prompt 主体不变。
3. 给 `generate_viewpoint_detail()` 增加最多 3 次重试。
4. 首次失败后构造 corrective retry prompt。
5. 对空响应、非法 JSON、非 object JSON、缺失 `sub_theses` 都触发重试。
6. 重试耗尽后仍抛 `EvidenceExtractionError`，保持严格失败策略。

本次最小修复不做：

- 不跳过失败 viewpoint。
- 不改变 `viewpoints.json` 格式。
- 不改变 `selected_viewpoint_ids` / `omitted_viewpoint_ids` 语义。
- 不生成部分成功报告。

## 验证方式

新增测试应覆盖：

- 第一次空响应，第二次成功。
- 第一次非法 JSON，第二次成功。
- 多次失败后抛出清晰错误。

建议运行：

```bash
.venv/bin/python -m pytest tests/test_viewpoint_generation.py
```

全量验证：

```bash
.venv/bin/python -m pytest
```
