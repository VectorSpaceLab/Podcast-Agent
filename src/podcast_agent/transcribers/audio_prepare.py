"""Audio normalization and chunking helpers for transcription."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess

from podcast_agent.errors import AudioTranscriptionError


def prepare_audio_for_transcription(audio_path: Path) -> Path:
    normalized_audio_path = audio_path.parent / f"{audio_path.stem}.16k-mono.wav"
    if _is_non_empty_file(normalized_audio_path):
        return normalized_audio_path

    command = [
        _resolve_tool_path("FFMPEG_BIN", "ffmpeg"),
        "-y",
        "-i",
        str(audio_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(normalized_audio_path),
    ]
    _run(command, "Failed to normalize audio with ffmpeg")
    if not _is_non_empty_file(normalized_audio_path):
        raise AudioTranscriptionError(f"ffmpeg did not produce a normalized WAV file for {audio_path}")
    return normalized_audio_path


def split_audio_by_duration(
    audio_path: Path,
    chunks_dir: Path,
    *,
    chunk_duration_seconds: int = 1800,
) -> list[tuple[Path, float]]:
    if chunk_duration_seconds <= 0:
        raise AudioTranscriptionError(f"Invalid chunk duration for audio chunking: {chunk_duration_seconds}")

    chunks_dir.mkdir(parents=True, exist_ok=True)
    existing_chunks = _existing_chunks(chunks_dir)
    if not existing_chunks:
        command = [
            _resolve_tool_path("FFMPEG_BIN", "ffmpeg"),
            "-y",
            "-i",
            str(audio_path),
            "-f",
            "segment",
            "-segment_time",
            str(chunk_duration_seconds),
            "-c",
            "copy",
            str(chunks_dir / "chunk_%03d.wav"),
        ]
        _run(command, "Failed to split audio with ffmpeg")
        existing_chunks = _existing_chunks(chunks_dir)

    if not existing_chunks:
        raise AudioTranscriptionError(f"ffmpeg did not produce audio chunks for {audio_path}")

    return [
        (chunk, index * float(chunk_duration_seconds))
        for index, chunk in enumerate(existing_chunks)
    ]


def _existing_chunks(chunks_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(chunks_dir.glob("chunk_*.wav"))
        if _is_non_empty_file(path)
    ]


def _is_non_empty_file(path: Path) -> bool:
    return path.is_file() and path.stat().st_size > 0


def _resolve_tool_path(env_var: str, tool_name: str) -> str:
    configured = os.environ.get(env_var)
    if configured and configured.strip():
        return configured.strip()
    return shutil.which(tool_name) or tool_name


def _run(command: list[str], message: str) -> None:
    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise AudioTranscriptionError(f"{message}: {exc}") from exc
