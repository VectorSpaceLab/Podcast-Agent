# Aliyun transcription result timeout implementation plan

## Source summary

This plan implements:

- [阿里云转录结果下载 ReadTimeout 问题总结](../error-summary/2026-06-19-aliyun-transcription-result-timeout.md)

The goal is to keep Podcast-Agent strictly aligned with the VideoChat workflow fix for Aliyun result JSON `ReadTimeout` failures.

## Minimum implementation

Required behavior:

1. Use `requests.Session` for Aliyun ASR client HTTP work.
2. Configure a default HTTP adapter connection pool with size `16`.
3. Pass the same session to `Transcription.async_call(...)`.
4. Pass the same session to `Transcription.wait(...)`.
5. Download `transcription_url` through `self.session.get(...)`.
6. Use result download timeout `(10, 300)`.
7. Retry result download `requests.RequestException` failures up to `8` attempts.
8. Retry `Transcription.wait(...)` transport failures up to `5` attempts.
9. Log retry events with `aliyun_transcription_result_download_retrying` and `aliyun_transcription_wait_retrying`.
10. Raise immediately on malformed result JSON instead of retrying invalid content.
11. Keep tests fully fake; no real Aliyun, OSS, DashScope, or network access.

## Module organization

```text
src/podcast_agent/transcribers/
└── aliyun.py                  Aliyun ASR client, result download, session reuse, chunk orchestration

tests/
└── test_transcribers_aliyun.py
```

No CLI, source detection, report generation, insight generation, or artifact format modules should change.

## Responsibility boundaries

### `transcribers/aliyun.py`

Owns:

- Constructing the default `requests.Session`.
- Mounting HTTP and HTTPS adapters with pool size `16`.
- Submitting DashScope ASR tasks with `session=self.session`.
- Polling DashScope ASR task status with `session=self.session`.
- Retrying transient `Transcription.wait(...)` transport failures.
- Reading `transcription_url` from successful subtasks.
- Downloading final result JSON through `self.session.get(...)`.
- Retrying transient result download failures.
- Parsing result JSON and raising a clear parse error for invalid JSON.
- Merging chunk transcripts in source order.

Should expose:

- `connection_pool_size = 16`
- `result_download_attempts = 8`
- `result_download_timeout = (10, 300)`
- `transcription_wait_attempts = 5`

Does not own:

- OSS credential loading beyond upload/download URL generation.
- CLI option parsing.
- Batch job concurrency outside this transcriber.
- Report generation.

### `tests/test_transcribers_aliyun.py`

Owns:

- Aliyun result parsing tests.
- No-words response tests.
- Chunk offset and merge behavior tests.
- Session connection pool tests.
- Result download retry behavior tests.
- Result download exhaustion tests.
- Malformed JSON no-retry tests.
- SDK session reuse tests.
- `Transcription.wait(...)` transport retry tests.

Should use fakes or monkeypatching for:

- `requests.Session.get`
- `Transcription.async_call`
- `Transcription.wait`
- `time.sleep`
- response objects

Should not require:

- real DashScope API keys
- real OSS buckets
- network access

## Implementation sequence

1. Update `AliyunAsrClient` constants:
   - `connection_pool_size = 16`
   - `result_download_attempts = 8`
   - `result_download_timeout = (10, 300)`
   - `transcription_wait_attempts = 5`

2. Add session construction:
   - create `requests.Session()`
   - mount one `HTTPAdapter(pool_connections=16, pool_maxsize=16)` for `http://`
   - mount the same adapter for `https://`
   - allow tests to inject a session

3. Update ASR task submission:
   - call `Transcription.async_call(..., session=self.session)`

4. Add `_wait_for_transcription()`:
   - call `Transcription.wait(task=task_id, session=self.session)`
   - catch `requests.RequestException`
   - retry up to `5` attempts
   - use exponential backoff `1s, 2s, 4s, 8s...`
   - log `aliyun_transcription_wait_retrying`
   - raise `AudioTranscriptionError` after retry exhaustion

5. Update result download:
   - replace `urllib.request.urlopen` with `self.session.get(...)`
   - set `headers={"Accept": "application/json", "User-Agent": "Podcast-Agent/0.1"}`
   - set `timeout=self.result_download_timeout`
   - set `allow_redirects=True`
   - call `response.raise_for_status()`
   - return `response.json()`

6. Update result download error handling:
   - catch `requests.RequestException`
   - retry up to `8` attempts
   - use exponential backoff capped at `8`
   - log `aliyun_transcription_result_download_retrying`
   - after exhaustion, raise `AudioTranscriptionError` with host only
   - catch JSON `ValueError` separately and raise `AudioTranscriptionError("Failed to parse Aliyun transcription result JSON")`

7. Update tests:
   - add fake session and fake HTTP response helpers
   - assert default connection pool size is `16`
   - assert temporary `SSLError` retries and then succeeds
   - assert `ReadTimeout` retries exhaust after `8` attempts
   - assert result download timeout is `(10, 300)`
   - assert malformed JSON is not retried
   - assert SDK submit/wait calls receive the injected session
   - assert wait transport errors retry and use `5` attempts

8. Run focused tests:

```bash
.venv/bin/python -m pytest tests/test_transcribers_aliyun.py
```

9. Run broader tests if needed:

```bash
.venv/bin/python -m pytest
```

## Acceptance criteria

- Result JSON download uses `self.session.get(...)`.
- Result JSON download uses timeout `(10, 300)`.
- Result JSON download retries `requests.RequestException` failures up to `8` attempts.
- JSON parse failures are not retried.
- Retry delay uses exponential backoff capped at 8 seconds.
- Retry exhaustion raises `AudioTranscriptionError`.
- Error message includes the result URL host, not a full signed URL.
- Default session has HTTP and HTTPS connection pool size `16`.
- `Transcription.async_call(...)` receives `session=self.session`.
- `Transcription.wait(...)` receives `session=self.session`.
- `Transcription.wait(...)` transport failures retry up to `5` attempts.
- Tests prove all of the above without network access.
- Existing parsing and chunk offset tests continue to pass.

## Non-goals

- Do not add new CLI flags for timeout or retry settings.
- Do not change `chunk_max_workers` default.
- Do not change OSS upload/delete behavior.
- Do not introduce real Aliyun integration tests.
- Do not change report, insight, source, or artifact behavior.
