"""Report intent detection and shared report intent contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from podcast_agent.insights.evidence import parse_model_json
from podcast_agent.insights.evidence_prompts import JSON_OBJECT_OUTPUT_RULES
from podcast_agent.insights.llm import ModelWriter
from podcast_agent.pipeline.artifacts import load_json, save_json


DEFAULT_REPORT_LANGUAGE = "zh-Hans"
REPORT_LENGTHS = {"brief", "default", "detailed"}
SUPPORTED_REPORT_LANGUAGES = {
    "ar",
    "de",
    "en",
    "en-GB",
    "en-US",
    "es",
    "fr",
    "it",
    "ja",
    "ko",
    "pt",
    "ru",
    "zh-Hans",
    "zh-Hant",
}


@dataclass(frozen=True)
class ReportIntent:
    report_language: str = DEFAULT_REPORT_LANGUAGE
    report_length: str = "default"
    source: str = "default"
    fallback_reason: str = ""


@dataclass(frozen=True)
class ReportLengthProfile:
    max_viewpoints: int
    summary_conclusions: str
    introduction_length: str
    takeaway_length: str
    outline_viewpoints: str


_REPORT_LANGUAGE_NAMES = {
    "zh-Hans": "Chinese",
    "zh-Hant": "Chinese",
    "en": "English",
    "en-GB": "English",
    "en-US": "English",
    "ja": "Japanese",
    "ko": "Korean",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ru": "Russian",
    "ar": "Arabic",
    "pt": "Portuguese",
    "it": "Italian",
}


_REPORT_LENGTH_PROFILES = {
    "brief": ReportLengthProfile(
        max_viewpoints=3,
        summary_conclusions="2-3",
        introduction_length="60-100 Chinese characters or equivalent length in the target language",
        takeaway_length="60-100 Chinese characters or equivalent length in the target language",
        outline_viewpoints="3-4",
    ),
    "default": ReportLengthProfile(
        max_viewpoints=8,
        summary_conclusions="3-5",
        introduction_length="120-180 Chinese characters or equivalent length in the target language",
        takeaway_length="120-180 Chinese characters or equivalent length in the target language",
        outline_viewpoints="4-8",
    ),
    "detailed": ReportLengthProfile(
        max_viewpoints=12,
        summary_conclusions="4-6",
        introduction_length="160-240 Chinese characters or equivalent length in the target language",
        takeaway_length="160-240 Chinese characters or equivalent length in the target language",
        outline_viewpoints="6-12",
    ),
}


def build_report_intent_prompt(question: str) -> str:
    allowed_languages = ", ".join(sorted(SUPPORTED_REPORT_LANGUAGES))
    allowed_lengths = ", ".join(sorted(REPORT_LENGTHS))
    output_rules = "\n".join(f"- {rule}" for rule in JSON_OBJECT_OUTPUT_RULES)
    return (
        "Infer the user's output intent for a video question report.\n"
        "Output requirements:\n"
        f"{output_rules}\n"
        'The "language" value must be an IETF BCP 47 language tag.\n'
        f'Choose the "language" value from these supported subtitle language tags: {allowed_languages}.\n'
        f'The "length" value must be exactly one of: {allowed_lengths}.\n'
        "Language rules:\n"
        "1. First infer whether the user wants the answer/report/summary written in a specific language.\n"
        "2. Return that requested output language only when the user intent is about response language.\n"
        "3. Output the language tag directly; do not output a language name such as English or Chinese.\n"
        "4. Do not choose a language just because the question mentions that language as a topic.\n"
        "5. If no output-language intent is expressed, return the primary language used by the question itself as one supported tag.\n"
        f"6. Use {DEFAULT_REPORT_LANGUAGE} if the language is unclear or not in the supported tag list.\n"
        "Length rules:\n"
        "1. Return brief only when the user clearly asks for a short, concise, simple, or brief report.\n"
        "2. Return detailed only when the user clearly asks for a detailed, comprehensive, long, or in-depth report.\n"
        "3. Return default when the user does not explicitly mention the desired report length.\n"
        "4. Do not infer length from topic complexity alone.\n"
        "Examples:\n"
        '- "Please summarize this video in English briefly." -> {"language":"en","length":"brief"}\n'
        '- "请用中文详细分析这个视频。" -> {"language":"zh-Hans","length":"detailed"}\n'
        '- "What does the video say about Chinese language education?" -> {"language":"en","length":"default"}\n'
        f'Expected format: {{"language":"{DEFAULT_REPORT_LANGUAGE}","length":"default"}}\n\n'
        f"Question:\n{question}"
    )


def detect_report_intent(*, question: str, model_writer: ModelWriter) -> ReportIntent:
    stripped_question = question.strip()
    if not stripped_question:
        raise ValueError("question is required")
    response = model_writer(build_report_intent_prompt(stripped_question))
    payload = parse_model_json(response)
    if not payload:
        snippet = response.strip().replace("\n", " ")[:120]
        raise ValueError(f"Report intent model returned invalid JSON: {snippet}")
    return ReportIntent(
        report_language=normalize_report_language(payload.get("language")),
        report_length=normalize_report_length(payload.get("length")),
        source="model",
        fallback_reason="",
    )


def resolve_report_intent(*, question: str, model_writer: ModelWriter) -> ReportIntent:
    try:
        return detect_report_intent(question=question, model_writer=model_writer)
    except Exception as exc:
        return ReportIntent(
            report_language=DEFAULT_REPORT_LANGUAGE,
            report_length="default",
            source="fallback",
            fallback_reason=str(exc),
        )


def write_report_intent(*, path: Path, question: str, intent: ReportIntent) -> Path:
    save_json(
        path,
        {
            "question": question,
            "report_language": intent.report_language,
            "report_length": intent.report_length,
            "source": intent.source,
            "fallback_reason": intent.fallback_reason,
        },
    )
    return path


def load_report_intent(path: Path) -> ReportIntent | None:
    if not path.is_file():
        return None
    payload = load_json(path)
    if not isinstance(payload, dict):
        return None
    return ReportIntent(
        report_language=normalize_report_language(payload.get("report_language")),
        report_length=normalize_report_length(payload.get("report_length")),
        source=str(payload.get("source") or "default"),
        fallback_reason=str(payload.get("fallback_reason") or ""),
    )


def normalize_report_language(value: Any) -> str:
    language = str(value or "").strip()
    if language in SUPPORTED_REPORT_LANGUAGES:
        return language
    return DEFAULT_REPORT_LANGUAGE


def normalize_report_length(value: Any) -> str:
    length = str(value or "").strip().lower()
    return length if length in REPORT_LENGTHS else "default"


def report_language_name(language: str) -> str:
    normalized = normalize_report_language(language)
    return _REPORT_LANGUAGE_NAMES.get(normalized, normalized)


def report_length_profile(length: str) -> ReportLengthProfile:
    return _REPORT_LENGTH_PROFILES[normalize_report_length(length)]
