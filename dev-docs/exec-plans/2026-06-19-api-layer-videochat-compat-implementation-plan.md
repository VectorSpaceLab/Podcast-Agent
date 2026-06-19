# API layer VideoChat compatibility implementation plan

## Source design

This plan implements:

- [API 层 VideoChat 兼容设计](../design/2026-06-19-api-layer-videochat-compat-design.md)

The goal is to add a minimal HTTP API layer to Podcast-Agent that keeps the external VideoChat task API contract stable while adapting to Podcast-Agent's current artifact layout.

## Minimum implementation

Required behavior:

1. Add a `podcast_agent.api` package.
2. Expose a standard-library HTTP server runnable with `.venv/bin/python -m podcast_agent.api.server`.
3. Keep these VideoChat-compatible endpoints:
   - `POST /videochat/api/tasks`
   - `POST /videochat/api/tasks/sync`
   - `GET /videochat/api/tasks/{task_id}/status`
   - `GET /videochat/api/tasks/{task_id}/progress`
   - `GET /videochat/api/tasks/{task_id}/report`
   - `POST /videochat/api/tasks/{task_id}/followup`
   - `DELETE /videochat/api/tasks/{task_id}`
4. Keep request and response JSON field names compatible with VideoChat.
5. Store API task runtime files under `output/api/<task-id>/` by default.
6. Adapt report lookup to Podcast-Agent's current `reports/report.md`.
7. Adapt metadata lookup to Podcast-Agent's current `elements/metadata.json`.
8. Adapt subtitle lookup to Podcast-Agent's current `elements/transcript.vtt`.
9. Support status/progress/report/followup lazy loading from existing `status.json` after server restart.
10. Implement asynchronous task execution with a background thread.
11. Implement synchronous task execution that returns `report_markdown` on success.
12. Implement progress event logging in VideoChat `progress.jsonl` format.
13. Implement `timing` in `/status` and `/progress`.
14. Implement followup with `segments`, `sufficient`, and `reason`, without generating a final answer.
15. Keep existing insight/report artifact schemas unchanged.
16. Render only Markdown by default for API tasks.
17. Add an optional report output mode that can render HTML, PDF, XHS, or all report formats when explicitly requested.

## Module organization

```text
src/podcast_agent/api/
├── __init__.py
├── adapters.py
├── followup.py
├── progress.py
├── runner.py
├── server.py
├── store.py
└── timing.py

tests/
├── test_api_adapters.py
├── test_api_followup.py
├── test_api_progress.py
├── test_api_server.py
└── test_api_store.py
```

Do not move existing CLI, insight, report, source, downloader, or transcriber modules.

## Responsibility boundaries

### `api/progress.py`

Owns:

- `ProgressLog`.
- Progress event append and read.
- Monotonic `seq` assignment.
- JSONL persistence.
- Missing progress file behavior.

Should preserve event shape:

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

Does not own:

- HTTP response formatting.
- Task status persistence.
- Pipeline execution.

### `api/adapters.py`

Owns:

- Finding `reports/report.md`.
- Finding `elements/transcript.vtt`.
- Loading source metadata from `elements/metadata.json`.
- Falling back to old VideoChat paths when useful.
- Resolving source URL from metadata/source/input artifacts.
- Formatting followup segment timestamps for compatibility.

Should expose helpers such as:

```text
find_report_path(task_dir)
find_subtitle_path(task_dir)
load_source_metadata(task_dir)
resolve_source_url(task_dir)
read_report_markdown(task_dir)
```

Does not own:

- Generating reports.
- Running followup LLM calls.
- Writing status.

### `api/store.py`

Owns:

- `TaskRecord`.
- `TaskStore`.
- Task id generation.
- `status.json` persistence.
- In-memory task registry.
- Lazy loading existing tasks from `status.json`.
- Appending and reading progress via `ProgressLog`.
- Deleting task directories.
- Reporting task timing snapshots.

Should keep VideoChat-compatible status payloads:

```text
task_id
status
created_at
updated_at
report_available
report_path
error_message
source_metadata
```

Does not own:

- HTTP routing.
- Pipeline stage implementation.
- Followup evidence search.

### `api/timing.py`

Owns:

- Deriving timing from `TaskRecord` and progress events.
- Default phase remaining-time estimates.
- Progress-based estimates when event `data` contains chunk or viewpoint counts.

Can be ported from the VideoChat implementation with naming adjusted to this package.

Does not own:

- Writing progress events.
- Persisting timing results.

### `api/runner.py`

Owns:

- Running the Podcast-Agent API pipeline for tasks.
- Emitting coarse VideoChat-compatible progress events around current project stages.
- Calling current project functions directly, not through CLI subprocesses.
- Rendering report outputs according to an explicit report output mode.

Should call:

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

Default report output mode:

```text
markdown
```

Supported report output modes:

```text
markdown  -> produce reports/report.md
html      -> produce Markdown and HTML
pdf       -> produce Markdown, HTML, and PDF
xhs       -> produce Markdown plus XHS note/assets
all       -> produce Markdown, HTML, PDF, and XHS outputs
```

The default mode must stay `markdown` because the VideoChat-compatible API only requires `report_markdown`. Heavier formats should be opt-in.

Should emit at least:

```text
phase_started prepare
phase_started media_acquire
phase_completed media_acquire
phase_started evidence_search
phase_completed evidence_search
phase_started report_write
phase_completed report_write
task_completed completed
task_failed failed
```

Does not own:

- HTTP request validation.
- Task id creation.
- JSON response formatting.

### `api/followup.py`

Owns:

- Running a followup question against an existing task directory.
- Parsing existing transcript content.
- Reusing current evidence chunk/search logic where practical.
- Judging evidence sufficiency.
- Writing `follow_up/<run-id>/question.json`, `segments.json`, `sufficiency.json`, and `llm.json`.

Required output shape:

```json
{
  "segments": [],
  "sufficient": false,
  "reason": "..."
}
```

Does not own:

- Creating final answer markdown.
- Changing `insights/evidence.json`.
- Changing transcript artifacts.

### `api/server.py`

Owns:

- `BaseHTTPRequestHandler` implementation.
- Route parsing.
- JSON request parsing.
- JSON response writing.
- HTTP status codes.
- `create_server()`.
- `parse_args()`.
- `main()`.

Should keep the `API_PREFIX = "/videochat/api/tasks"` constant.

Does not own:

- Artifact lookup details.
- Pipeline internals.
- Timing math.

## Implementation sequence

### Phase 1: Progress and artifact adapters

1. Add `src/podcast_agent/api/__init__.py`.
2. Add `api/progress.py`:
   - implement `PROGRESS_PHASE_MESSAGES`
   - implement `utc_now()`
   - implement `ProgressLog.append()`
   - implement `ProgressLog.read()`
   - implement monotonic `_next_seq_unlocked()`
3. Add `tests/test_api_progress.py`:
   - append assigns `seq = 1`
   - second append assigns `seq = 2`
   - read filters by `after_seq`
   - read honors `limit`
   - missing file returns `[]`
4. Add `api/adapters.py`:
   - find current report path
   - find current subtitle path
   - load current metadata
   - resolve current source URL
   - include old VideoChat fallback paths
5. Add `tests/test_api_adapters.py`:
   - report lookup finds `reports/report.md`
   - metadata lookup reads `elements/metadata.json`
   - subtitle lookup finds `elements/transcript.vtt`
   - source URL resolution uses metadata `source_url`
   - fallback paths still work for old-style task directories

Run:

```bash
.venv/bin/python -m pytest tests/test_api_progress.py tests/test_api_adapters.py
```

### Phase 2: Store and timing

1. Add `api/timing.py`:
   - port VideoChat timing implementation
   - keep phase order `prepare`, `media_acquire`, `evidence_search`, `report_write`
   - keep completed/failed handling
2. Add `api/store.py`:
   - implement `TaskRecord`
   - implement `TaskStore.create_task()`
   - implement `TaskStore.run_task_sync()`
   - implement `TaskStore.get_task()`
   - implement lazy `TaskStore.load_task()`
   - implement `TaskStore.get_or_load_task()`
   - implement `TaskStore.delete_task()`
   - implement `TaskStore.read_report()`
   - implement progress append/read methods
   - implement status writing
3. Add `tests/test_api_store.py`:
   - create task writes `status.json`
   - sync success marks task completed when `reports/report.md` exists
   - missing report marks task failed
   - runner exception writes `error.log` and failed status
   - lazy load restores task from `status.json`
   - read report uses `reports/report.md`
   - delete removes task directory
4. Add timing-focused tests in `tests/test_api_store.py` or separate `tests/test_api_timing.py`:
   - completed task returns high-confidence zero remaining
   - running evidence phase estimates remaining from `completed_chunks/chunk_count`
   - report stage estimates from `completed_viewpoints/total_viewpoints`

Run:

```bash
.venv/bin/python -m pytest tests/test_api_store.py
```

### Phase 3: HTTP status/progress/report/delete endpoints

1. Add `api/server.py` skeleton:
   - constants `DEFAULT_HOST`, `DEFAULT_PORT`, `DEFAULT_TASK_ROOT`, `API_PREFIX`
   - `VideoChatRequestHandler`
   - `_parse_task_path()`
   - `_read_json()`
   - `_send_json()`
   - `create_server()`
   - `parse_args()`
   - `main()`
2. Implement `GET /status`:
   - use `store.get_or_load_task()`
   - attach `timing`
3. Implement `GET /progress`:
   - parse `after_seq` and `limit`
   - return `next_after_seq`, `has_more`, `events`, `timing`
4. Implement `GET /report`:
   - return `report_markdown`, `report_path`, `source_metadata`
5. Implement `DELETE /tasks/{task_id}`.
6. Add `tests/test_api_server.py`:
   - unknown route returns `not_found`
   - status returns compatible fields
   - progress validates query params
   - progress returns pagination fields
   - report returns markdown from `reports/report.md`
   - report missing returns `report_not_found`
   - delete returns `deleted`
   - lazy-loaded task works through HTTP

Run:

```bash
.venv/bin/python -m pytest tests/test_api_server.py
```

### Phase 4: API pipeline runner and task creation

1. Add `api/runner.py`.
2. Add a report output mode model:
   - support `markdown`, `html`, `pdf`, `xhs`, and `all`
   - default to `markdown`
   - expose the mode as a runner argument, for example `report_mode="markdown"`
   - keep the HTTP API default mode as `markdown`
   - optionally allow server-level configuration through a command-line flag such as `--report-mode`
3. Implement `run_api_pipeline(url, question, task_dir, progress_sink=None, report_mode="markdown")`:
   - build one model writer
   - resolve and persist report intent to `insights/intent.json`
   - call `run_pipeline(..., audio_transcriber=LazyDefaultAliyunTranscriber())`
   - call `extract_evidence(...)`
   - call `generate_outline(...)`
   - call `generate_viewpoints(...)`
   - call `generate_summary(...)`
   - call `render_markdown_report(...)`
   - if `report_mode` is `html`, ensure HTML output exists
   - if `report_mode` is `pdf`, call `render_pdf_report(...)`
   - if `report_mode` is `xhs`, call `compose_xhs_report(...)`, `prepare_xhs_cover(...)`, and `render_xhs_images(...)`
   - if `report_mode` is `all`, render every supported report output
4. Keep Markdown as the required completion artifact:
   - task completion requires `reports/report.md`
   - optional report format failures should fail the task in that mode, because the caller explicitly requested those outputs
   - default `markdown` mode should not spend time rendering PDF or XHS outputs
5. Emit progress lifecycle around each coarse stage.
6. Wire `TaskStore` default runner to `run_api_pipeline`.
7. Implement `POST /videochat/api/tasks`:
   - validate `url` and `question`
   - create async task
   - return `202`
8. Implement `POST /videochat/api/tasks/sync`:
   - validate `url` and `question`
   - run sync task
   - success returns `200` and `report_markdown`
   - failure returns `500` and task status payload
9. Add tests:
   - async create returns `202` and queued payload
   - sync success returns `report_markdown`
   - sync missing report returns `500`
   - invalid create request returns `400`
   - progress contains expected lifecycle events
   - default runner mode only requires Markdown
   - `pdf` mode invokes PDF rendering after Markdown/HTML
   - `xhs` mode invokes XHS compose, cover, and image rendering
   - `all` mode invokes every optional renderer

Testing should fake the runner where possible to avoid real network or LLM calls.

Run:

```bash
.venv/bin/python -m pytest tests/test_api_server.py tests/test_api_store.py
```

### Phase 5: Followup

1. Add `api/followup.py`.
2. Implement `FollowupResult`.
3. Implement transcript loading:
   - use `adapters.find_subtitle_path(task_dir)`
   - support VTT first
   - support old SRT fallback if present
4. Implement followup evidence search:
   - reuse `parse_subtitle_segments`, chunking, normalization, and hydration helpers from `podcast_agent.insights.evidence`
   - use `EvidenceConfig(max_final_segments=0)` semantics for no final segment limit
   - avoid writing to `insights/evidence.json`
5. Implement sufficiency judgment:
   - prompt asks only whether evidence is sufficient
   - parse JSON result
   - return false with a useful reason on empty segments
6. Add LLM call recording for `follow_up/<run-id>/llm.json`.
   - If the existing model writer tracing utilities are not present, implement a small wrapper local to API followup.
7. Implement `POST /tasks/{task_id}/followup` in `server.py`.
8. Add `tests/test_api_followup.py`:
   - missing task returns `task_not_found`
   - missing subtitle returns `subtitle_not_found`
   - empty question returns `400`
   - empty evidence returns `sufficient=false`
   - successful followup returns only `segments`, `sufficient`, `reason`
   - writes `question.json`, `segments.json`, `sufficiency.json`, `llm.json`
   - does not write `answer.md`

Testing should use fake model writers and tiny transcript fixtures.

Run:

```bash
.venv/bin/python -m pytest tests/test_api_followup.py tests/test_api_server.py
```

### Phase 6: Documentation and final verification

1. Add usage docs:
   - either update `usage-docs/cli.md`
   - or add `usage-docs/api.md`
2. Include:
   - server start command
   - default task root
   - default report output mode
   - optional report output mode values
   - endpoint list
   - minimal curl examples
3. Run all API tests:

```bash
.venv/bin/python -m pytest \
  tests/test_api_progress.py \
  tests/test_api_adapters.py \
  tests/test_api_store.py \
  tests/test_api_server.py \
  tests/test_api_followup.py
```

4. Run broader tests if API changes touched shared modules:

```bash
.venv/bin/python -m pytest
```

## Acceptance criteria

- `.venv/bin/python -m podcast_agent.api.server --host 127.0.0.1 --port 8080 --task-root output/api` starts a server.
- `POST /videochat/api/tasks` returns `202` with VideoChat-compatible status fields.
- `POST /videochat/api/tasks/sync` returns `200` with `report_markdown` when the fake or real runner creates `reports/report.md`.
- API task execution defaults to `report_mode="markdown"`.
- Default `markdown` mode does not render PDF or XHS outputs.
- Optional report output mode can request `html`, `pdf`, `xhs`, or `all`.
- `GET /status` returns task status and `timing`.
- `GET /progress` returns `next_after_seq`, `has_more`, `events`, and `timing`.
- `GET /report` reads `reports/report.md` and returns `report_markdown`.
- `POST /followup` reads `elements/transcript.vtt` and returns `segments`, `sufficient`, and `reason`.
- `DELETE /tasks/{task_id}` deletes the task directory.
- Existing Podcast-Agent artifact schemas remain unchanged.
- Old VideoChat response field names remain unchanged.
- Existing CLI tests continue to pass unless a deliberate shared bug fix is required.
- API tests use fakes for network and LLM-dependent behavior.

## Non-goals

- Do not add authentication or user-scoped task ownership.
- Do not add CORS configuration unless a frontend integration explicitly requires it.
- Do not introduce FastAPI, Flask, or another web framework for the minimum implementation.
- Do not change current `input.json`, `source.json`, `elements/*.json`, `insights/*.json`, or `reports/report.md` formats.
- Do not generate a final answer in followup.
- Do not rewrite existing CLI commands.
- Do not run real YouTube, Bilibili, Aliyun, or LLM integration calls in tests.
