# API 层 VideoChat 兼容设计

## 目标

Podcast-Agent 需要新增一层 HTTP API，用于对接已有 videochat 前端和调用方。API 的外部契约保持与 videochat 一致，但内部复用当前项目已有的 pipeline、insights 和 reports 产物结构。

目标范围：

- 保持 API 路径、请求字段、响应字段与 videochat API 同步。
- 支持创建任务、查询状态、查看进度、获取报告、追问和删除任务。
- 适配当前项目的产物目录结构，不修改现有 `input/source/elements/insights/reports` 数据格式。
- 允许在 API 层优化代码目录和流程，但不改变对外 JSON 结构。

非目标：

- 不引入鉴权、用户系统、CORS 配置或生产级网关能力。
- 不修改 insights、reports、metadata、transcript 等已有 artifact schema。
- 不把现有 CLI 流程重写成另一套业务实现。

## 外部接口

API 前缀沿用 videochat：

```text
/videochat/api/tasks
```

接口列表：

```text
POST   /videochat/api/tasks
POST   /videochat/api/tasks/sync
GET    /videochat/api/tasks/{task_id}/status
GET    /videochat/api/tasks/{task_id}/progress
GET    /videochat/api/tasks/{task_id}/report
POST   /videochat/api/tasks/{task_id}/followup
DELETE /videochat/api/tasks/{task_id}
```

创建任务请求保持不变：

```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "question": "这个视频讲了什么？"
}
```

追问请求保持不变：

```json
{
  "question": "视频里是否提到了模型能力提升放缓？"
}
```

报告响应继续使用 `report_markdown` 字段承载 Markdown 字符串。状态响应继续返回 `task_id`、`status`、`created_at`、`updated_at`、`report_available`、`report_path`、`error_message`，并在查询状态和进度时附加 `timing`。

## 模块结构

新增 API 包：

```text
src/podcast_agent/api/
├── __init__.py
├── server.py      # HTTP handler、路由分发、启动入口
├── store.py       # TaskRecord、TaskStore、任务状态和生命周期
├── progress.py    # progress.jsonl 读写、seq、分页
├── timing.py      # 任务耗时和剩余时间估算
├── adapters.py    # 当前产物结构到 videochat API 响应的适配
├── runner.py      # API 任务编排，调用当前完整 pipeline
└── followup.py    # 追问流程，复用 transcript 和 evidence 能力
```

启动方式：

```bash
.venv/bin/python -m podcast_agent.api.server --host 127.0.0.1 --port 8080 --task-root output/api
```

后续可以在 `pyproject.toml` 中增加 console script，但最小实现先保留模块启动方式即可。

## 任务目录

API 任务根目录默认使用：

```text
output/api/<task-id>/
```

当前项目实际产物结构为：

```text
output/api/<task-id>/
  status.json
  progress.jsonl
  error.log
  input.json
  source.json
  elements/
    metadata.json
    transcript.vtt
    transcript.txt
    transcript_info.json
  insights/
    intent.json
    evidence.json
    outline.json
    viewpoint_*.json
    viewpoints.json
    summary.json
  reports/
    report.md
    report.html
    report.pdf
    xhs/
  follow_up/
    <run-id>/
      question.json
      segments.json
      sufficiency.json
      llm.json
```

这个目录结构不同于旧 videochat 的 `input/` 和 `report/`，因此 API 层必须通过适配器定位文件，不能要求业务产物迁移到旧目录。

## 产物适配

`adapters.py` 负责屏蔽目录差异。

报告定位：

- 首选 `reports/report.md`。
- 可兼容查找旧路径 `report/report.md`。
- 响应中的 `report_path` 返回实际文件路径字符串，不改字段名。

字幕定位：

- 首选 `elements/transcript.vtt`。
- 可兼容查找旧路径 `input/*.srt`、`report/*.srt`。
- 追问内部统一解析为字幕片段，HTTP 响应仍返回 `start`、`end`、`text`。

元数据定位：

- 首选 `elements/metadata.json`。
- 可兼容旧路径 `input/SOURCE_METADATA.json`、`report/SOURCE_METADATA.json`。
- 对外继续放入 `source_metadata` 字段。

来源 URL 定位顺序：

```text
elements/metadata.json.source_url
elements/metadata.json.webpage_url
elements/metadata.json.url
source.json.url
input.json.url
```

## 任务状态

`TaskRecord` 对外字段保持 videochat 风格：

```json
{
  "task_id": "20260619T120000Z-abc12345",
  "status": "completed",
  "created_at": "2026-06-19T12:00:00.000000+00:00",
  "updated_at": "2026-06-19T12:03:00.000000+00:00",
  "report_available": true,
  "report_path": "output/api/.../reports/report.md",
  "error_message": ""
}
```

状态值：

```text
queued
running
completed
failed
```

`TaskStore` 负责：

- 创建 task id 和 task directory。
- 写入 `status.json`。
- 维护进程内任务表。
- 读写 `progress.jsonl`。
- 删除任务目录。
- 在服务重启后，至少支持通过 `status.json` 懒加载已有任务，避免旧任务无法获取报告和进度。

懒加载规则：

- 当 `GET /status`、`GET /progress`、`GET /report`、`POST /followup` 收到未知 `task_id` 时，检查 `task_root/<task_id>/status.json`。
- 如果存在则恢复最小 `TaskRecord` 到内存。
- 如果不存在则返回 `task_not_found`。

## 进度事件

`progress.jsonl` 保持 videochat 事件结构：

```json
{
  "seq": 1,
  "ts": "2026-06-19T12:00:00.000000+00:00",
  "type": "phase_started",
  "phase": "prepare",
  "message": "任务准备中",
  "data": {}
}
```

阶段保持兼容：

```text
prepare
media_acquire
evidence_search
report_write
completed
failed
```

最小阶段映射：

```text
prepare
  -> 创建任务和准备目录

media_acquire
  -> resolve_report_intent
  -> run_pipeline，生成 source、metadata、transcript

evidence_search
  -> extract_evidence，生成 insights/evidence.json

report_write
  -> generate_outline
  -> generate_viewpoints
  -> generate_summary
  -> render_markdown_report

completed / failed
  -> 任务结束
```

`/progress` 支持：

```text
after_seq: int，默认 0
limit: int，默认 100，最大 500
```

响应保持：

```json
{
  "task_id": "...",
  "status": "running",
  "next_after_seq": 6,
  "has_more": false,
  "events": [],
  "timing": {}
}
```

## Timing

`timing.py` 可从 videochat 迁移并小幅整理。它只读取 `TaskRecord` 和 `progress.jsonl`，动态计算：

- `timing.task.elapsed_ms`
- `timing.task.remaining_min_ms`
- `timing.task.remaining_max_ms`
- `timing.task.estimated_total_min_ms`
- `timing.task.estimated_total_max_ms`
- `timing.task.confidence`
- `timing.phase.*`

最小实现先使用默认阶段耗时估算。后续如果 insights 内部支持 `progress_sink`，再补充 chunk/viewpoint 级别进度，不影响外部格式。

## 任务执行

异步任务：

```text
POST /videochat/api/tasks
```

流程：

1. 校验 `url` 和 `question` 非空。
2. 创建 `TaskRecord`，状态为 `queued`。
3. 写 `status.json` 和 `phase_started/prepare`。
4. 启动后台线程执行 `runner.run_api_pipeline()`。
5. 立即返回 `202` 和任务状态。

同步任务：

```text
POST /videochat/api/tasks/sync
```

流程相同，但在请求线程中执行，成功后直接返回 `report_markdown`。失败时返回 `500` 和任务状态。

`runner.py` 复用当前项目函数：

```text
build_default_model_writer
resolve_report_intent
write_report_intent
run_pipeline
extract_evidence
generate_outline
generate_viewpoints
generate_summary
render_markdown_report
```

不通过 CLI 子进程执行，避免解析终端输出和重复进程开销。

## 获取报告

```text
GET /videochat/api/tasks/{task_id}/report
```

逻辑：

1. 从 `TaskStore` 获取或懒加载任务。
2. 通过 `adapters.find_report_path(task_dir)` 定位 `reports/report.md`。
3. 不存在则返回：

```json
{
  "error": "report_not_found",
  "status": "running"
}
```

成功响应：

```json
{
  "task_id": "...",
  "status": "completed",
  "report_markdown": "# ...",
  "report_path": "output/api/.../reports/report.md",
  "source_metadata": {}
}
```

## 追问

```text
POST /videochat/api/tasks/{task_id}/followup
```

最小行为与 videochat 对齐：只返回证据片段和充分性判断，不生成最终回答。

流程：

1. 获取或懒加载任务。
2. 定位 `elements/transcript.vtt`。
3. 读取请求问题。
4. 按当前 `podcast_agent.insights.evidence` 的字幕解析和 chunk 逻辑重新搜索证据。
5. 调用新增的 sufficiency 判断，判断证据是否足以回答问题。
6. 写入 `follow_up/<run-id>/question.json`、`segments.json`、`sufficiency.json`、`llm.json`。
7. 返回：

```json
{
  "segments": [
    {
      "start": "00:03:57,208",
      "end": "00:04:31,232",
      "text": "..."
    }
  ],
  "sufficient": true,
  "reason": "..."
}
```

时间戳兼容：

- 当前 transcript 为 VTT，内部可能是 `00:03:57.208`。
- 对外可以转换为旧接口常见的 `00:03:57,208`。
- 如果已有数据是 SRT 逗号格式，则原样返回。

错误响应保持：

```json
{"error": "task_not_found"}
{"error": "subtitle_not_found", "message": "Task has no subtitle file"}
{"error": "invalid_request", "message": "question is required"}
{"error": "followup_failed", "message": "..."}
```

## 测试计划

新增测试文件建议：

```text
tests/test_api_progress.py
tests/test_api_store.py
tests/test_api_server.py
tests/test_api_followup.py
tests/test_api_adapters.py
```

最小测试覆盖：

- `ProgressLog.append()` 生成单调递增 `seq`。
- `/tasks` 异步创建任务返回 `202`。
- `/tasks/sync` 成功返回 `report_markdown`。
- `/status` 返回 videochat 兼容字段和 `timing`。
- `/progress` 支持 `after_seq`、`limit` 和 `has_more`。
- `/report` 从 `reports/report.md` 读取报告。
- 服务重启后可通过 `status.json` 懒加载旧任务。
- `/followup` 从 `elements/transcript.vtt` 生成 `segments/sufficient/reason`。
- 删除任务会移除任务目录并返回 `deleted`。

## 实现顺序

1. 实现 `progress.py`、`adapters.py`、`store.py`。
2. 实现 `server.py` 的 `GET /status`、`GET /progress`、`GET /report`。
3. 实现 `runner.py` 和异步/同步创建任务。
4. 实现 `followup.py` 和 `/followup`。
5. 补充 README 或 usage-docs 中的启动说明。

这个顺序优先让已有产物能被 API 读取，再接入任务执行，最后实现追问。
