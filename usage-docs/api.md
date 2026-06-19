# VideoChat-compatible API

Podcast-Agent provides a minimal VideoChat-compatible HTTP API for task-based report generation.

## Start server

```bash
.venv/bin/python -m podcast_agent.api.server --host 127.0.0.1 --port 8080 --task-root output/api
```

Or use the helper script:

```bash
scripts/api/start_service.sh --background
```

Default task root:

```text
output/api
```

Default report output mode:

```text
markdown
```

Optional report output modes:

```text
markdown
html
pdf
xhs
all
```

Example:

```bash
.venv/bin/python -m podcast_agent.api.server --report-mode pdf
```

## Endpoints

```text
POST   /videochat/api/tasks
POST   /videochat/api/tasks/sync
GET    /videochat/api/tasks/{task_id}/status
GET    /videochat/api/tasks/{task_id}/progress
GET    /videochat/api/tasks/{task_id}/report
POST   /videochat/api/tasks/{task_id}/followup
DELETE /videochat/api/tasks/{task_id}
```

## Create task

```bash
curl -X POST http://127.0.0.1:8080/videochat/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://www.youtube.com/watch?v=xxxx","question":"这个视频讲了什么？"}'
```

Helper script:

```bash
scripts/api/ask_question.sh \
  --url "https://www.youtube.com/watch?v=xxxx" \
  --question "这个视频讲了什么？" \
  --async
```

## Get report

```bash
curl http://127.0.0.1:8080/videochat/api/tasks/<task-id>/report
```

## Get progress

```bash
curl "http://127.0.0.1:8080/videochat/api/tasks/<task-id>/progress?after_seq=0&limit=100"
```

Helper script:

```bash
scripts/api/watch_progress.sh --task-id "<task-id>"
```

## Followup

```bash
curl -X POST http://127.0.0.1:8080/videochat/api/tasks/<task-id>/followup \
  -H 'Content-Type: application/json' \
  -d '{"question":"视频里是否提到了模型能力提升放缓？"}'
```

Helper script:

```bash
scripts/api/ask_followup.sh \
  --task-id "<task-id>" \
  --question "视频里是否提到了模型能力提升放缓？"
```
