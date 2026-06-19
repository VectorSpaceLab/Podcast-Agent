from http import HTTPStatus
from pathlib import Path
from types import SimpleNamespace

import pytest
import requests

from podcast_agent.errors import AudioTranscriptionError
from podcast_agent.transcribers.aliyun import (
    AliyunAsrClient,
    AliyunTranscriber,
    AliyunTranscriberConfig,
    is_no_words_response,
    parse_aliyun_transcription_result,
)
from podcast_agent.transcribers.types import TranscriptionRequest
from podcast_agent.types import TranscriptSegment


def _config() -> AliyunTranscriberConfig:
    return AliyunTranscriberConfig(
        api_key="key",
        oss_endpoint="endpoint",
        oss_bucket_name="bucket",
        oss_access_key_id="access",
        oss_access_key_secret="secret",
        chunk_duration_seconds=1800,
        chunk_max_workers=1,
    )


def test_parse_aliyun_transcription_result_parses_sentences() -> None:
    raw = {
        "transcripts": [
            {
                "sentences": [
                    {"begin_time": 0, "end_time": 1500, "text": "第一句。"},
                    {"begin_time": 1500, "end_time": 3000, "text": "第二句。"},
                    {"begin_time": 3000, "end_time": 3500, "text": " "},
                ]
            }
        ]
    }

    assert parse_aliyun_transcription_result(raw) == [
        TranscriptSegment(start=0.0, end=1.5, text="第一句。"),
        TranscriptSegment(start=1.5, end=3.0, text="第二句。"),
    ]


def test_parse_aliyun_transcription_result_returns_empty_for_missing_sentences() -> None:
    assert parse_aliyun_transcription_result({"transcripts": []}) == []


def test_is_no_words_response() -> None:
    assert is_no_words_response({"code": "ASR_RESPONSE_HAVE_NO_WORDS"})
    assert is_no_words_response({"message": "ASR_RESPONSE_HAVE_NO_WORDS"})
    assert not is_no_words_response({"code": "OTHER"})


class FakeHttpResponse:
    def __init__(self, payload: dict | None = None, *, json_error: ValueError | None = None) -> None:
        self.payload = payload or {}
        self.json_error = json_error
        self.raise_for_status_calls = 0

    def raise_for_status(self) -> None:
        self.raise_for_status_calls += 1

    def json(self) -> dict:
        if self.json_error is not None:
            raise self.json_error
        return self.payload


class FakeSession:
    def __init__(self, *responses) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_aliyun_client_builds_session_with_connection_pool() -> None:
    client = AliyunAsrClient(_config())
    https_adapter = client.session.get_adapter("https://example.com")

    assert client.connection_pool_size == 16
    assert https_adapter._pool_connections == client.connection_pool_size
    assert https_adapter._pool_maxsize == client.connection_pool_size


def test_aliyun_result_download_retries_temporary_errors(monkeypatch) -> None:
    session = FakeSession(
        requests.exceptions.SSLError("temporary TLS EOF"),
        FakeHttpResponse({"transcripts": []}),
    )
    client = AliyunAsrClient(_config(), session=session)
    sleeps: list[float] = []

    monkeypatch.setattr("podcast_agent.transcribers.aliyun.time.sleep", sleeps.append)

    assert client._download_transcription_result("https://dashscope-result-bj.example.com/result.json") == {
        "transcripts": []
    }
    assert len(session.calls) == 2
    assert session.calls[0]["timeout"] == client.result_download_timeout
    assert session.calls[0]["allow_redirects"] is True
    assert client.result_download_attempts == 8
    assert sleeps == [1]


def test_aliyun_result_download_raises_after_retry_exhaustion(monkeypatch) -> None:
    session = FakeSession(*[requests.exceptions.ReadTimeout("read timed out") for _ in range(8)])
    client = AliyunAsrClient(_config(), session=session)

    monkeypatch.setattr("podcast_agent.transcribers.aliyun.time.sleep", lambda delay: None)

    with pytest.raises(AudioTranscriptionError) as exc_info:
        client._download_transcription_result("https://dashscope-result-bj.example.com/result.json?signature=secret")

    assert len(session.calls) == client.result_download_attempts
    message = str(exc_info.value)
    assert "dashscope-result-bj.example.com" in message
    assert "signature=secret" not in message


def test_aliyun_result_download_passes_configured_timeout() -> None:
    session = FakeSession(FakeHttpResponse({"transcripts": []}))
    client = AliyunAsrClient(_config(), session=session)

    assert client._download_transcription_result("https://dashscope-result-bj.example.com/result.json") == {
        "transcripts": []
    }
    assert session.calls == [
        {
            "url": "https://dashscope-result-bj.example.com/result.json",
            "headers": {
                "Accept": "application/json",
                "User-Agent": "Podcast-Agent/0.1",
            },
            "timeout": (10, 300),
            "allow_redirects": True,
        }
    ]


def test_aliyun_result_download_does_not_retry_malformed_json() -> None:
    session = FakeSession(FakeHttpResponse(json_error=ValueError("invalid json")))
    client = AliyunAsrClient(_config(), session=session)

    with pytest.raises(AudioTranscriptionError, match="Failed to parse Aliyun transcription result JSON"):
        client._download_transcription_result("https://dashscope-result-bj.example.com/result.json")

    assert len(session.calls) == 1


class FakeTranscriptionResponse:
    def __init__(self, *, status_code=HTTPStatus.OK, output=None, message="") -> None:
        self.status_code = status_code
        self.output = output or {}
        self.message = message


def test_aliyun_client_reuses_session_for_sdk_calls(monkeypatch) -> None:
    session = FakeSession(FakeHttpResponse({"transcripts": []}))
    client = AliyunAsrClient(_config(), session=session)
    calls: dict[str, object] = {}

    from dashscope.audio.asr import Transcription

    def fake_async_call(**kwargs):
        calls["async_session"] = kwargs["session"]
        return FakeTranscriptionResponse(output=SimpleNamespace(task_id="task-1"))

    def fake_wait(**kwargs):
        calls["wait_session"] = kwargs["session"]
        return FakeTranscriptionResponse(
            output={
                "results": [
                    {
                        "subtask_status": "SUCCEEDED",
                        "transcription_url": "https://dashscope-result-bj.example.com/result.json",
                    }
                ]
            }
        )

    monkeypatch.setattr(Transcription, "async_call", fake_async_call)
    monkeypatch.setattr(Transcription, "wait", fake_wait)

    assert client.transcribe_from_url("https://example.com/audio.wav", language_hints=("zh",)) == []
    assert calls["async_session"] is session
    assert calls["wait_session"] is session


def test_aliyun_client_retries_transcription_wait_transport_errors(monkeypatch) -> None:
    session = FakeSession()
    client = AliyunAsrClient(_config(), session=session)
    sleeps: list[float] = []
    calls = 0

    class FakeTranscription:
        @staticmethod
        def wait(*, task, session):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise requests.exceptions.ConnectionError("connection reset")
            return FakeTranscriptionResponse(output={"results": []})

    monkeypatch.setattr("podcast_agent.transcribers.aliyun.time.sleep", sleeps.append)

    response = client._wait_for_transcription(FakeTranscription, "task-1")

    assert response.output == {"results": []}
    assert calls == 2
    assert sleeps == [1]
    assert client.transcription_wait_attempts == 5


class FakeArtifactStore:
    def __init__(self) -> None:
        self.uploads: list[tuple[Path, str]] = []
        self.deleted: list[str] = []

    def upload_file(self, local_path: Path, object_key: str) -> str:
        self.uploads.append((local_path, object_key))
        return object_key

    def get_signed_download_url(self, object_key: str) -> str:
        return f"https://example.com/{object_key}"

    def delete_object(self, object_key: str) -> None:
        self.deleted.append(object_key)


class FakeAsrClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def transcribe_from_url(
        self,
        file_url: str,
        *,
        language_hints: tuple[str, ...],
    ) -> list[TranscriptSegment]:
        self.calls.append((file_url, language_hints))
        return [TranscriptSegment(start=0.0, end=1.0, text=file_url.rsplit("/", 1)[-1])]


def test_aliyun_transcriber_merges_chunk_offsets(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"raw")
    normalized = tmp_path / "audio.16k-mono.wav"
    normalized.write_bytes(b"normalized")
    chunks_dir = tmp_path / "transcription_chunks_aliyun"
    chunks_dir.mkdir()
    (chunks_dir / "chunk_000.wav").write_bytes(b"0")
    (chunks_dir / "chunk_001.wav").write_bytes(b"1")
    store = FakeArtifactStore()
    asr = FakeAsrClient()

    result = AliyunTranscriber(
        _config(),
        artifact_store=store,
        asr_client=asr,
    ).transcribe(TranscriptionRequest(audio_path=audio_path, language_hints=("zh",)))

    assert result.provider == "aliyun"
    assert len(result.segments) == 2
    assert result.segments[0].start == 0.0
    assert result.segments[1].start == 1800.0
    assert asr.calls[0][1] == ("zh",)
    assert len(store.uploads) == 2
    assert len(store.deleted) == 2
