from pathlib import Path
from typing import Any

from podcast_agent.types import TranscriptSegment
from podcast_agent.transcribers.types import TranscriptionRequest, TranscriptionResult


class FakeMetadataDownloader:
    def __init__(self, info: dict[str, Any] | None = None) -> None:
        self.info = info or fake_metadata_info()
        self.calls: list[tuple[str, Path]] = []

    def extract_info(self, url: str, *, output_dir: Path) -> dict[str, Any]:
        self.calls.append((url, output_dir))
        return self.info


def fake_metadata_info() -> dict[str, Any]:
    return {
        "id": "dQw4w9WgXcQ",
        "title": "Example Video",
        "uploader": "Example Channel",
        "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "duration": 212,
        "description": "Example description",
        "upload_date": "20091025",
        "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/maxresdefault.jpg",
        "local_thumbnail_path": "/tmp/output/elements/dQw4w9WgXcQ.jpg",
        "chapters": [
            {"start_time": 60, "title": "Middle"},
            {"start": "00:00:00.000", "title": "Opening"},
            {"timestamp": "00:01:00", "title": "Duplicate middle"},
            {"time": "00:02:00.500", "name": "Ending"},
        ],
    }


class FakeTranscriptDownloader:
    def __init__(
        self,
        *,
        info: dict[str, Any] | None = None,
        subtitle_suffix: str = ".vtt",
        fail_downloads: int = 0,
        audio_duration: float = 212.0,
    ) -> None:
        self.info = info if info is not None else fake_transcript_info()
        self.subtitle_suffix = subtitle_suffix
        self.fail_downloads = fail_downloads
        self.audio_duration = audio_duration
        self.extract_calls: list[tuple[str, Path]] = []
        self.subtitle_calls: list[tuple[str, Path, str, str]] = []
        self.audio_calls: list[tuple[str, Path]] = []

    def extract_info(self, url: str, *, output_dir: Path) -> dict[str, Any]:
        self.extract_calls.append((url, output_dir))
        return self.info

    def download_subtitle(
        self,
        url: str,
        *,
        output_dir: Path,
        language: str,
        track_kind: str,
    ) -> dict[str, Any]:
        self.subtitle_calls.append((url, output_dir, language, track_kind))
        if len(self.subtitle_calls) <= self.fail_downloads:
            raise RuntimeError("subtitle download failed")
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"dQw4w9WgXcQ.{language}{self.subtitle_suffix}"
        if self.subtitle_suffix == ".srt":
            path.write_text(fake_srt_content(), encoding="utf-8")
        else:
            path.write_text(fake_vtt_content(), encoding="utf-8")
        return {
            "requested_subtitles": {
                language: {
                    "filepath": str(path),
                }
            }
        }

    def download_audio(self, url: str, *, output_dir: Path) -> dict[str, Any]:
        self.audio_calls.append((url, output_dir))
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / "dQw4w9WgXcQ.wav"
        path.write_bytes(b"fake audio")
        return {
            "duration": self.audio_duration,
            "requested_downloads": [
                {
                    "filepath": str(path),
                }
            ],
        }


class FakeAudioTranscriber:
    provider_name = "fake"

    def __init__(self) -> None:
        self.calls: list[tuple[Path, str | None]] = []

    def transcribe(self, request: TranscriptionRequest) -> TranscriptionResult:
        language = request.language_hints[0] if request.language_hints else None
        self.calls.append((request.audio_path, language))
        return TranscriptionResult(
            provider=self.provider_name,
            segments=[
                TranscriptSegment(start=0.0, end=1.5, text="转录第一句。"),
                TranscriptSegment(start=1.5, end=3.0, text="转录第二句。"),
            ],
        )


def fake_transcript_info() -> dict[str, Any]:
    return {
        "subtitles": {
            "en": [{"ext": "vtt"}],
            "zh-Hans": [{"ext": "vtt"}],
        },
        "automatic_captions": {
            "zh": [{"ext": "vtt"}],
        },
    }


def fake_vtt_content() -> str:
    return "WEBVTT\n\n00:00:00.000 --> 00:00:01.500\n第一句字幕。\n\n00:00:01.500 --> 00:00:03.000\n第二句字幕。\n"


def fake_srt_content() -> str:
    return "1\n00:00:00,000 --> 00:00:01,500\n第一句字幕。\n\n2\n00:00:01,500 --> 00:00:03,000\n第二句字幕。\n"
