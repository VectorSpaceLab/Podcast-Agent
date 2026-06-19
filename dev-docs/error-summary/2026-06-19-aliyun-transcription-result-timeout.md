# 阿里云转录结果下载 ReadTimeout 问题总结

## 问题概述

在 Podcast-Agent 音频转录 fallback 中，阿里云 ASR 任务本身可能已经提交成功并完成处理，但后续下载最终转录结果 JSON 时失败：

```text
error_type: ReadTimeout
error: HTTPSConnectionPool(host='dashscope-result-bj.oss-cn-beijing.aliyuncs.com', port=443): Read timed out. (read timeout=10)
```

后续日志里如果出现：

```text
KeyboardInterrupt
```

通常表示进程被人工中断，例如按下 `Ctrl+C`。这不是根因；本次需要定位和处理的根因是更早发生的阿里云转录结果 JSON 下载 `ReadTimeout`。

## 准确问题位置

问题不发生在 OSS 上传或提交阿里云 ASR 任务阶段，而发生在任务成功后读取 `transcription_url` 的阶段。

运行链路如下：

```text
src/podcast_agent/transcribers/aliyun.py
AliyunTranscriber.transcribe(...)
  -> AliyunAsrClient.transcribe_from_url(...)
  -> Transcription.async_call(...)
  -> AliyunAsrClient._wait_for_transcription(...)
  -> Transcription.wait(...)
  -> response.output["results"]
  -> result["transcription_url"]
  -> AliyunAsrClient._download_transcription_result(...)
```

精确代码位置：

- `src/podcast_agent/transcribers/aliyun.py:143-148`：提交阿里云转录任务，并传入复用的 `session`。
- `src/podcast_agent/transcribers/aliyun.py:158`：等待阿里云转录任务结果。
- `src/podcast_agent/transcribers/aliyun.py:178-196`：`Transcription.wait(...)` 的传输层重试。
- `src/podcast_agent/transcribers/aliyun.py:162-168`：读取 `results`，取出 `transcription_url` 并下载结果 JSON。
- `src/podcast_agent/transcribers/aliyun.py:198-229`：真正执行结果 JSON 下载的位置，即 `_download_transcription_result()`。

失败主机通常是阿里云 DashScope 生成的临时 OSS 结果地址：

```text
dashscope-result-bj.oss-cn-beijing.aliyuncs.com
```

这和提交任务接口不同。提交接口默认是：

```text
https://dashscope.aliyuncs.com/api/v1
```

## 直接原因

原始失败日志中的关键点是：

```text
read timeout=10
```

这说明连接已经建立，但在读取响应内容时 10 秒内没有读完或没有收到后续数据。长音频切片生成的转录 JSON 可能较大，并发运行时多个 case 与多个切片会同时下载结果，10 秒读取超时过短，容易触发 `requests.exceptions.ReadTimeout`、临时 TLS/连接错误或 OSS 侧短暂卡顿。

并发压力大致来自两层：

```text
外层批处理并发 × 阿里云 chunk_max_workers
```

例如：

```text
--jobs 5 × chunk_max_workers 4 = 约 20 个并发切片操作
```

## 现在已经修改的代码位置

当前代码已经在阿里云 transcriber 内做了结果下载超时拆分、重试、任务等待传输层重试，以及 HTTP session/连接池复用。

### 1. 结果下载重试次数和超时配置

位置：

```text
src/podcast_agent/transcribers/aliyun.py:109-113
```

当前配置：

```python
class AliyunAsrClient:
    connection_pool_size = 16
    result_download_attempts = 8
    result_download_timeout = (10, 300)
    transcription_wait_attempts = 5
```

含义：

- 连接池大小：16。
- 连接超时：10 秒。
- 读取超时：300 秒。
- 下载结果最多尝试：8 次。
- 等待任务状态的传输层错误最多尝试：5 次。

这解决了原先日志中 `read timeout=10` 太短的问题。

### 2. 结果 JSON 下载逻辑

位置：

```text
src/podcast_agent/transcribers/aliyun.py:198-229
```

当前 `_download_transcription_result()` 已经：

- 使用 `self.session.get(...)` 下载 `transcription_url`。
- 设置 `timeout=self.result_download_timeout`，即 `(10, 300)`。
- 设置 `allow_redirects=True`。
- 调用 `response.raise_for_status()`。
- 捕获 `requests.RequestException`，包括 `ReadTimeout`、`ConnectionError`、`SSLError`、`HTTPError` 等网络/HTTP 类错误。
- 下载失败时记录 `aliyun_transcription_result_download_retrying` 日志。
- 使用指数退避重试：`1s, 2s, 4s, 8s...`，最大 8 秒。
- 重试耗尽后抛出清晰的 `AudioTranscriptionError`。
- JSON 解析失败时直接抛出 `AudioTranscriptionError("Failed to parse Aliyun transcription result JSON")`，避免无限重试无效内容。

### 3. 阿里云任务轮询也增加了传输层重试

位置：

```text
src/podcast_agent/transcribers/aliyun.py:178-196
```

当前 `_wait_for_transcription()` 已经对 `Transcription.wait(...)` 的 `requests.RequestException` 做最多 5 次重试，并记录：

```text
aliyun_transcription_wait_retrying
```

这不是本次 `read timeout=10` 的直接失败点，但可以缓解等待任务状态时发生的临时 TLS EOF、连接重置等传输层异常。

### 4. 复用 HTTP session 和连接池

位置：

```text
src/podcast_agent/transcribers/aliyun.py:115-127
```

当前 `AliyunAsrClient` 默认构建 `requests.Session`，并配置 HTTP adapter 连接池：

```python
connection_pool_size = 16
```

提交任务、等待任务、下载结果都通过同一个 session 传递或执行：

- `src/podcast_agent/transcribers/aliyun.py:143-148`：`Transcription.async_call(..., session=self.session)`。
- `src/podcast_agent/transcribers/aliyun.py:182`：`Transcription.wait(..., session=self.session)`。
- `src/podcast_agent/transcribers/aliyun.py:203-211`：`self.session.get(...)` 下载结果 JSON。

## 已有测试覆盖位置

相关单元测试在：

```text
tests/test_transcribers_aliyun.py
```

重点测试：

- `test_aliyun_client_builds_session_with_connection_pool`
  - 验证默认 session 配置了 16 个连接池大小。
- `test_aliyun_result_download_retries_temporary_errors`
  - 验证结果下载遇到临时 `SSLError` 后会重试。
  - 验证结果下载 timeout 是 `(10, 300)`。
  - 验证最多下载尝试配置是 `8`。
- `test_aliyun_result_download_raises_after_retry_exhaustion`
  - 验证重试耗尽后抛出 `AudioTranscriptionError`。
  - 验证错误消息只包含 host，不泄露完整带签名 URL。
- `test_aliyun_result_download_does_not_retry_malformed_json`
  - 验证 JSON 解析失败直接抛错，不做无效重试。
- `test_aliyun_client_reuses_session_for_sdk_calls`
  - 验证 SDK 提交、等待、结果下载复用注入的 session。
- `test_aliyun_client_retries_transcription_wait_transport_errors`
  - 验证 `Transcription.wait(...)` 遇到临时传输错误后会重试。
  - 验证等待任务最多尝试配置是 `5`。

建议验证命令：

```bash
.venv/bin/python -m pytest tests/test_transcribers_aliyun.py
```

或运行全量测试：

```bash
.venv/bin/python -m pytest
```

## 运行时确认方式

如果运行环境仍然出现：

```text
read timeout=10
```

优先确认部署环境中的文件是否是最新版本：

```bash
grep -n "connection_pool_size\|result_download_attempts\|result_download_timeout\|session=self.session" \
  src/podcast_agent/transcribers/aliyun.py
```

预期能看到：

```text
connection_pool_size = 16
result_download_attempts = 8
result_download_timeout = (10, 300)
session=self.session
timeout=self.result_download_timeout
```

同时检查日志中是否出现重试事件：

```bash
grep -R "aliyun_transcription_result_download_retrying\|aliyun_transcription_wait_retrying\|ReadTimeout\|SSLError" \
  output/run-logs/*.log
```

## 建议验证流程

先低并发确认阿里云结果下载稳定性：

```bash
.venv/bin/podcast-agent transcribe-audio <audio-file> --output-dir output/transcribe-debug
```

再逐步提高外层并发和 `chunk_max_workers`。

如果 `ReadTimeout`、`SSLError`、TLS EOF 类错误随并发增大明显增加，需要降低外层并发或降低阿里云切片并发 `chunk_max_workers`。
