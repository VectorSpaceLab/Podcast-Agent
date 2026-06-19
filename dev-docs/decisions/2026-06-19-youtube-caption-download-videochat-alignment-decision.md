# YouTube Caption Download VideoChat Alignment Decision

**Date:** 2026-06-19

## Background

Podcast-Agent currently uses `yt-dlp` to acquire YouTube subtitles before falling back to audio transcription. In recent runs, subtitle downloading is not stable enough: some tasks fail during caption acquisition even when VideoChat's workflow-v2 implementation can acquire captions more reliably for similar sources.

The VideoChat reference implementation is:

```text
/share/project/chenchen/code/videochat/.worktrees/workflow-v2/src/source/youtube.py
```

Podcast-Agent's relevant implementation points are:

```text
src/podcast_agent/elements/youtube_transcript.py
src/podcast_agent/elements/transcript_tracks.py
src/podcast_agent/downloaders/yt_dlp.py
```

## Problem

### 1. Automatic caption fallback can try the wrong language

Podcast-Agent ranks manual and automatic caption tracks, then tries the first `max_download_attempts` tracks.

The current ranking can include non-preferred-language automatic captions after preferred-language candidates fail. This is risky because automatic captions in another language are often low-value for the report language and can also trigger unstable `yt-dlp` subtitle download paths.

VideoChat avoids this by filtering caption download candidates:

- keep preferred-language automatic captions
- keep any manual captions
- exclude non-preferred-language automatic captions

This keeps useful manual fallback while avoiding low-value automatic caption attempts.

### 2. YouTube `yt-dlp` base options are missing one VideoChat stability option

Podcast-Agent already uses:

```python
"ignoreconfig": True
"js_runtimes": {"node": {}}
"quiet": True
"no_warnings": True
```

VideoChat also uses:

```python
"remote_components": ["ejs:github"]
```

This option lets `yt-dlp` fetch remote JavaScript interpreter components when YouTube extraction requires them. It should be aligned for YouTube subtitle and metadata extraction.

### 3. Subtitle download options are missing VideoChat tolerance and pacing options

VideoChat subtitle download options include:

```python
"ignore_no_formats_error": True
"sleep_interval_subtitles": 30
```

Podcast-Agent currently does not include these options for YouTube subtitle download.

The difference matters because subtitle-only downloads may encounter videos where media formats are unavailable or irrelevant to the caption path. `ignore_no_formats_error` keeps the subtitle operation focused on captions. `sleep_interval_subtitles` adds pacing between subtitle downloads and reduces pressure on YouTube subtitle endpoints.

### 4. Failure visibility is weaker than VideoChat

VideoChat logs coarse caption acquisition states:

- caption track listing failed
- caption tracks listed
- no acceptable candidates
- candidate list limited by max attempts
- each caption download attempt
- attempt failure with track language/kind and error

Podcast-Agent currently catches subtitle download exceptions and continues, but does not expose the same level of per-attempt diagnostic context.

For unstable subtitle issues, this makes it harder to distinguish:

- no tracks found
- wrong candidates selected
- `yt-dlp` download failure
- downloaded file not found
- unsupported or empty subtitle file

### 5. Browser cookie parity is not currently enabled

VideoChat supports both:

- `cookies_file`
- `cookies_from_browser`

Podcast-Agent currently supports `YOUTUBE_COOKIES_FILE` / `cookies_file`, but does not expose a browser-cookie option for YouTube acquisition.

This is not required for every environment, but it is a real parity gap when YouTube requests need browser session state.

## Decision

Align Podcast-Agent's YouTube subtitle acquisition behavior with VideoChat's stable caption acquisition path, without changing any transcript artifact schema, report schema, API response schema, or downstream data format.

## Required Alignments

### 1. Add VideoChat-compatible caption download candidate filtering

Add a candidate filtering step after ranking tracks and before applying `max_download_attempts`.

Rules:

1. If there is no preferred language, keep all ranked tracks.
2. If a preferred language exists, keep tracks where:
   - the track language matches the preferred language by normalized two-letter prefix, or
   - the track is not automatic.
3. Exclude non-preferred-language automatic tracks.

Expected behavior:

```text
preferred_language = "zh-Hans"

manual en      -> keep
manual ja      -> keep
automatic zh   -> keep
automatic ai-zh -> keep
automatic en   -> exclude
automatic ja   -> exclude
```

This matches VideoChat's practical strategy: automatic captions are only acceptable when they match the target language, while manual captions remain useful fallback candidates.

### 2. Keep the existing rank order

Keep the current rank semantics because they already match VideoChat's intent:

1. preferred-language manual
2. preferred-language automatic
3. other manual
4. other automatic

The new filtering step changes which ranked candidates are downloadable, not the ranking contract itself.

### 3. Add `remote_components` to YouTube base `yt-dlp` options

Add:

```python
"remote_components": ["ejs:github"]
```

to YouTube base options in:

```text
src/podcast_agent/downloaders/yt_dlp.py
```

This should apply to YouTube metadata, subtitle, and audio operations through `build_base_yt_dlp_options()`.

### 4. Add subtitle download tolerance and pacing options

Add the following to YouTube subtitle download options:

```python
"ignore_no_formats_error": True
"sleep_interval_subtitles": 30
```

Primary target:

```text
build_subtitle_download_yt_dlp_options()
```

Bilibili subtitle options should not be changed as part of this decision unless a separate Bilibili-specific failure proves the same options are needed there.

### 5. Add VideoChat-style caption acquisition logging

Add diagnostic logging around subtitle acquisition in:

```text
src/podcast_agent/elements/youtube_transcript.py
```

The log events should include at least:

- subtitle track listing success with track count and preferred language
- no subtitles available
- no acceptable candidates after filtering
- candidate list limited by max attempts
- each download attempt with attempt number, language, and track kind
- each failed attempt with language, track kind, and error
- final failure after all attempts

This logging should use the existing project logging style and must not change returned exceptions or public data contracts.

### 6. Keep audio transcription fallback unchanged

If subtitle listing or all accepted subtitle candidates fail, the current flow should still fall back to audio transcription when a transcriber is configured.

This decision only changes subtitle candidate selection, `yt-dlp` options, and diagnostics.

### 7. Treat browser-cookie support as an explicit follow-up

Podcast-Agent should evaluate reintroducing a YouTube browser-cookie configuration only if full VideoChat runtime parity is required in deployment.

Recommended follow-up shape:

```text
YOUTUBE_COOKIES_FROM_BROWSER=chrome
```

or a structured value accepted by `yt-dlp`'s `cookiesfrombrowser` option.

This is intentionally not part of the minimal first implementation because:

- `.env` was recently cleaned to remove unused settings.
- Browser cookie extraction can be environment-specific.
- `cookies_file` already exists and is enough for many server deployments.

## Implementation Notes

### `transcript_tracks.py`

Add a helper equivalent to VideoChat's `caption_download_candidates()`:

```python
def transcript_download_candidates(
    tracks: list[TranscriptTrack],
    preference: TranscriptLanguagePreference | None = None,
) -> list[TranscriptTrack]:
    ...
```

The helper should reuse the existing normalized language matching logic so `ai-zh` can match `zh-Hans`.

### `youtube_transcript.py`

Use the helper after `rank_transcript_tracks()`:

```python
ranked_tracks = rank_transcript_tracks(...)
candidate_tracks = transcript_download_candidates(ranked_tracks, self.language_preference)
for track in candidate_tracks[: self.language_preference.max_download_attempts]:
    ...
```

Add logging around listing, filtering, limiting, attempts, and failures.

### `yt_dlp.py`

Update:

```text
build_base_yt_dlp_options()
build_subtitle_download_yt_dlp_options()
```

Do not change output paths, file names, requested subtitle parsing, transcript normalization, or generated artifact shapes.

## Test Plan

Add focused tests for:

1. Candidate filtering keeps preferred-language automatic captions.
2. Candidate filtering excludes non-preferred-language automatic captions.
3. Candidate filtering keeps non-preferred-language manual captions.
4. Candidate filtering keeps all ranked tracks when no preferred language exists.
5. YouTube base `yt-dlp` options include `remote_components`.
6. YouTube subtitle download options include `ignore_no_formats_error`.
7. YouTube subtitle download options include `sleep_interval_subtitles`.
8. Transcript fetch attempts only filtered candidates and still respects `max_download_attempts`.

Run focused tests:

```bash
.venv/bin/python -m pytest \
  tests/test_transcript_tracks.py \
  tests/test_youtube_transcript_fetch.py \
  tests/test_downloaders_yt_dlp.py
```

Then run the full suite:

```bash
.venv/bin/python -m pytest
```

## Expected Effects

- YouTube subtitle downloads should avoid unstable non-target-language automatic caption attempts.
- Manual captions in other languages remain available as fallback.
- `yt-dlp` has the same YouTube remote JavaScript component support as VideoChat.
- Subtitle-only download becomes more tolerant when full media formats are unavailable.
- Subtitle download attempts become easier to diagnose from logs.
- Existing output artifacts and data formats remain unchanged.

## Non-goals

- Do not change `TranscriptInfo`, `AudioInfo`, evidence, outline, viewpoint, summary, report, or API schemas.
- Do not change report language behavior.
- Do not change transcript VTT normalization.
- Do not change audio transcription provider behavior.
- Do not change Bilibili subtitle acquisition in this decision.
- Do not make browser-cookie extraction mandatory.
- Do not increase default caption download attempts beyond the current value of 3.

## Relationship to VideoChat

This decision mirrors VideoChat workflow-v2's YouTube caption acquisition behavior and adapts it to Podcast-Agent's module boundaries:

- VideoChat `CaptionTrack` maps to Podcast-Agent `TranscriptTrack`.
- VideoChat `rank_caption_tracks()` maps to Podcast-Agent `rank_transcript_tracks()`.
- VideoChat `caption_download_candidates()` should be mirrored as a Podcast-Agent transcript candidate helper.
- VideoChat YouTube `yt-dlp` option differences should be applied in Podcast-Agent's shared YouTube downloader builder.

