"""Summary prompts copied from videochat."""

from __future__ import annotations

import json
from typing import Any

from podcast_agent.insights.evidence_prompts import JSON_OBJECT_OUTPUT_RULES
from podcast_agent.insights.outline_prompts import ReportIntent, normalize_report_length, report_language_name, report_length_profile


REPORT_SUMMARY_V1_HEADER = (
    "You are a senior feature editor synthesizing an evidence-based report from completed viewpoint details. "
    "Your task is to write a short reader introduction, distill condensed viewpoints into final report-level core conclusions, and produce one concise takeaway."
)


REPORT_SUMMARY_V1_INPUTS = [
    "The user's original question, used as the lens for the final synthesis.",
    "The target report language, which controls all user-facing generated summary fields.",
    "The target report length, which controls the number of core conclusions and the size of the introduction and takeaway.",
    "The video source URL, included only as source metadata.",
    "The video chapters, used only to understand the video's broad topic structure.",
    "The condensed viewpoint payload, containing viewpoint titles, viewpoint summaries, importance scores, importance reasons, sub-thesis titles, and short sub-thesis explanations.",
]


REPORT_SUMMARY_V1_BASE_OUTPUT_SHAPE_RULES = [
    "The introduction must be a concise reader guide in the target report language that frames what the report answers and why the findings matter.",
    "Write the introduction as a natural editorial opening, not an executive-summary label.",
    "The introduction should read like a fluent lead paragraph that brings the reader into the interview's central tension, speaker judgments, and report throughline.",
    "Core conclusion titles must be opinionated judgments, not neutral topic labels.",
    "Each core conclusion must include a concise rationale explaining why the judgment matters.",
    "Each core conclusion must include source_viewpoint_ids listing only the viewpoint ids that materially support that conclusion.",
    "Each core conclusion must include synthesis_type as multi_viewpoint when the conclusion genuinely depends on multiple viewpoints, or single_viewpoint when one strong viewpoint is the primary source.",
    "The one_paragraph_takeaway must be a concise editorial closing judgment in the target report language.",
    "Write the one_paragraph_takeaway as an editorial closing judgment, not a recap of every core conclusion.",
    "The one_paragraph_takeaway should answer the larger 'so what' implied by the core conclusions.",
    "viewpoint_order must list the completed viewpoint ids in the final narrative order for the viewpoint breakdown section.",
]


REPORT_SUMMARY_V1_INTENT_RULES = [
    "Treat the target report language as a hard constraint for introduction, core conclusion titles, core conclusion rationales, and one_paragraph_takeaway.",
    "Do not use the question language, subtitle language, or video language as the summary language when they conflict with the target report language.",
    "Treat the target report length as a synthesis constraint for summary density and paragraph length.",
    "For brief reports, write only the strongest editorial conclusions and keep the opening and takeaway tight.",
    "For default reports, synthesize the strongest distinct conclusions without trying to cover every secondary idea.",
    "For detailed reports, allow more core conclusions and fuller editorial framing when the condensed viewpoints support it, but do not pad weak material.",
]


REPORT_SUMMARY_V1_SYNTHESIS_RULES = [
    "Use the user's original question as the lens for deciding what the summary should emphasize.",
    "Use video chapters only to understand the video's broad topic structure and context.",
    "Use condensed viewpoints as the source material for synthesizing core conclusions.",
    "Use importance_score and importance_reason as prioritization signals when deciding which viewpoints deserve report-level core conclusions.",
    "Prioritize viewpoints scored 4-5 when distilling core conclusions, especially when they are directly relevant to the user's question.",
    "Use viewpoints scored 3 as supporting context, merge material, or secondary evidence unless they connect several higher-scored viewpoints.",
    "Usually exclude viewpoints scored 1-2 from core conclusions unless they create an essential contrast, caveat, or causal bridge.",
    "Do not mechanically sort or summarize by score; synthesize by argument structure, question relevance, and evidence strength.",
    "Decide viewpoint_order from the final report narrative, not from transcript chronology, outline order, or importance score alone.",
    "Make viewpoint_order follow the argument flow established by core_conclusions and source_viewpoint_ids.",
    "Every id in viewpoint_order must refer to a completed viewpoint present in the condensed viewpoint payload.",
    "Include each completed viewpoint id at most once in viewpoint_order.",
    "After ordering viewpoints that support core conclusions, append any remaining completed viewpoints where they best fit the narrative.",
    "Each viewpoint title and summary expresses a major argument; each sub-thesis title expresses a supporting judgment under that argument.",
    "Condense related viewpoints and sub-theses into report conclusions when they truly form one shared implication.",
    "Do not force unrelated or already-complete viewpoints into a multi-viewpoint conclusion.",
    "A core conclusion may rest on a single strong viewpoint when that viewpoint is already a complete report-level argument.",
    "List multiple source_viewpoint_ids only when the conclusion would be incomplete or misleading without each listed viewpoint.",
    "Do not create a one-to-one list of every top viewpoint under new wording; select the strongest conclusions for the requested report length.",
    "Each core conclusion should express what its source viewpoints justify, whether that source is one viewpoint or a genuine cross-viewpoint synthesis.",
    "Prefer conclusions that reveal causality, shifts, tradeoffs, bottlenecks, risks, opportunities, or strategic implications.",
    "Write core_conclusions first, then write the introduction from those final core_conclusions and their source_viewpoint_ids.",
    "Every major idea in the introduction must be traceable to at least one core conclusion.",
    "The introduction should set up the report's throughline, not preview stray interesting facts.",
    "Write one_paragraph_takeaway after core_conclusions and introduction, using the final core_conclusions as its only argumentative source.",
]


REPORT_SUMMARY_V1_BOUNDARY_RULES = [
    "Do not treat chapters as evidence for conclusions.",
    "Do not organize the summary around chapter order.",
    "Do not summarize each viewpoint one by one.",
    "Do not rely on subtitle quotes, timestamps, or full detailed explanations.",
    "Do not create new viewpoints, sub-theses, quote snippets, timestamps, or Markdown.",
    "Do not include Markdown headings, bullets, or labels in introduction or one_paragraph_takeaway.",
    "Do not start the introduction with 本报告基于, 本文将, 报告揭示了, or 核心看点包括.",
    "Do not make the introduction a list of topics.",
    "Do not use explicit counts such as two core judgments, three conclusions, or several points in introduction or one_paragraph_takeaway.",
    "Do not mention a topic in the introduction unless it is developed by a core conclusion and at least one selected viewpoint.",
    "Do not use the one_paragraph_takeaway to enumerate the report's topics or repeat the core conclusions in compressed form.",
    "Do not introduce any idea in one_paragraph_takeaway that is not grounded in the final core_conclusions.",
    "Do not mention importance scores, scoring mechanics, or importance_reason in the final user-facing output.",
    "Do not introduce facts, names, numbers, examples, or claims not present in the condensed viewpoints.",
]


REPORT_SUMMARY_V1_OUTPUT_RULES = [
    *JSON_OBJECT_OUTPUT_RULES,
    "Follow the schema exactly.",
    "Do not add extra top-level keys.",
]


REPORT_SUMMARY_V1_SCHEMA = {
    "report_type": "summary",
    "language": "<target_language>",
    "introduction": "<natural editorial introduction in the target report language>",
    "core_conclusions": [
        {
            "id": "C1",
            "title": "<sharp core judgment in the target report language>",
            "rationale": "<1-2 sentences in the target report language explaining the evidence basis and importance of the judgment>",
            "source_viewpoint_ids": ["V1", "V2"],
            "synthesis_type": "multi_viewpoint",
        }
    ],
    "viewpoint_order": ["<first_viewpoint_id_in_narrative_order>", "<next_viewpoint_id_in_narrative_order>"],
    "one_paragraph_takeaway": "<one concise editorial closing judgment in the target report language>",
}


def summary_intent_payload(report_intent: ReportIntent | None) -> dict[str, str]:
    active_intent = report_intent or ReportIntent()
    length = normalize_report_length(active_intent.report_length)
    profile = report_length_profile(length)
    return {
        "target_language": active_intent.report_language,
        "target_language_name": report_language_name(active_intent.report_language),
        "target_length": length,
        "target_core_conclusions": profile.summary_conclusions,
        "target_introduction_length": profile.introduction_length,
        "target_takeaway_length": profile.takeaway_length,
    }


def _summary_intent_requirement_lines(report_intent: ReportIntent | None) -> list[str]:
    payload = summary_intent_payload(report_intent)
    return [
        f"Target report language: {payload['target_language_name']}.",
        f"Target report length: {payload['target_length']}.",
        f"Target core conclusions: {payload['target_core_conclusions']}.",
        f"Target introduction length: {payload['target_introduction_length']}.",
        f"Target takeaway length: {payload['target_takeaway_length']}.",
        *REPORT_SUMMARY_V1_INTENT_RULES,
    ]


def _summary_output_shape_lines(report_intent: ReportIntent | None) -> list[str]:
    payload = summary_intent_payload(report_intent)
    return [
        *REPORT_SUMMARY_V1_BASE_OUTPUT_SHAPE_RULES[:3],
        f"Keep the introduction around {payload['target_introduction_length']}.",
        f"Distill only the essence into {payload['target_core_conclusions']} sharp, report-level core conclusions.",
        *REPORT_SUMMARY_V1_BASE_OUTPUT_SHAPE_RULES[3:],
        f"Keep the one_paragraph_takeaway around {payload['target_takeaway_length']}.",
    ]


def build_report_summary_v1_prompt(
    *,
    question: str,
    viewpoints: dict[str, Any],
    chapters: list[Any] | None = None,
    source_url: str | None = None,
    report_intent: ReportIntent | None = None,
) -> str:
    condensed_viewpoints = sanitize_summary_viewpoints(viewpoints)
    return "\n".join(
        [
            REPORT_SUMMARY_V1_HEADER,
            "",
            "## Input You Will Receive",
            "",
            *[f"- {item}" for item in REPORT_SUMMARY_V1_INPUTS],
            "",
            "## How To Synthesize",
            "",
            "### Report Intent Requirements",
            *[f"- {rule}" for rule in _summary_intent_requirement_lines(report_intent)],
            "",
            "### What To Produce",
            *[f"- {rule}" for rule in _summary_output_shape_lines(report_intent)],
            "",
            "### How To Produce It",
            *[f"- {rule}" for rule in REPORT_SUMMARY_V1_SYNTHESIS_RULES],
            "",
            "### Boundaries",
            *[f"- {rule}" for rule in REPORT_SUMMARY_V1_BOUNDARY_RULES],
            "",
            "## Output Requirements",
            "",
            *[f"- {rule}" for rule in REPORT_SUMMARY_V1_OUTPUT_RULES],
            "",
            "## Required JSON Schema",
            "",
            json.dumps(REPORT_SUMMARY_V1_SCHEMA, ensure_ascii=False, indent=2),
            "",
            "---",
            "",
            "Question:",
            question,
            "",
            "Report Intent:",
            json.dumps(summary_intent_payload(report_intent), ensure_ascii=False, indent=2),
            "",
            "Video URL:",
            source_url.strip() if source_url and source_url.strip() else "(not provided)",
            "",
            "Video Chapters:",
            json.dumps(chapters if isinstance(chapters, list) else [], ensure_ascii=False, indent=2),
            "",
            "Condensed Viewpoints:",
            json.dumps(condensed_viewpoints, ensure_ascii=False, indent=2),
            "",
            "Return the summary JSON now:",
        ]
    )


def sanitize_summary_viewpoints(viewpoints: dict[str, Any]) -> dict[str, Any]:
    raw_viewpoints = viewpoints.get("viewpoints", []) if isinstance(viewpoints, dict) else []
    if not isinstance(raw_viewpoints, list):
        raw_viewpoints = []
    condensed = []
    for viewpoint in raw_viewpoints:
        if not isinstance(viewpoint, dict):
            continue
        raw_sub_theses = viewpoint.get("sub_theses", [])
        if not isinstance(raw_sub_theses, list):
            raw_sub_theses = []
        sub_theses = []
        for sub_thesis in raw_sub_theses:
            if not isinstance(sub_thesis, dict):
                continue
            title = str(sub_thesis.get("title", "")).strip()
            if not title:
                continue
            condensed_sub_thesis = {"title": title}
            explanation = str(sub_thesis.get("explanation", "")).strip()
            if explanation:
                condensed_sub_thesis["explanation"] = explanation
            sub_theses.append(condensed_sub_thesis)
        condensed.append(
            {
                "id": str(viewpoint.get("id", "")).strip(),
                "title": str(viewpoint.get("title", "")).strip(),
                "summary": str(viewpoint.get("summary", "")).strip(),
                "importance_score": sanitize_importance_score(viewpoint.get("importance_score")),
                "importance_reason": str(viewpoint.get("importance_reason", "")).strip(),
                "sub_theses": sub_theses,
            }
        )
    return {"viewpoints": condensed}


def sanitize_importance_score(value: Any) -> int | None:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    if 1 <= score <= 5:
        return score
    return None
