"""CLI command and helpers for concurrent full-pipeline batches."""

import json
from pathlib import Path
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import typer

from podcast_agent.cli.app import app
from podcast_agent.errors import PodcastAgentError


@dataclass(frozen=True)
class FullBatchCase:
    id: str
    url: str
    question: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class FullBatchCaseResult:
    case: FullBatchCase
    output_dir: Path
    log_path: Path
    exit_code: int

    @property
    def status(self) -> str:
        return "success" if self.exit_code == 0 else "failure"


@app.command("full-batch")
def full_batch(
    cases_path: Path = typer.Option(
        Path("examples/full-report-cases.jsonl"),
        "--cases",
        help="JSONL or JSON file containing full pipeline cases.",
    ),
    case_ids: list[str] | None = typer.Option(
        None,
        "--case",
        help="Run only the given case id. Can be passed multiple times.",
    ),
    tags: list[str] | None = typer.Option(
        None,
        "--tag",
        help="Run only cases containing this tag. Can be passed multiple times.",
    ),
    output_root: Path = typer.Option(Path("output"), help="Root directory for batch outputs."),
    run_id: str | None = typer.Option(None, help="Run id for this batch. Defaults to a UTC timestamp."),
    max_jobs: int = typer.Option(3, help="Maximum number of concurrent full runs."),
    dry_run: bool = typer.Option(False, help="Print selected cases without running them."),
) -> None:
    """Run full pipeline cases from a JSONL or JSON file."""
    try:
        selected_cases = select_full_batch_cases(
            load_full_batch_cases(cases_path),
            case_ids=case_ids or [],
            tags=tags or [],
        )
        if max_jobs < 1:
            raise PodcastAgentError("Full batch failed: --max-jobs must be at least 1.")
        active_run_id = run_id or utc_run_id()
        batch_root = output_root / f"batch-{active_run_id}"
        logs_dir = batch_root / "logs"
        plans = [
            {
                "case": case,
                "output_dir": batch_root / f"{case.id}-{active_run_id}",
                "log_path": logs_dir / f"{case.id}.log",
            }
            for case in selected_cases
        ]
        if dry_run:
            typer.echo(f"Dry run: {len(plans)} cases selected.")
            typer.echo(f"Run ID: {active_run_id}")
            typer.echo(f"Output root: {batch_root}")
            for plan in plans:
                case = plan["case"]
                typer.echo(f"{case.id}\t{case.url}\t{plan['output_dir']}")
            return

        logs_dir.mkdir(parents=True, exist_ok=True)
        typer.echo(f"Running {len(plans)} cases with up to {max_jobs} parallel jobs.")
        typer.echo(f"Run ID: {active_run_id}")
        typer.echo(f"Output root: {batch_root}")
        typer.echo(f"Logs: {logs_dir}")
        results = run_full_batch_plans(plans=plans, max_jobs=max_jobs)
        write_full_batch_summary(
            logs_dir / "summary.json",
            run_id=active_run_id,
            results=results,
        )
    except PodcastAgentError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    failed = [result for result in results if result.exit_code != 0]
    for result in results:
        label = "OK  " if result.exit_code == 0 else "FAIL"
        typer.echo(f"{label} {result.case.id} log={result.log_path}")
    typer.echo(f"Summary: {logs_dir / 'summary.json'}")
    if failed:
        raise typer.Exit(code=1)


def load_full_batch_cases(path: Path) -> list[FullBatchCase]:
    if not path.is_file():
        raise PodcastAgentError(f"Full batch failed: cases file not found: {path}")
    if path.suffix.lower() == ".jsonl":
        return load_full_batch_cases_jsonl(path)
    return load_full_batch_cases_json(path)


def load_full_batch_cases_json(path: Path) -> list[FullBatchCase]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PodcastAgentError("Full batch failed: cases file must be valid JSON.") from exc
    if not isinstance(payload, dict):
        raise PodcastAgentError("Full batch failed: cases file must contain a JSON object.")
    default_question = str(payload.get("default_question") or "").strip()
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise PodcastAgentError("Full batch failed: cases must be a non-empty array.")

    return build_full_batch_cases(raw_cases, default_question=default_question, source_label="cases")


def load_full_batch_cases_jsonl(path: Path) -> list[FullBatchCase]:
    raw_cases: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError as exc:
        raise PodcastAgentError("Full batch failed: cases file must be UTF-8 encoded.") from exc

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            raw_case = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise PodcastAgentError(f"Full batch failed: cases line {line_number} must be valid JSON.") from exc
        if not isinstance(raw_case, dict):
            raise PodcastAgentError(f"Full batch failed: cases line {line_number} must be a JSON object.")
        if raw_case.get("enabled", True) is False:
            continue
        raw_cases.append(raw_case)

    if not raw_cases:
        raise PodcastAgentError("Full batch failed: cases must contain at least one enabled case.")
    return build_full_batch_cases(raw_cases, default_question="", source_label="cases line")


def build_full_batch_cases(
    raw_cases: list[dict[str, Any]],
    *,
    default_question: str,
    source_label: str,
) -> list[FullBatchCase]:
    cases: list[FullBatchCase] = []
    seen_ids: set[str] = set()
    for index, raw_case in enumerate(raw_cases, start=1):
        if not isinstance(raw_case, dict):
            raise PodcastAgentError(f"Full batch failed: {source_label}[{index}] must be a JSON object.")
        case_id = str(raw_case.get("id") or "").strip()
        url = str(raw_case.get("url") or "").strip()
        question = str(raw_case.get("question") or default_question).strip()
        tags = raw_case.get("tags", [])
        if not case_id:
            raise PodcastAgentError(f"Full batch failed: {source_label}[{index}].id is required.")
        if case_id in seen_ids:
            raise PodcastAgentError("Full batch failed: cases[].id must be unique.")
        if not url:
            raise PodcastAgentError(f"Full batch failed: {source_label}[{index}].url is required.")
        if not question:
            raise PodcastAgentError(f"Full batch failed: {source_label}[{index}].question is required.")
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise PodcastAgentError(f"Full batch failed: {source_label}[{index}].tags must be an array of strings.")
        seen_ids.add(case_id)
        cases.append(
            FullBatchCase(
                id=case_id,
                url=url,
                question=question,
                tags=tuple(tag.strip() for tag in tags if tag.strip()),
            )
        )
    return cases


def select_full_batch_cases(
    cases: list[FullBatchCase],
    *,
    case_ids: list[str],
    tags: list[str],
) -> list[FullBatchCase]:
    selected = cases
    normalized_case_ids = {case_id.strip() for case_id in case_ids if case_id.strip()}
    if normalized_case_ids:
        selected = [case for case in selected if case.id in normalized_case_ids]
    normalized_tags = {tag.strip() for tag in tags if tag.strip()}
    if normalized_tags:
        selected = [case for case in selected if normalized_tags.issubset(set(case.tags))]
    if not selected:
        raise PodcastAgentError("Full batch failed: no cases selected.")
    return selected


def run_full_batch_plans(*, plans: list[dict[str, Any]], max_jobs: int) -> list[FullBatchCaseResult]:
    results: list[FullBatchCaseResult] = []
    with ThreadPoolExecutor(max_workers=max_jobs) as executor:
        futures = [executor.submit(run_full_batch_case, case=plan["case"], output_dir=plan["output_dir"], log_path=plan["log_path"]) for plan in plans]
        for future in as_completed(futures):
            results.append(future.result())
    results_by_id = {result.case.id: result for result in results}
    return [results_by_id[plan["case"].id] for plan in plans]


def run_full_batch_case(*, case: FullBatchCase, output_dir: Path, log_path: Path) -> FullBatchCaseResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        str(resolve_podcast_agent_command()),
        "full",
        "--url",
        case.url,
        "--question",
        case.question,
        "--output-dir",
        str(output_dir),
    ]
    with log_path.open("w", encoding="utf-8") as log_file:
        log_file.write("==> Running full pipeline\n")
        log_file.write(f"    Case: {case.id}\n")
        log_file.write(f"    URL: {case.url}\n")
        log_file.write(f"    Output: {output_dir}\n")
        log_file.write(f"    Started: {datetime.now(timezone.utc).isoformat()}\n\n")
        log_file.flush()
        completed = subprocess.run(command, stdout=log_file, stderr=subprocess.STDOUT, text=True)
        log_file.write(f"\n    Finished: {datetime.now(timezone.utc).isoformat()}\n")
        log_file.write(f"    Exit code: {completed.returncode}\n")
    return FullBatchCaseResult(case=case, output_dir=output_dir, log_path=log_path, exit_code=completed.returncode)


def write_full_batch_summary(path: Path, *, run_id: str, results: list[FullBatchCaseResult]) -> None:
    payload = {
        "run_id": run_id,
        "case_count": len(results),
        "success_count": sum(1 for result in results if result.exit_code == 0),
        "failure_count": sum(1 for result in results if result.exit_code != 0),
        "cases": [
            {
                "id": result.case.id,
                "url": result.case.url,
                "output_dir": str(result.output_dir),
                "log_path": str(result.log_path),
                "status": result.status,
                "exit_code": result.exit_code,
            }
            for result in results
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def resolve_podcast_agent_command() -> Path | str:
    current = Path(sys.argv[0])
    if current.name == "podcast-agent" and current.exists():
        return current
    local = Path(".venv/bin/podcast-agent")
    if local.exists():
        return local
    return "podcast-agent"
