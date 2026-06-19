"""Standard-library HTTP server for the VideoChat-compatible API."""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from podcast_agent.api.adapters import find_report_path, load_source_metadata
from podcast_agent.api.followup import run_followup_for_task
from podcast_agent.api.runner import ReportMode, run_api_pipeline
from podcast_agent.api.store import DEFAULT_TASK_ROOT, TaskStore


DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8080
API_PREFIX = "/videochat/api/tasks"


class VideoChatRequestHandler(BaseHTTPRequestHandler):
    store: TaskStore

    def do_POST(self) -> None:
        if self.path == f"{API_PREFIX}/sync":
            self._handle_sync_post()
            return

        task_id, action = self._parse_task_path()
        if task_id and action == "followup":
            self._handle_followup(task_id)
            return

        if self.path != API_PREFIX:
            self._send_json(404, {"error": "not_found"})
            return

        payload = self._read_json()
        url = str(payload.get("url", "")).strip()
        question = str(payload.get("question", "")).strip()
        if not url or not question:
            self._send_json(400, {"error": "invalid_request", "message": "url and question are required"})
            return

        record = self.store.create_task(url=url, question=question)
        self._send_json(202, record.to_dict())

    def _handle_sync_post(self) -> None:
        payload = self._read_json()
        url = str(payload.get("url", "")).strip()
        question = str(payload.get("question", "")).strip()
        if not url or not question:
            self._send_json(400, {"error": "invalid_request", "message": "url and question are required"})
            return

        record = self.store.run_task_sync(url=url, question=question)
        report = self.store.read_report(record.task_id)
        if record.status != "completed" or report is None:
            self._send_json(500, record.to_dict())
            return
        self._send_json(200, {**record.to_dict(), "report_markdown": report, "report_path": str(record.report_path or "")})

    def _handle_followup(self, task_id: str) -> None:
        record = self.store.get_or_load_task(task_id)
        if record is None:
            self._send_json(404, {"error": "task_not_found"})
            return

        payload = self._read_json()
        question = str(payload.get("question", "")).strip()
        if not question:
            self._send_json(400, {"error": "invalid_request", "message": "question is required"})
            return

        try:
            result = run_followup_for_task(task_dir=record.task_dir, task_id=task_id, question=question)
        except FileNotFoundError:
            self._send_json(404, {"error": "subtitle_not_found", "message": "Task has no subtitle file"})
            return
        except Exception as exc:
            self._send_json(500, {"error": "followup_failed", "message": str(exc)})
            return

        self._send_json(200, {"segments": result.segments, "sufficient": result.sufficient, "reason": result.reason})

    def do_GET(self) -> None:
        task_id, action = self._parse_task_path()
        if not task_id:
            self._send_json(404, {"error": "not_found"})
            return

        record = self.store.get_or_load_task(task_id)
        if record is None:
            self._send_json(404, {"error": "task_not_found"})
            return

        if action == "status":
            payload = record.to_dict()
            timing = self.store.timing_snapshot(task_id)
            if timing is not None:
                payload["timing"] = timing
            self._send_json(200, payload)
            return

        if action == "progress":
            query = self._read_progress_query()
            if query is None:
                self._send_json(400, {"error": "invalid_request", "message": "after_seq must be a non-negative integer"})
                return
            after_seq, limit = query
            events = self.store.read_progress(task_id, after_seq=after_seq, limit=limit) or []
            next_after_seq = int(events[-1]["seq"]) if events else after_seq
            more_events = self.store.read_progress(task_id, after_seq=next_after_seq, limit=1) or []
            self._send_json(
                200,
                {
                    "task_id": task_id,
                    "status": record.status,
                    "next_after_seq": next_after_seq,
                    "has_more": bool(more_events),
                    "events": events,
                    "timing": self.store.timing_snapshot(task_id) or {},
                },
            )
            return

        if action == "report":
            report = self.store.read_report(task_id)
            if report is None:
                self._send_json(404, {"error": "report_not_found", "status": record.status})
                return
            report_path = find_report_path(record.task_dir)
            self._send_json(
                200,
                {
                    "task_id": task_id,
                    "status": record.status,
                    "report_markdown": report,
                    "report_path": str(report_path) if report_path else "",
                    "source_metadata": load_source_metadata(record.task_dir),
                },
            )
            return

        self._send_json(404, {"error": "not_found"})

    def do_DELETE(self) -> None:
        task_id, action = self._parse_task_path()
        if not task_id or action:
            self._send_json(404, {"error": "not_found"})
            return
        if not self.store.delete_task(task_id):
            self._send_json(404, {"error": "task_not_found"})
            return
        self._send_json(200, {"task_id": task_id, "status": "deleted"})

    def log_message(self, _format: str, *_args: object) -> None:
        return

    def _parse_task_path(self) -> tuple[str, str]:
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        if len(parts) == 4 and parts[:3] == ["videochat", "api", "tasks"]:
            return parts[3], ""
        if len(parts) == 5 and parts[:3] == ["videochat", "api", "tasks"]:
            return parts[3], parts[4]
        return "", ""

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _read_progress_query(self) -> tuple[int, int] | None:
        query = parse_qs(urlparse(self.path).query)
        try:
            after_seq = int(query.get("after_seq", ["0"])[0])
            limit = int(query.get("limit", ["100"])[0])
        except ValueError:
            return None
        if after_seq < 0 or limit < 1:
            return None
        return after_seq, min(limit, 500)

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def create_server(address: tuple[str, int], store: TaskStore) -> ThreadingHTTPServer:
    class Handler(VideoChatRequestHandler):
        pass

    Handler.store = store
    return ThreadingHTTPServer(address, Handler)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Podcast-Agent VideoChat-compatible API.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--task-root", default=str(DEFAULT_TASK_ROOT))
    parser.add_argument("--report-mode", choices=["markdown", "html", "pdf", "xhs", "all"], default="markdown")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report_mode: ReportMode = args.report_mode

    def runner(url: str, question: str, task_dir: Path, progress_sink=None) -> None:
        run_api_pipeline(url=url, question=question, task_dir=task_dir, progress_sink=progress_sink, report_mode=report_mode)

    store = TaskStore(Path(args.task_root), runner=runner)
    server = create_server((args.host, args.port), store)
    print(f"Podcast-Agent API listening on http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
