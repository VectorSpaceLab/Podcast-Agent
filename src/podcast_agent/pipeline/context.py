"""Pipeline run context and output paths."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


@dataclass(frozen=True)
class PipelineContext:
    run_id: str
    url: str
    question: str
    output_dir: Path
    input_path: Path
    source_path: Path
    elements_dir: Path
    insights_dir: Path
    reports_dir: Path

    @classmethod
    def create(cls, url: str, question: str, output_dir: Path) -> "PipelineContext":
        output_dir = output_dir.expanduser()
        elements_dir = output_dir / "elements"
        insights_dir = output_dir / "insights"
        reports_dir = output_dir / "reports"

        for directory in (output_dir, elements_dir, insights_dir, reports_dir):
            directory.mkdir(parents=True, exist_ok=True)

        return cls(
            run_id=uuid4().hex,
            url=url,
            question=question,
            output_dir=output_dir,
            input_path=output_dir / "input.json",
            source_path=output_dir / "source.json",
            elements_dir=elements_dir,
            insights_dir=insights_dir,
            reports_dir=reports_dir,
        )
