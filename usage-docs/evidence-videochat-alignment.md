# Evidence Extraction Alignment With videochat

## Problem Observed

The workflow output at `output/workflow/insights/evidence.json` only contained 8 evidence segments, ending at `00:07:46.319`, even though the source subtitle file `output/workflow/elements/transcript.vtt` runs until `01:17:08.199`.

This made the artifact look as if evidence extraction only processed the first 10 minutes of the video.

## Local Findings

The subtitle source is complete:

- `transcript.vtt` contains 2,244 subtitle segments.
- The first subtitle starts at `00:00:00.480`.
- The last subtitle ends at `01:17:08.199`.
- `metadata.json` contains 21 chapters covering the full video.

The extraction code also builds chunks across the full subtitle timeline:

- It first tries `chunk_subtitle_segments_by_chapters(...)`.
- If chapters are unavailable, it falls back to 600 second chunks with 30 second overlap.

The truncation happened after all chunk candidates were merged:

```python
final_segments = reindex_segments(normalize_segments(chunk_candidates))
if active_config.max_final_segments > 0:
    final_segments = final_segments[: active_config.max_final_segments]
    final_segments = reindex_segments(final_segments)
```

Before this fix, `EvidenceConfig.max_final_segments` defaulted to `8`, so the standard workflow artifact kept only the first 8 normalized segments in chronological order. For broad questions such as `总结这个视频`, early chapters can easily produce 8 relevant candidates, causing later video sections to be dropped from `evidence.json`.

## videochat Reference Behavior

The reference implementation is under:

`/share/project/chenchen/code/videochat/.worktrees/workflow-v2/src/workflow/evidence`

Relevant behavior:

- `chunking.py` uses chapters first and time windows as fallback.
- `extraction.py` runs model extraction per chunk, often concurrently.
- `hydration.py` hydrates returned `start` and `end` timestamps from the original subtitles.
- Standard artifact extraction uses `truncate_final_segments=None`.

In `videochat`:

```python
def _request_from_artifact_contract(request: EvidenceExtractionInput) -> _EvidenceExtractionRequest:
    return _EvidenceExtractionRequest(
        ...
        truncate_final_segments=None,
        ...
    )
```

The final truncation branch only runs when an explicit positive value is provided:

```python
if request.truncate_final_segments and request.truncate_final_segments > 0:
    normalized_final_segments = normalized_final_segments[: request.truncate_final_segments]
```

The `videochat` workflow README also states that the standard evidence artifact writes all merged, deduplicated, sorted evidence segments and does not truncate by `max_final_segments`.

## Podcast-Agent Fix

Podcast-Agent now follows the same standard-artifact behavior:

- `EvidenceConfig.max_final_segments` defaults to `0`.
- `0` keeps the existing meaning of "do not truncate".
- Explicit positive values still work for callers that need a bounded search result.

This keeps standard `insights/evidence.json` broad enough for later outline and viewpoint planning, while preserving the existing truncation option for narrower workflows such as follow-up evidence search.

## Why This Matters

The evidence artifact is the factual basis for downstream outline, viewpoint, summary, and report generation. If it is chronologically truncated at the extraction stage, downstream stages cannot recover later topics, even when the subtitle file and chunk extraction covered the full video.
