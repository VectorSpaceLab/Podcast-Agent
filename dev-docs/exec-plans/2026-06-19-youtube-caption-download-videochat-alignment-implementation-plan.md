# YouTube caption download VideoChat alignment implementation plan

## Source decision

This plan implements:

- [YouTube Caption Download VideoChat Alignment Decision](../decisions/2026-06-19-youtube-caption-download-videochat-alignment-decision.md)

The goal is to make Podcast-Agent's YouTube subtitle acquisition behavior match the more stable VideoChat workflow-v2 implementation, without changing transcript, report, API, or insight artifact schemas.

## Minimum implementation

Required behavior:

1. Keep all existing output data formats unchanged.
2. Keep the current transcript ranking semantics unchanged.
3. Add a VideoChat-compatible candidate filter before subtitle download attempts.
4. Allow preferred-language automatic captions.
5. Allow any manual captions.
6. Exclude non-preferred-language automatic captions.
7. Keep the current default maximum subtitle download attempts at `3`.
8. Add `remote_components=["ejs:github"]` to YouTube base `yt-dlp` options.
9. Add `ignore_no_formats_error=True` to YouTube subtitle download options.
10. Add `sleep_interval_subtitles=30` to YouTube subtitle download options.
11. Add diagnostic logging around subtitle track listing, filtering, attempts, and failures.
12. Keep audio transcription fallback behavior unchanged.
13. Do not add `cookies_from_browser` in the minimum implementation.
14. Add focused regression tests for candidate filtering and `yt-dlp` option parity.

## Module organization

```text
src/podcast_agent/elements/
├── transcript_tracks.py
└── youtube_transcript.py

src/podcast_agent/downloaders/
└── yt_dlp.py

tests/
├── test_transcript_tracks.py
├── test_youtube_transcript_fetch.py
└── test_downloaders_yt_dlp.py
```

No API, report rendering, evidence extraction, outline generation, viewpoint generation, summary generation, CLI parsing, or transcriber modules should change for the minimum implementation.

## Responsibility boundaries

### `elements/transcript_tracks.py`

Owns:

- Reading manual and automatic caption tracks from `yt-dlp` info.
- Filtering unavailable or draft transcript tracks.
- Ranking tracks by language and track kind.
- Language matching helpers.

Should add:

- `transcript_download_candidates(...)`

The helper should:

- accept already-ranked tracks
- reuse existing normalized language matching behavior
- keep all tracks when no preferred language exists
- keep matching-language automatic tracks
- keep all manual tracks
- exclude non-matching automatic tracks

Should not change:

- `TranscriptLanguagePreference` fields
- `DEFAULT_TRANSCRIPT_LANGUAGES`
- `MAX_TRANSCRIPT_DOWNLOAD_ATTEMPTS`
- `transcript_tracks_from_info_for_source(...)`
- `rank_transcript_tracks(...)` ordering semantics

### `elements/youtube_transcript.py`

Owns:

- Fetching transcript data for YouTube and Bilibili sources.
- Listing subtitle tracks through the downloader.
- Downloading selected subtitle tracks.
- Falling back to audio transcription when configured.
- Writing transcript artifacts.

Should update:

- `_fetch_from_youtube_subtitles(...)`

Required flow:

1. Extract `yt-dlp` info.
2. Build and rank transcript tracks.
3. Log listed track count and preferred language.
4. Filter ranked tracks with `transcript_download_candidates(...)`.
5. If no accepted candidates remain, raise `TranscriptFetchError` so the existing audio fallback path can run when configured.
6. Limit accepted candidates by `max_download_attempts`.
7. Log when candidates are limited.
8. Log each download attempt with attempt number, language, track kind, and track id.
9. On failure, log language, track kind, track id, and error, then continue.
10. After all attempts fail, raise the same style of `TranscriptFetchError` currently used.

Should not change:

- `TranscriptInfo` construction
- `transcript.vtt` path
- `transcript.txt` path
- `transcript_info.json` shape
- `_download_track(...)` requested subtitle path lookup
- `_read_as_vtt(...)` normalization
- `_fetch_from_audio_transcription(...)`

### `downloaders/yt_dlp.py`

Owns:

- Shared `yt-dlp` option builders.
- YouTube downloader wrapper.
- Bilibili downloader wrapper.
- Requested download and subtitle integration.

Should update:

- `build_base_yt_dlp_options(...)`
- `build_subtitle_download_yt_dlp_options(...)`

Required option additions:

```python
"remote_components": ["ejs:github"]
"ignore_no_formats_error": True
"sleep_interval_subtitles": 30
```

Scope:

- `remote_components` belongs in the shared YouTube base options and will apply to metadata, subtitles, and audio.
- `ignore_no_formats_error` and `sleep_interval_subtitles` belong only in YouTube subtitle download options for the minimum implementation.
- Bilibili option builders should not be changed in this implementation.

## Implementation sequence

1. Add `transcript_download_candidates(...)` to `src/podcast_agent/elements/transcript_tracks.py`.

2. Implement candidate filtering:

```python
def transcript_download_candidates(
    tracks: list[TranscriptTrack],
    preference: TranscriptLanguagePreference | None = None,
) -> list[TranscriptTrack]:
    preference = preference or TranscriptLanguagePreference()
    preferred_language = preference.preferred_languages[0] if preference.preferred_languages else None
    if not preferred_language:
        return tracks
    return [
        track
        for track in tracks
        if _is_language_match(track.language, preferred_language) or track.track_kind != "automatic"
    ]
```

3. Add tests in `tests/test_transcript_tracks.py`:
   - preferred-language automatic captions are kept
   - `ai-zh` automatic captions match `zh-Hans` and are kept
   - non-preferred automatic captions are excluded
   - non-preferred manual captions are kept
   - all tracks are kept when the preference has no preferred languages

4. Import `transcript_download_candidates` in `src/podcast_agent/elements/youtube_transcript.py`.

5. Update `_fetch_from_youtube_subtitles(...)`:
   - rename local `tracks` to `ranked_tracks` for clarity
   - build `candidate_tracks`
   - use `candidate_tracks[: self.language_preference.max_download_attempts]` for attempts
   - keep the existing final `TranscriptFetchError` behavior

6. Add a module logger in `youtube_transcript.py`:

```python
import logging

LOGGER = logging.getLogger(__name__)
```

7. Add logging in `_fetch_from_youtube_subtitles(...)`:
   - `transcript_tracks_listed`
   - `transcript_tracks_no_acceptable_candidates`
   - `transcript_tracks_limited`
   - `transcript_download_attempt`
   - `transcript_download_attempt_failed`
   - `transcript_download_failed`

8. Keep log messages structured enough to search in `pipeline.log`, for example:

```text
youtube_transcript_tracks_listed | source_id=... | track_count=... | preferred_language=...
youtube_transcript_download_attempt | source_id=... | attempt=1 | language=zh | track_kind=automatic | track_id=zh
youtube_transcript_download_attempt_failed | source_id=... | language=zh | track_kind=automatic | error=...
```

9. Update `build_base_yt_dlp_options(...)` in `src/podcast_agent/downloaders/yt_dlp.py`:

```python
"remote_components": ["ejs:github"],
```

10. Update `build_subtitle_download_yt_dlp_options(...)`:

```python
"ignore_no_formats_error": True,
"sleep_interval_subtitles": 30,
```

11. Add tests in `tests/test_downloaders_yt_dlp.py`:
   - base options include `remote_components == ["ejs:github"]`
   - subtitle download options include `ignore_no_formats_error is True`
   - subtitle download options include `sleep_interval_subtitles == 30`

12. Add or update a test in `tests/test_youtube_transcript_fetch.py`:
   - fake info includes a preferred-language automatic track, a non-preferred automatic track, and a manual fallback track
   - configure preferred language as `zh-Hans`
   - make preferred-language automatic download fail
   - verify the fetcher attempts the manual fallback
   - verify the fetcher does not attempt the non-preferred automatic track

13. Run focused tests:

```bash
.venv/bin/python -m pytest \
  tests/test_transcript_tracks.py \
  tests/test_youtube_transcript_fetch.py \
  tests/test_downloaders_yt_dlp.py
```

14. Run full tests:

```bash
.venv/bin/python -m pytest
```

15. Review `git diff` and confirm:
   - no schema files changed
   - no report renderer changed
   - no API contract changed
   - no Bilibili option builder changed unless explicitly required by test fallout

## Acceptance criteria

- Podcast-Agent no longer attempts non-preferred-language automatic subtitles when a preferred language exists.
- Podcast-Agent still attempts non-preferred-language manual subtitles as fallback.
- `ai-zh` style automatic captions match `zh-Hans` through normalized language matching.
- Subtitle download attempts still respect `max_download_attempts`.
- YouTube base `yt-dlp` options include `remote_components=["ejs:github"]`.
- YouTube subtitle download options include `ignore_no_formats_error=True`.
- YouTube subtitle download options include `sleep_interval_subtitles=30`.
- Subtitle acquisition emits searchable diagnostic logs.
- Audio transcription fallback still works when subtitle acquisition fails and a transcriber is configured.
- Existing transcript artifact paths and JSON schemas remain unchanged.
- Focused subtitle and downloader tests pass.
- Full test suite passes.

## Non-goals

- Do not change report generation.
- Do not change API responses.
- Do not change transcript artifact schemas.
- Do not change evidence, outline, viewpoint, or summary schemas.
- Do not increase default subtitle download attempts.
- Do not add browser cookie extraction in this implementation.
- Do not modify Bilibili subtitle acquisition unless a separate Bilibili decision requires it.
- Do not add network-dependent tests.

