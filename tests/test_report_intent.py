from pathlib import Path

from podcast_agent.intent import (
    ReportIntent,
    detect_report_intent,
    load_report_intent,
    resolve_report_intent,
    write_report_intent,
)


def test_detect_report_intent_returns_language_and_length() -> None:
    prompts = []

    def fake_model_writer(prompt: str) -> str:
        prompts.append(prompt)
        return '{"language": "en", "length": "brief"}'

    intent = detect_report_intent(question="Please give me a concise English report.", model_writer=fake_model_writer)

    assert intent.report_language == "en"
    assert intent.report_length == "brief"
    assert intent.source == "model"
    assert len(prompts) == 1
    assert "Infer the user's output intent" in prompts[0]
    assert '"language"' in prompts[0]
    assert '"length"' in prompts[0]


def test_detect_report_intent_does_not_alias_language_names() -> None:
    intent = detect_report_intent(
        question="Please give me a concise English report.",
        model_writer=lambda _prompt: '{"language": "English", "length": "brief"}',
    )

    assert intent.report_language == "zh-Hans"
    assert intent.report_length == "brief"
    assert intent.source == "model"


def test_resolve_report_intent_falls_back_for_invalid_json() -> None:
    intent = resolve_report_intent(question="What changed?", model_writer=lambda _prompt: "not json")

    assert intent.report_language == "zh-Hans"
    assert intent.report_length == "default"
    assert intent.source == "fallback"
    assert "invalid JSON" in intent.fallback_reason


def test_write_and_load_report_intent(tmp_path: Path) -> None:
    path = tmp_path / "insights" / "intent.json"
    intent = ReportIntent(report_language="en", report_length="detailed", source="model")

    write_report_intent(path=path, question="Explain this in detail.", intent=intent)
    loaded = load_report_intent(path)

    assert loaded == intent
    assert '"question": "Explain this in detail."' in path.read_text(encoding="utf-8")
