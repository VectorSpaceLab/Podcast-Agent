from pathlib import Path

from podcast_agent.transcribers.aliyun import (
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
