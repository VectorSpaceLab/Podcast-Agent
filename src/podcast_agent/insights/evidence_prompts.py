"""Evidence extraction prompts copied from videochat."""

from __future__ import annotations

import json


JSON_OBJECT_OUTPUT_RULES = [
    "Output exactly one JSON object.",
    "The first non-whitespace character must be {.",
    "The last non-whitespace character must be }.",
    "Use valid JSON with double quotes for all keys and string values.",
    "Never place raw ASCII double quotes (\") inside JSON string values in any language.",
    "If quotation marks are needed inside string values, use language-appropriate curly quotation marks such as “...”, 「...」, «...», or escape ASCII quotes as \\\".",
    "Do not include Markdown fences, comments, trailing commas, or any explanatory text.",
    "Do not output any explanation before or after the JSON.",
]


EVIDENCE_CHUNK_V1_HEADER = (
    "You are an evidence extraction editor reviewing one subtitle chunk from a video podcast. "
    "Your task is to select the subtitle spans in this chunk that are most useful for answering the user's question."
)


EVIDENCE_CHUNK_V1_INPUTS = [
    "The user's original question.",
    "The video outline or chapter context for this chunk.",
    "One subtitle chunk from the video, including subtitle timestamps and text.",
]


EVIDENCE_CHUNK_V1_OUTPUT_SHAPE_RULES = [
    "Produce a list of evidence segments selected from this subtitle chunk.",
    "Each evidence segment is a continuous subtitle span that is useful for answering the user's question.",
    "Return only the start and end timestamp for each selected segment.",
    "Do not assign segment ids or indexes; global indexes will be assigned later after all chunks are merged.",
    "If this chunk does not contain useful evidence for the question, return an empty segments array.",
    "Each start and end timestamp must exactly match an existing subtitle timestamp in this chunk.",
]


EVIDENCE_SEGMENT_DEFINITION = (
    "An evidence segment is a continuous span of subtitle lines in the current chunk that contains one complete, "
    "high-signal idea relevant to the user's question. It may be a claim, explanation, example, cause-effect chain, "
    "tension, objection, prediction, decision rationale, or a complete Q&A exchange. Choose spans that are "
    "self-contained enough for later models to understand without reading the entire chunk. The segment should be "
    "long enough to preserve the idea's context, but not so long that it includes unrelated topics."
)


EVIDENCE_SELECTION_RULES = [
    "Select segments that contain substantive claims, reasoning, examples, tensions, tradeoffs, decisions, predictions, or explanations relevant to the user's question.",
    "Prefer complete, self-contained idea units over isolated punchlines or fragmented adjacent clips.",
    "Keep enough context for later models to understand the idea, but avoid including unrelated setup, digressions, or topic changes.",
    "Do not select greetings, intro music, sponsorship reads, housekeeping, or other low-information material.",
    "Do not select every relevant-looking line; keep only high-signal segments that could support later viewpoint clustering.",
    "If several adjacent subtitle lines form one coherent idea, merge them into one evidence segment.",
    "If the speaker clearly moves to a new idea or subtopic, start a separate evidence segment.",
    "Return selected segments in chronological order.",
]


EVIDENCE_CHUNK_V1_OUTPUT_RULES = [
    *JSON_OBJECT_OUTPUT_RULES,
    "Follow the schema exactly.",
    "Do not add extra top-level keys.",
]


EVIDENCE_CHUNK_V1_SCHEMA = {
    "segments": [
        {
            "start": "HH:MM:SS,mmm",
            "end": "HH:MM:SS,mmm",
        }
    ]
}


def build_evidence_chunk_prompt(
    *,
    question: str,
    chunk_text: str,
    outline_text: str,
) -> str:
    return "\n".join(
        [
            EVIDENCE_CHUNK_V1_HEADER,
            "",
            "## Input You Will Receive",
            "",
            *[f"- {item}" for item in EVIDENCE_CHUNK_V1_INPUTS],
            "",
            "## What To Produce",
            "",
            *[f"- {rule}" for rule in EVIDENCE_CHUNK_V1_OUTPUT_SHAPE_RULES],
            "",
            "## How To Select Evidence Segments",
            "",
            "### Evidence Segment Definition",
            "",
            EVIDENCE_SEGMENT_DEFINITION,
            "",
            "### Selection Rules",
            "",
            *[f"- {rule}" for rule in EVIDENCE_SELECTION_RULES],
            "",
            "## Output Requirements",
            "",
            *[f"- {rule}" for rule in EVIDENCE_CHUNK_V1_OUTPUT_RULES],
            "",
            "## Required JSON Schema",
            "",
            json.dumps(EVIDENCE_CHUNK_V1_SCHEMA, ensure_ascii=False, indent=2),
            "",
            "---",
            "",
            "Question:",
            question,
            "",
            "Outline / Chapters:",
            outline_text,
            "",
            "Subtitle Chunk:",
            chunk_text,
            "",
            "Return the evidence segment JSON now:",
        ]
    )
