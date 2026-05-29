"""Outline planning prompts copied from videochat."""

from __future__ import annotations

import json
from typing import Any

from podcast_agent.insights.evidence_prompts import JSON_OBJECT_OUTPUT_RULES
from podcast_agent.intent import ReportIntent, normalize_report_length, report_language_name, report_length_profile


REPORT_OUTLINE_V1_HEADER = (
    "You are a senior feature editor planning an evidence-based report from video evidence. "
    "Your task is to extract the strongest major viewpoints from the provided evidence segments for later detail expansion."
)


REPORT_OUTLINE_V1_INPUTS = [
    "The user's original question.",
    "The target report language, which controls all user-facing generated outline fields.",
    "The target report length, which controls how many major viewpoints to plan and how selective the outline should be.",
    "The video source URL, included only as source metadata.",
    "The video title, used only as source context.",
    "The video description, used only as source context.",
    "The video chapters, used only to understand the video's broad topic structure.",
    "Evidence segments: representative text excerpts previously extracted from subtitle chunks, including segment indexes, timestamps, and text.",
]


REPORT_OUTLINE_V1_INPUT_USAGE_RULES = [
    "Use the user's original question as the primary lens for deciding which themes, tensions, and implications matter most.",
    "Use the video description to understand the video's stated topic, guest/context, and intended scope, but do not treat it as evidence for claims.",
    "Use video chapters to understand the broad structure of the video, major topic shifts, and where different themes appear in the timeline.",
    "Use chapters to avoid over-focusing on one section of the video when later sections introduce materially different themes.",
    "Do not convert chapter titles directly into viewpoints; viewpoints must be grounded in evidence segment text.",
    "Use evidence segments as the only factual basis for viewpoint titles, summaries, and evidence_segment_indexes.",
    "Use source URL only as source metadata; do not derive viewpoints from the URL.",
]


REPORT_OUTLINE_V1_OUTPUT_SHAPE_RULES = [
    "Produce a list of major viewpoints that will serve as the planning structure for later detail expansion.",
    "Each viewpoint must include an id, a judgment title in the target report language, a concise summary in the target report language, an importance score, an importance reason in the target report language, and supporting evidence segment indexes.",
]

REPORT_OUTLINE_V1_INTENT_RULES = [
    "Treat the target report language as a hard constraint for title, summary, and importance_reason.",
    "Do not use the question language, subtitle language, or video language as the output language when they conflict with the target report language.",
    "Treat the target report length as a planning constraint, not as a request to write the final report body.",
    "For brief reports, select only the strongest high-level viewpoints and avoid marginal or overlapping viewpoints.",
    "For default reports, select the strongest distinct viewpoints without trying to cover every minor topic.",
    "For detailed reports, include more distinct high-value viewpoints when the evidence supports them, but do not pad weak viewpoints.",
]

REPORT_OUTLINE_V1_VIEWPOINT_DEVELOPMENT_RULES = [
    "Use the user's question as the lens for deciding which evidence matters most.",
    "Scan the full evidence set before selecting viewpoints.",
    "Build viewpoints by clustering evidence segments that support the same higher-level argument.",
    "Evidence segments may be clustered even when they appear in different or non-adjacent parts of the video.",
    "Cluster segments when they express the same judgment, build the same causal chain, repeat the same tension, or when one segment clarifies, deepens, challenges, or gives an example of another.",
    "Do not cluster segments merely because they share a broad topic; the cluster must support one coherent argument.",
    "Turn each strong evidence cluster into one major viewpoint.",
    "Record all evidence segment indexes in each viewpoint's evidence cluster.",
    "Every viewpoint must express a directional judgment, not a neutral topic label.",
    "A valid viewpoint should answer: so what, why does this matter, what is changing, or what does this imply.",
    "Avoid generic statements; make every viewpoint specific to the provided evidence.",
    "Reasonable implications are allowed only when clearly derived from the evidence.",
    "When names appear in evidence and matter to the argument, use real names instead of generic labels.",
    "Write viewpoint titles in short, declarative phrasing in the target report language.",
]


REPORT_OUTLINE_V1_IMPORTANCE_RULES = [
    "Assign each viewpoint an integer importance_score from 1 to 5.",
    "Use 5 for a core report argument that should almost certainly receive full detail expansion.",
    "Use 4 for a strong argument that is worth expanding.",
    "Use 3 for a useful argument that may be shortened, merged, or used as supporting context.",
    "Use 2 for a marginal or mostly background argument that usually should not receive full expansion.",
    "Use 1 for a weak, repetitive, or briefly mentioned argument that should usually be discarded.",
    "Score higher when the viewpoint is strongly supported, directly relevant to the user's question, and rich enough for later sub-thesis expansion.",
    "Score lower when the viewpoint is weakly supported, mostly background, repetitive, or too narrow to support later expansion.",
    "Write importance_reason as one concise sentence in the target report language explaining the score.",
]


REPORT_OUTLINE_V1_BOUNDARY_RULES = [
    "Use only the provided evidence segments as factual grounding.",
    "Do not invent facts, names, numbers, examples, or claims not supported by evidence.",
    "Do not write sub-theses, subtitle quotes, detailed explanations, core conclusions, takeaways, or the final report body.",
    "Do not produce a transcript-style summary.",
    "Do not make the outline a chronological summary of the video; organize viewpoints by coherent arguments instead.",
]


REPORT_OUTLINE_V1_OUTPUT_RULES = [
    *JSON_OBJECT_OUTPUT_RULES,
    "Follow the schema exactly.",
    "Do not add extra top-level keys.",
]


REPORT_OUTLINE_V1_SCHEMA = {
    "viewpoint_breakdown": [
        {
            "id": "V1",
            "title": "<sharp judgment in the target report language, not a neutral topic label>",
            "summary": "<1-2 sentences in the target report language explaining the viewpoint's reasoning and implication, without sub-theses or quotes>",
            "importance_score": 5,
            "importance_reason": "<one concise sentence in the target report language explaining why this viewpoint is or is not worth later expansion>",
            "evidence_segment_indexes": [3, 17, 42],
        }
    ]
}


def outline_intent_payload(report_intent: ReportIntent | None) -> dict[str, str]:
    active_intent = report_intent or ReportIntent()
    length = normalize_report_length(active_intent.report_length)
    profile = report_length_profile(length)
    return {
        "target_language": active_intent.report_language,
        "target_language_name": report_language_name(active_intent.report_language),
        "target_length": length,
        "target_outline_viewpoints": profile.outline_viewpoints,
    }


def _outline_intent_requirement_lines(report_intent: ReportIntent | None) -> list[str]:
    payload = outline_intent_payload(report_intent)
    return [
        f"Target report language: {payload['target_language_name']}.",
        f"Target report length: {payload['target_length']}.",
        f"Target outline size: {payload['target_outline_viewpoints']} major viewpoints.",
        *REPORT_OUTLINE_V1_INTENT_RULES,
    ]


def sanitize_outline_evidence(evidence: dict[str, Any] | list[Any]) -> list[dict[str, Any]]:
    if isinstance(evidence, dict):
        raw_segments = evidence.get("segments", [])
    elif isinstance(evidence, list):
        raw_segments = evidence
    else:
        raw_segments = []

    sanitized: list[dict[str, Any]] = []
    for item in raw_segments:
        if not isinstance(item, dict):
            continue
        segment: dict[str, Any] = {}
        for key in ("index", "start", "end", "text"):
            if key in item:
                segment[key] = item[key]
        if segment:
            sanitized.append(segment)
    return sanitized


def build_report_outline_v1_prompt(
    *,
    question: str,
    evidence: dict[str, Any] | list[Any],
    source_url: str | None = None,
    video_title: str | None = None,
    video_description: str | None = None,
    chapters: list[Any] | None = None,
    report_intent: ReportIntent | None = None,
) -> str:
    """Build prompt for a JSON outline used to assemble a later full report."""
    return "\n".join(
        [
            REPORT_OUTLINE_V1_HEADER,
            "",
            "## Input You Will Receive",
            "",
            *[f"- {item}" for item in REPORT_OUTLINE_V1_INPUTS],
            "",
            "## How To Build The Outline",
            "",
            "### Report Intent Requirements",
            *[f"- {rule}" for rule in _outline_intent_requirement_lines(report_intent)],
            "",
            "### How To Use The Inputs",
            *[f"- {rule}" for rule in REPORT_OUTLINE_V1_INPUT_USAGE_RULES],
            "",
            "### What To Produce",
            *[f"- {rule}" for rule in REPORT_OUTLINE_V1_OUTPUT_SHAPE_RULES],
            "",
            "### How To Produce It",
            *[f"- {rule}" for rule in REPORT_OUTLINE_V1_VIEWPOINT_DEVELOPMENT_RULES],
            "",
            "### Importance Scoring",
            *[f"- {rule}" for rule in REPORT_OUTLINE_V1_IMPORTANCE_RULES],
            "",
            "### Boundaries",
            *[f"- {rule}" for rule in REPORT_OUTLINE_V1_BOUNDARY_RULES],
            "",
            "## Output Requirements",
            "",
            *[f"- {rule}" for rule in REPORT_OUTLINE_V1_OUTPUT_RULES],
            "",
            "## Required JSON Schema",
            "",
            json.dumps(REPORT_OUTLINE_V1_SCHEMA, ensure_ascii=False, indent=2),
            "",
            "---",
            "",
            "Question:",
            question,
            "",
            "Report Intent:",
            json.dumps(outline_intent_payload(report_intent), ensure_ascii=False, indent=2),
            "",
            "Video Source URL:",
            source_url.strip() if source_url and source_url.strip() else "(not provided)",
            "",
            "Video Title:",
            video_title.strip() if video_title and video_title.strip() else "(not provided)",
            "",
            "Video Description:",
            video_description.strip() if video_description and video_description.strip() else "(not provided)",
            "",
            "Video Chapters:",
            json.dumps(chapters if isinstance(chapters, list) else [], ensure_ascii=False, indent=2),
            "",
            "Evidence Segments:",
            json.dumps(sanitize_outline_evidence(evidence), ensure_ascii=False, indent=2),
            "",
            "Return the JSON outline now:",
        ]
    )
