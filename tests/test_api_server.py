import http.client
import json
import threading
import time
from pathlib import Path

from podcast_agent.api.server import create_server
from podcast_agent.api.store import TaskStore


def _request(port: int, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {"Content-Type": "application/json"} if body is not None else {}
    conn.request(method, path, body=payload, headers=headers)
    resp = conn.getresponse()
    raw = resp.read().decode("utf-8")
    conn.close()
    return resp.status, json.loads(raw) if raw else {}


def _start_server(store: TaskStore):
    server = create_server(("127.0.0.1", 0), store)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]


def test_api_server_sync_task_report_progress_and_delete(tmp_path: Path) -> None:
    def fake_runner(_url: str, _question: str, task_dir: Path) -> None:
        report_path = task_dir / "reports" / "report.md"
        report_path.parent.mkdir(parents=True)
        report_path.write_text("# Demo\n", encoding="utf-8")
        metadata_path = task_dir / "elements" / "metadata.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text('{"title": "Demo"}\n', encoding="utf-8")

    store = TaskStore(tmp_path, runner=fake_runner)
    server, port = _start_server(store)
    try:
        code, data = _request(port, "POST", "/videochat/api/tasks/sync", {"url": "https://example.com", "question": "q"})
        task_id = data["task_id"]

        assert code == 200
        assert data["report_markdown"] == "# Demo\n"

        code, status = _request(port, "GET", f"/videochat/api/tasks/{task_id}/status")
        assert code == 200
        assert status["status"] == "completed"
        assert "timing" in status

        code, progress = _request(port, "GET", f"/videochat/api/tasks/{task_id}/progress?after_seq=0&limit=10")
        assert code == 200
        assert progress["next_after_seq"] >= 1
        assert "events" in progress

        code, report = _request(port, "GET", f"/videochat/api/tasks/{task_id}/report")
        assert code == 200
        assert report["source_metadata"] == {"title": "Demo"}

        code, deleted = _request(port, "DELETE", f"/videochat/api/tasks/{task_id}")
        assert code == 200
        assert deleted["status"] == "deleted"
    finally:
        server.shutdown()
        server.server_close()


def test_api_server_async_create_returns_accepted(tmp_path: Path) -> None:
    def fake_runner(_url: str, _question: str, task_dir: Path) -> None:
        time.sleep(0.05)
        report_path = task_dir / "reports" / "report.md"
        report_path.parent.mkdir(parents=True)
        report_path.write_text("# Demo\n", encoding="utf-8")

    store = TaskStore(tmp_path, runner=fake_runner)
    server, port = _start_server(store)
    try:
        code, data = _request(port, "POST", "/videochat/api/tasks", {"url": "https://example.com", "question": "q"})

        assert code == 202
        assert data["status"] == "queued"
    finally:
        server.shutdown()
        server.server_close()


def test_api_server_invalid_request_returns_400(tmp_path: Path) -> None:
    server, port = _start_server(TaskStore(tmp_path, runner=lambda *_args: None))
    try:
        code, data = _request(port, "POST", "/videochat/api/tasks", {"url": ""})

        assert code == 400
        assert data["error"] == "invalid_request"
    finally:
        server.shutdown()
        server.server_close()

