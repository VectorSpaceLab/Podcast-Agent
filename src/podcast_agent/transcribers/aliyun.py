"""Aliyun DashScope ASR transcription provider."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from http import HTTPStatus
import logging
from pathlib import Path
import time
from typing import Any, Protocol
from urllib.parse import urlparse
from uuid import uuid4

import requests
from requests.adapters import HTTPAdapter

from podcast_agent.errors import AudioTranscriptionError
from podcast_agent.transcribers.audio_prepare import (
    prepare_audio_for_transcription,
    split_audio_by_duration,
)
from podcast_agent.transcribers.types import TranscriptionRequest, TranscriptionResult
from podcast_agent.types import TranscriptSegment


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AliyunTranscriberConfig:
    api_key: str
    oss_endpoint: str
    oss_bucket_name: str
    oss_access_key_id: str
    oss_access_key_secret: str
    api_base: str = "https://dashscope.aliyuncs.com/api/v1"
    model: str = "fun-asr"
    language_hints: tuple[str, ...] = ("zh", "en")
    poll_interval_sec: float = 2.0
    poll_timeout_sec: float = 900.0
    chunk_duration_seconds: int = 1800
    chunk_max_workers: int = 4
    oss_object_prefix: str = "audio/"
    signed_url_expires_sec: int = 3600
    retain_remote_artifacts: bool = False


class ArtifactStore(Protocol):
    def upload_file(self, local_path: Path, object_key: str) -> str:
        ...

    def get_signed_download_url(self, object_key: str) -> str:
        ...

    def delete_object(self, object_key: str) -> None:
        ...


class AsrClient(Protocol):
    def transcribe_from_url(
        self,
        file_url: str,
        *,
        language_hints: tuple[str, ...],
    ) -> list[TranscriptSegment]:
        ...


class AliyunOssStore:
    def __init__(self, config: AliyunTranscriberConfig) -> None:
        self.config = config
        self._bucket: Any | None = None

    def upload_file(self, local_path: Path, object_key: str) -> str:
        bucket = self._load_bucket()
        with local_path.open("rb") as handle:
            bucket.put_object(object_key, handle)
        return object_key

    def get_signed_download_url(self, object_key: str) -> str:
        bucket = self._load_bucket()
        return bucket.sign_url("GET", object_key, self.config.signed_url_expires_sec)

    def delete_object(self, object_key: str) -> None:
        bucket = self._load_bucket()
        bucket.delete_object(object_key)

    def _load_bucket(self) -> Any:
        if self._bucket is not None:
            return self._bucket
        try:
            import oss2  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AudioTranscriptionError("oss2 is required for Aliyun OSS uploads.") from exc

        auth = oss2.Auth(
            self.config.oss_access_key_id,
            self.config.oss_access_key_secret,
        )
        self._bucket = oss2.Bucket(
            auth,
            self.config.oss_endpoint,
            self.config.oss_bucket_name,
        )
        return self._bucket


class AliyunAsrClient:
    connection_pool_size = 16
    result_download_attempts = 8
    result_download_timeout = (10, 300)
    transcription_wait_attempts = 5

    def __init__(self, config: AliyunTranscriberConfig, *, session: requests.Session | None = None) -> None:
        self.config = config
        self.session = session or self._build_session()

    def _build_session(self) -> requests.Session:
        session = requests.Session()
        adapter = HTTPAdapter(
            pool_connections=self.connection_pool_size,
            pool_maxsize=self.connection_pool_size,
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def transcribe_from_url(
        self,
        file_url: str,
        *,
        language_hints: tuple[str, ...],
    ) -> list[TranscriptSegment]:
        try:
            import dashscope  # type: ignore[import-not-found]
            from dashscope.audio.asr import Transcription  # type: ignore[import-not-found]
        except ImportError as exc:
            raise AudioTranscriptionError("dashscope is required for Aliyun ASR transcription.") from exc

        dashscope.base_http_api_url = self.config.api_base
        dashscope.api_key = self.config.api_key
        task_response = Transcription.async_call(
            model=self.config.model,
            file_urls=[file_url],
            language_hints=list(language_hints),
            session=self.session,
        )
        if task_response.status_code != HTTPStatus.OK:
            raise AudioTranscriptionError(f"Failed to submit Aliyun transcription task: {task_response.message}")

        task_id = task_response.output.task_id
        started = time.time()
        while True:
            if time.time() - started > self.config.poll_timeout_sec:
                raise AudioTranscriptionError(f"Aliyun transcription timed out after {self.config.poll_timeout_sec}s")

            response = self._wait_for_transcription(Transcription, task_id)
            if response.status_code != HTTPStatus.OK:
                raise AudioTranscriptionError(f"Aliyun transcription failed: {response.message}")

            results = response.output.get("results", [])
            for result in results:
                if result.get("subtask_status") == "SUCCEEDED":
                    transcription_url = result.get("transcription_url")
                    if transcription_url:
                        raw_result = self._download_transcription_result(str(transcription_url))
                        return parse_aliyun_transcription_result(raw_result)

            for result in results:
                if result.get("subtask_status") == "FAILED":
                    if is_no_words_response(result):
                        return []
                    raise AudioTranscriptionError(f"Aliyun transcription subtask failed: {result.get('message', result)}")

            time.sleep(self.config.poll_interval_sec)

    def _wait_for_transcription(self, transcription: Any, task_id: str):
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.transcription_wait_attempts + 1):
            try:
                return transcription.wait(task=task_id, session=self.session)
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.transcription_wait_attempts:
                    delay = min(2 ** (attempt - 1), 8)
                    logger.warning(
                        "aliyun_transcription_wait_retrying host=%s attempt=%s/%s delay=%s error=%s",
                        "dashscope.aliyuncs.com",
                        attempt,
                        self.transcription_wait_attempts,
                        delay,
                        exc.__class__.__name__,
                    )
                    time.sleep(delay)
        raise AudioTranscriptionError(f"Aliyun transcription wait failed after retries: {last_error}") from last_error

    def _download_transcription_result(self, transcription_url: str) -> dict[str, Any]:
        host = urlparse(transcription_url).netloc or "<unknown>"
        last_error: requests.RequestException | None = None
        for attempt in range(1, self.result_download_attempts + 1):
            try:
                response = self.session.get(
                    transcription_url,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "Podcast-Agent/0.1",
                    },
                    timeout=self.result_download_timeout,
                    allow_redirects=True,
                )
                response.raise_for_status()
                return response.json()
            except requests.RequestException as exc:
                last_error = exc
                if attempt < self.result_download_attempts:
                    delay = min(2 ** (attempt - 1), 8)
                    logger.warning(
                        "aliyun_transcription_result_download_retrying host=%s attempt=%s/%s delay=%s error=%s",
                        host,
                        attempt,
                        self.result_download_attempts,
                        delay,
                        exc.__class__.__name__,
                    )
                    time.sleep(delay)
            except ValueError as exc:
                raise AudioTranscriptionError("Failed to parse Aliyun transcription result JSON") from exc
        raise AudioTranscriptionError(f"Failed to download Aliyun transcription result from {host}: {last_error}") from last_error


class AliyunTranscriber:
    provider_name = "aliyun"

    def __init__(
        self,
        config: AliyunTranscriberConfig,
        *,
        artifact_store: ArtifactStore | None = None,
        asr_client: AsrClient | None = None,
    ) -> None:
        self.config = config
        self.artifact_store = artifact_store or AliyunOssStore(config)
        self.asr_client = asr_client or AliyunAsrClient(config)

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        normalized_audio = prepare_audio_for_transcription(request.audio_path)
        chunks = split_audio_by_duration(
            normalized_audio,
            normalized_audio.parent / "transcription_chunks_aliyun",
            chunk_duration_seconds=self.config.chunk_duration_seconds,
        )
        language_hints = request.language_hints or self.config.language_hints

        def transcribe_one(
            index: int,
            chunk_path: Path,
            offset_seconds: float,
        ) -> list[TranscriptSegment]:
            object_key = self._build_object_key(chunk_path)
            self.artifact_store.upload_file(chunk_path, object_key)
            try:
                signed_url = self.artifact_store.get_signed_download_url(object_key)
                chunk_segments = self.asr_client.transcribe_from_url(
                    signed_url,
                    language_hints=language_hints,
                )
                return [
                    TranscriptSegment(
                        start=segment.start + offset_seconds,
                        end=segment.end + offset_seconds,
                        text=segment.text,
                    )
                    for segment in chunk_segments
                    if segment.text.strip()
                ]
            finally:
                if not self.config.retain_remote_artifacts:
                    try:
                        self.artifact_store.delete_object(object_key)
                    except Exception:
                        pass

        chunk_results: dict[int, list[TranscriptSegment]] = {}
        if len(chunks) > 1 and self.config.chunk_max_workers > 1:
            with ThreadPoolExecutor(max_workers=self.config.chunk_max_workers) as executor:
                futures = {
                    executor.submit(transcribe_one, index, chunk_path, offset_seconds): index
                    for index, (chunk_path, offset_seconds) in enumerate(chunks, start=1)
                }
                for future in as_completed(futures):
                    chunk_results[futures[future]] = future.result()
        else:
            for index, (chunk_path, offset_seconds) in enumerate(chunks, start=1):
                chunk_results[index] = transcribe_one(index, chunk_path, offset_seconds)

        merged_segments: list[TranscriptSegment] = []
        for index in sorted(chunk_results):
            merged_segments.extend(chunk_results[index])
        return TranscriptionResult(provider=self.provider_name, segments=merged_segments)

    def _build_object_key(self, audio_path: Path) -> str:
        prefix = self.config.oss_object_prefix.strip("/")
        unique_id = uuid4().hex
        if prefix:
            return f"{prefix}/{unique_id}/{audio_path.name}"
        return f"{unique_id}/{audio_path.name}"


def parse_aliyun_transcription_result(raw_result: dict[str, Any]) -> list[TranscriptSegment]:
    transcript_items = raw_result.get("transcripts") or []
    if not transcript_items:
        return []

    first_transcript = transcript_items[0]
    if not isinstance(first_transcript, dict):
        return []

    sentences = first_transcript.get("sentences") or []
    segments: list[TranscriptSegment] = []
    for sentence in sentences:
        if not isinstance(sentence, dict):
            continue
        text = str(sentence.get("text", "")).strip()
        if not text:
            continue
        segments.append(
            TranscriptSegment(
                start=float(sentence.get("begin_time", 0)) / 1000.0,
                end=float(sentence.get("end_time", 0)) / 1000.0,
                text=text,
            )
        )
    return segments


def is_no_words_response(result: dict[str, Any]) -> bool:
    code = str(result.get("code") or "").strip()
    message = str(result.get("message") or "").strip()
    return code == "ASR_RESPONSE_HAVE_NO_WORDS" or message == "ASR_RESPONSE_HAVE_NO_WORDS"
