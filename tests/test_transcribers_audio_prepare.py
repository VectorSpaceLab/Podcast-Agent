from pathlib import Path

from podcast_agent.transcribers.audio_prepare import (
    prepare_audio_for_transcription,
    split_audio_by_duration,
)


def test_prepare_audio_for_transcription_reuses_existing_normalized_file(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"raw")
    normalized = tmp_path / "audio.16k-mono.wav"
    normalized.write_bytes(b"normalized")

    assert prepare_audio_for_transcription(audio_path) == normalized


def test_split_audio_by_duration_reuses_existing_chunks(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.16k-mono.wav"
    audio_path.write_bytes(b"audio")
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    chunk_0 = chunks_dir / "chunk_000.wav"
    chunk_1 = chunks_dir / "chunk_001.wav"
    chunk_0.write_bytes(b"0")
    chunk_1.write_bytes(b"1")

    assert split_audio_by_duration(
        audio_path,
        chunks_dir,
        chunk_duration_seconds=1800,
    ) == [
        (chunk_0, 0.0),
        (chunk_1, 1800.0),
    ]
