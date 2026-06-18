"""Viewpoint detail prompts copied from videochat."""

from __future__ import annotations

import json
from typing import Any

from podcast_agent.insights.evidence_prompts import JSON_OBJECT_OUTPUT_RULES
from podcast_agent.insights.outline_prompts import ReportIntent, report_language_name


VIEWPOINT_DETAIL_V1_HEADER = (
    "You are a senior feature editor writing an evidence-based report from a video podcast. "
    "Your task is to develop the selected outline viewpoint into structured sub-theses with concise explanations and verbatim subtitle quote evidence."
)


VIEWPOINT_DETAIL_V1_INPUTS = [
    "The user's original question.",
    "The target report language, which controls all user-facing generated sub-thesis titles, explanations, and reader-facing quote text.",
    "The video title.",
    "The video description.",
    "The video source URL, provided as source metadata for the renderer.",
    "One selected viewpoint from the outline, including its id, title, summary, and evidence segment indexes.",
    "The selected evidence segments for that viewpoint, including segment start/end times and subtitle lines.",
]


VIEWPOINT_DETAIL_V1_INPUT_USAGE_RULES = [
    "Use the user's original question as the lens for deciding which supporting ideas under the selected viewpoint matter most.",
    "Use the video title and description to identify the video's topic, guest/interviewee names, organizations, and contextual scope when this helps write accurate explanations in the target report language.",
    "When the title or description clearly identifies the speaker, guest, or interviewee relevant to a sub-thesis, use the accurate person name instead of generic labels such as the interviewee, the guest, or the speaker; do not assign a name to a claim unless the selected subtitles make the speaker-claim relationship clear.",
    "Do not use the title or description as evidence for claims; claims must be grounded in the selected evidence segments and subtitles.",
    "Do not construct Markdown timestamp links; the renderer will create links from start times.",
    "Use the selected viewpoint as the fixed parent argument; do not replace, broaden, or redirect it.",
    "Use the selected viewpoint title and summary to understand the intended argument scope.",
    "Use the selected viewpoint evidence_segment_indexes to know which evidence segments may support this viewpoint.",
    "Use selected evidence segments and subtitle lines as the only factual grounding for sub-theses, explanations, quotes, and start/end times.",
    "Use exact text spans from subtitle lines when creating quote evidence; you may extract the relevant speaker sentence from inside a subtitle line or assemble one complete sentence from adjacent subtitle lines.",
]


VIEWPOINT_DETAIL_V1_OUTPUT_SHAPE_RULES = [
    "Develop the selected viewpoint into several report-ready sub-theses.",
    "Each sub-thesis must include a clear judgment title in the target report language, one concise explanation paragraph in the target report language, and supporting subtitle quotes.",
    "The explanation should explain what the evidence shows, why it matters, and how it supports the selected viewpoint.",
    "Each sub-thesis must include segment_start so the renderer can create the thesis-level timestamp link.",
    "Each subtitle quote must include subtitle_start and subtitle_end so the renderer can create the exact quote timestamp link.",
]


VIEWPOINT_DETAIL_V1_WRITING_METHOD_RULES = [
    "Start from the selected viewpoint, then use the selected evidence segments to identify the strongest supporting ideas.",
    "Group related subtitle evidence into 1-3 higher-level sub-theses.",
    "While developing each sub-thesis, also identify its supporting evidence segment.",
]


VIEWPOINT_DETAIL_V1_INTENT_RULES = [
    "Treat the target report language as a hard constraint for sub-thesis titles and explanations.",
    "The quote text field is reader-facing and MUST always be written in the target report language.",
    "When source_text is not in the target report language, translate it faithfully into the target report language in text.",
    "Never copy non-target-language subtitle text into text; non-target-language original wording belongs only in source_text.",
    "source_text MUST preserve the verbatim original subtitle evidence and MUST NOT be translated, polished, normalized, or rewritten.",
    "Do not use the question language, subtitle language, or video language as the generated explanation language when they conflict with the target report language.",
    "If the subtitle text is already in the target report language, text may be identical to source_text.",
    "Do not change the meaning of source_text when writing text in the target report language.",
]


VIEWPOINT_DETAIL_V1_QUOTE_RULES = [
    "Choose quote evidence while developing each sub-thesis, not after the argument is already written.",
    "Use enough non-redundant quotes to support each sub-thesis, but do not force weak quotes.",
    "Use 1-2 quotes per sub-thesis by default, at most 3 when the evidence is genuinely distinct, and never more than 4.",
    "Prefer concise, high-signal quote snippets over long transcript blocks.",
    "Prefer self-contained subtitle quotes that can be understood by report readers without additional transcript context.",
    "If adjacent candidate quotes express the same idea, keep only the more complete and self-contained quote.",
    "A quote may be an exact span assembled from adjacent subtitle lines when one complete speaker sentence is split across lines.",
    "If a subtitle line contains both a host question and the guest answer, quote only the exact guest sentence that supports the sub-thesis.",
    "If a strong quote depends on unclear pronouns or missing context, quote 2-3 consecutive subtitle sentences that make the reference clear.",
    "Write text as a faithful target-language translation or rendering of source_text for report readers.",
    "If source_text is in English and the target report language is Chinese, text MUST be Chinese.",
    "If source_text is in Chinese and the target report language is English, text MUST be English.",
    "Do not leave text in the subtitle/source language when it differs from the target report language.",
    "Copy source_text exactly from the selected subtitle text span, preserving the original wording and order.",
    "Do not rewrite, complete, polish, translate, normalize, or paraphrase source_text. If the original subtitle cannot be quoted clearly, choose a different quote.",
    "If text translates source_text, keep the translation faithful and do not add claims or emphasis absent from source_text.",
    "Do not quote host questions, prompts, or setup unless the host wording itself is necessary evidence.",
    "Avoid greetings, filler, repetition, and low-information lines unless they are necessary evidence.",
]


VIEWPOINT_DETAIL_V1_TIMESTAMP_RULES = [
    "Do not output Markdown timestamp links.",
    "For each sub-thesis, set segment_start to the earliest supporting evidence segment start time.",
    "For each quote, use the exact subtitle line start/end time where the quoted text appears.",
    "For quotes assembled from adjacent subtitle lines, subtitle_start must be the start time of the first subtitle line used and subtitle_end must be the end time of the last subtitle line used.",
    "For quotes extracted from part of one subtitle line, use that subtitle line's start and end time.",
    "The segment_start field must match the supporting evidence segment start time.",
    "The subtitle_start and subtitle_end fields must match the original subtitle line span used for the quote.",
]


VIEWPOINT_DETAIL_V1_BOUNDARY_RULES = [
    "Use only the selected viewpoint and selected evidence segments as factual grounding.",
    "Do not replace the selected viewpoint with a different argument.",
    "Do not invent facts, names, numbers, examples, or claims not supported by the selected evidence.",
    "Do not quote subtitle text that does not directly support the sub-thesis.",
    "Do not create sub-theses that are only loosely related to the selected viewpoint.",
]


VIEWPOINT_DETAIL_V1_OUTPUT_RULES = [
    *JSON_OBJECT_OUTPUT_RULES,
    "Follow the schema exactly.",
    "Do not add extra top-level keys.",
]


VIEWPOINT_DETAIL_V1_SCHEMA = {
    "sub_theses": [
        {
            "id": "V1-S1",
            "title": "<clear sub-thesis judgment in the target report language>",
            "explanation": "<1-3 sentences in the target report language explaining the sub-thesis reasoning and implication>",
            "segment_start": "00:01:35,000",
            "supporting_evidence_segment_indexes": [1, 12],
            "quotes": [
                {
                    "text": "<faithful reader-facing translation/rendering in the target report language, never non-target-language source wording>",
                    "source_text": "<verbatim original subtitle text used as evidence, unchanged and untranslated>",
                    "subtitle_start": "00:02:13,000",
                    "subtitle_end": "00:02:16,000",
                }
            ],
        }
    ]
}


def viewpoint_intent_payload(report_intent: ReportIntent | None) -> dict[str, str]:
    active_intent = report_intent or ReportIntent()
    return {
        "target_language": active_intent.report_language,
        "target_language_name": report_language_name(active_intent.report_language),
    }


def _viewpoint_intent_requirement_lines(report_intent: ReportIntent | None) -> list[str]:
    payload = viewpoint_intent_payload(report_intent)
    return [
        f"Target report language: {payload['target_language_name']}.",
        *VIEWPOINT_DETAIL_V1_INTENT_RULES,
    ]


def build_viewpoint_detail_v1_prompt(
    *,
    question: str,
    video_title: str | None = None,
    video_description: str | None = None,
    outline: dict[str, Any],
    evidence: dict[str, Any] | list[Any],
    viewpoint_id: str,
    source_url: str | None = None,
    report_intent: ReportIntent | None = None,
) -> str:
    viewpoint = find_viewpoint(outline, viewpoint_id)
    selected_segments = select_segments_for_viewpoint(
        evidence=evidence,
        viewpoint=viewpoint,
    )

    return "\n".join(
        [
            VIEWPOINT_DETAIL_V1_HEADER,
            "",
            "## Input You Will Receive",
            "",
            *[f"- {item}" for item in VIEWPOINT_DETAIL_V1_INPUTS],
            "",
            "## How To Write",
            "",
            "### Report Intent Requirements",
            *[f"- {rule}" for rule in _viewpoint_intent_requirement_lines(report_intent)],
            "",
            "### How To Use The Inputs",
            *[f"- {rule}" for rule in VIEWPOINT_DETAIL_V1_INPUT_USAGE_RULES],
            "",
            "### What To Produce",
            *[f"- {rule}" for rule in VIEWPOINT_DETAIL_V1_OUTPUT_SHAPE_RULES],
            "",
            "### How To Produce It",
            *[f"- {rule}" for rule in VIEWPOINT_DETAIL_V1_WRITING_METHOD_RULES],
            "",
            "### Quote Evidence Rules",
            *[f"- {rule}" for rule in VIEWPOINT_DETAIL_V1_QUOTE_RULES],
            "",
            "### Timestamp Rules",
            *[f"- {rule}" for rule in VIEWPOINT_DETAIL_V1_TIMESTAMP_RULES],
            "",
            "### Boundaries",
            *[f"- {rule}" for rule in VIEWPOINT_DETAIL_V1_BOUNDARY_RULES],
            "",
            "## Output Requirements",
            "",
            *[f"- {rule}" for rule in VIEWPOINT_DETAIL_V1_OUTPUT_RULES],
            "",
            "## Required JSON Schema",
            "",
            json.dumps(VIEWPOINT_DETAIL_V1_SCHEMA, ensure_ascii=False, indent=2),
            "",
            "---",
            "",
            "Question:",
            question,
            "",
            "Report Intent:",
            json.dumps(viewpoint_intent_payload(report_intent), ensure_ascii=False, indent=2),
            "",
            "Video Title:",
            video_title.strip() if video_title and video_title.strip() else "(not provided)",
            "",
            "Video Description:",
            video_description.strip() if video_description and video_description.strip() else "(not provided)",
            "",
            "Video Source URL:",
            source_url.strip() if source_url and source_url.strip() else "(not provided)",
            "",
            "Selected Viewpoint From Outline:",
            json.dumps(viewpoint, ensure_ascii=False, indent=2),
            "",
            "Selected Evidence Segments With Subtitles:",
            json.dumps(selected_segments, ensure_ascii=False, indent=2),
            "",
            "Return the viewpoint detail JSON now:",
        ]
    )


def get_viewpoints_from_outline(outline: dict[str, Any]) -> list[dict[str, Any]]:
    viewpoints = outline.get("viewpoint_breakdown", [])
    return viewpoints if isinstance(viewpoints, list) else []


def find_viewpoint(outline: dict[str, Any], viewpoint_id: str) -> dict[str, Any]:
    for viewpoint in get_viewpoints_from_outline(outline):
        if str(viewpoint.get("id")) == str(viewpoint_id):
            return viewpoint
    raise ValueError(f"Viewpoint id not found in outline: {viewpoint_id}")


def get_segments_from_evidence(evidence: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(evidence, dict) and isinstance(evidence.get("segments"), list):
        return evidence["segments"]
    if isinstance(evidence, list):
        return evidence
    return []


def compact_subtitles(subtitles: list[Any]) -> list[str]:
    compact: list[str] = []
    for item in subtitles:
        if not isinstance(item, dict):
            continue
        start = str(item.get("start", "")).strip()
        end = str(item.get("end", "")).strip()
        text = str(item.get("text", "")).strip()
        if not start or not end or not text:
            continue
        compact.append(f"{start} --> {end} {text}")
    return compact


def select_segments_for_viewpoint(
    *,
    evidence: dict[str, Any] | list[Any],
    viewpoint: dict[str, Any],
) -> list[dict[str, Any]]:
    segments = get_segments_from_evidence(evidence)
    indexes = viewpoint.get("evidence_segment_indexes", [])
    if not isinstance(indexes, list):
        indexes = []
    wanted = {str(index) for index in indexes}
    selected: list[dict[str, Any]] = []
    for position, segment in enumerate(segments):
        if not isinstance(segment, dict):
            continue
        explicit_index = segment.get("index", position)
        if str(explicit_index) not in wanted and str(position) not in wanted:
            continue
        selected.append(
            {
                "segment_start": segment.get("start"),
                "segment_end": segment.get("end"),
                "subtitle_lines": compact_subtitles(
                    segment.get("subtitles", []) if isinstance(segment.get("subtitles"), list) else []
                ),
            }
        )
    return selected
