# Viewpoint detail empty response retry implementation plan

## Source summary

This plan implements:

- [Viewpoint detail 空响应导致任务失败问题总结](../error-summary/2026-06-19-viewpoint-detail-empty-response.md)

The goal is to reduce task failures caused by transient invalid model output during viewpoint detail generation, especially empty responses such as:

```text
Viewpoint generation failed: model returned empty content for V3.
```

## Minimum implementation

Required behavior:

1. Keep existing viewpoint artifact schemas unchanged.
2. Keep existing prompt body unchanged for the first attempt.
3. Retry viewpoint detail generation up to `3` attempts.
4. Classify invalid model responses before retrying.
5. Treat empty response as `empty_response`.
6. Treat unparsable response as `invalid_json`.
7. Treat JSON values that are not objects as `non_object_json`.
8. Treat object JSON without a `sub_theses` list as `missing_sub_theses`.
9. On retry, append a corrective prompt suffix that asks for exactly one JSON object.
10. Preserve strict failure behavior after retries are exhausted.
11. Add focused tests for retry and exhaustion behavior.

## Module organization

```text
src/podcast_agent/insights/
└── viewpoint.py

tests/
└── test_viewpoint_generation.py
```

No report rendering, outline generation, evidence extraction, summary generation, CLI command parsing, or API modules should change for the minimum implementation.

## Responsibility boundaries

### `insights/viewpoint.py`

Owns:

- Selecting outline viewpoints for detail generation.
- Building one viewpoint detail prompt.
- Calling the model writer.
- Parsing viewpoint detail JSON.
- Merging generated detail with outline metadata.
- Saving `insights/viewpoint_<id>.json`.
- Saving final `insights/viewpoints.json`.

Should add:

- `VIEWPOINT_DETAIL_MAX_ATTEMPTS = 3`
- `VIEWPOINT_DETAIL_RESPONSE_PREVIEW_LIMIT = 200`
- `_classify_viewpoint_detail_failure(content)`
- `_build_viewpoint_retry_prompt(prompt, reason=...)`
- `_truncate_response_preview(content)`

Should update:

- `generate_viewpoint_detail(...)`

Should not change:

- `build_viewpoints_payload(...)`
- `select_viewpoints_for_detail(...)`
- `REPORT_VIEWPOINT_SELECTION_SORT`
- `viewpoint_<id>.json` schema
- `viewpoints.json` schema

### `tests/test_viewpoint_generation.py`

Owns:

- Unit tests for viewpoint selection.
- Unit tests for prompt shape.
- Unit tests for viewpoint detail generation.
- Regression tests for retry behavior.

Should add:

- Empty response retries and succeeds.
- Invalid JSON retries and succeeds.
- Retry exhaustion raises `EvidenceExtractionError` with attempt count and failure reason.

## Implementation sequence

1. Add constants to `src/podcast_agent/insights/viewpoint.py`:

```python
VIEWPOINT_DETAIL_MAX_ATTEMPTS = 3
VIEWPOINT_DETAIL_RESPONSE_PREVIEW_LIMIT = 200
```

2. Add `_classify_viewpoint_detail_failure(content)`:
   - strip response text
   - return `empty_response` if blank
   - try `json.loads(text)`
   - if direct parse fails, try extracting the first `{...}` block with regex
   - return `invalid_json` when no JSON object can be parsed
   - return `non_object_json` when parsed value is not a dict
   - return `None` when parsed value is a dict

3. Add `_build_viewpoint_retry_prompt(prompt, reason=...)`:
   - append a corrective suffix
   - include the previous failure reason
   - require the next response to be exactly one JSON object
   - require response to start with `{` and end with `}`
   - forbid Markdown fences and extra text

4. Add `_truncate_response_preview(content)`:
   - strip content
   - keep at most `VIEWPOINT_DETAIL_RESPONSE_PREVIEW_LIMIT`
   - append `...` when truncated

5. Update `generate_viewpoint_detail(...)`:
   - build the original prompt once
   - loop attempts from `1` to `VIEWPOINT_DETAIL_MAX_ATTEMPTS`
   - first attempt uses the original prompt
   - retry attempts use `_build_viewpoint_retry_prompt(...)`
   - call `model_writer(active_prompt).strip()`
   - classify response
   - if classification is `None`, parse with existing `parse_model_json(...)`
   - accept only when `detail.get("sub_theses")` is a list
   - merge metadata and return on success
   - set reason to `missing_sub_theses` when JSON object lacks the required list
   - after exhaustion, raise `EvidenceExtractionError`

6. Keep strict failure after retry exhaustion:
   - do not omit failed viewpoints
   - do not write partial `viewpoints.json`
   - do not modify final report behavior

7. Add test `test_generate_viewpoint_detail_retries_empty_response`:
   - fake model returns `""` first
   - fake model returns valid `{"sub_theses": []}` second
   - assert second prompt contains `Reason: empty_response.`
   - assert result includes `viewpoint_id`
   - assert exactly two calls

8. Add test `test_generate_viewpoint_detail_retries_invalid_json`:
   - fake model returns non-JSON first
   - fake model returns valid JSON second
   - assert second prompt contains `Reason: invalid_json.`
   - assert exactly two calls

9. Add test `test_generate_viewpoint_detail_raises_after_retry_exhaustion`:
   - fake model always returns `""`
   - assert `EvidenceExtractionError`
   - assert message includes `after 3 attempts`
   - assert message includes `empty_response`
   - assert exactly three calls

10. Run focused tests:

```bash
.venv/bin/python -m pytest tests/test_viewpoint_generation.py
```

11. Run full tests:

```bash
.venv/bin/python -m pytest
```

## Acceptance criteria

- Viewpoint detail generation retries blank model responses.
- Viewpoint detail generation retries invalid JSON responses.
- Viewpoint detail generation retries non-object JSON responses.
- Viewpoint detail generation retries JSON objects missing `sub_theses`.
- Retry prompts include the previous failure reason.
- Retry prompts demand exactly one JSON object.
- Successful retry writes the same detail payload shape as before.
- Retry exhaustion still fails the task clearly.
- No viewpoint artifact schemas change.
- Focused viewpoint tests pass.
- Full test suite passes.

## Non-goals

- Do not skip failed selected viewpoints.
- Do not generate partial reports after selected viewpoint failure.
- Do not change outline generation.
- Do not change evidence extraction.
- Do not change report rendering.
- Do not add provider-specific model retry or transport retry logic here.
- Do not change the first-attempt viewpoint prompt body.
