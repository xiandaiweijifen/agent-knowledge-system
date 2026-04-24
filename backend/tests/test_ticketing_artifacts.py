import json
import shutil
import uuid
from pathlib import Path

from app.schemas.tools import ToolExecutionRequest
from app.services.agent import tool_service


TMP_ROOT = Path(__file__).resolve().parent / "_tmp"
TMP_ROOT.mkdir(exist_ok=True)


def _make_tmp_dir() -> Path:
    path = TMP_ROOT / f"ticketing_artifacts_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_ticketing_draft_and_submit_persist_local_ticket_files(monkeypatch):
    tmp_path = _make_tmp_dir()
    ticket_store_path = tmp_path / "tickets.json"
    try:
        monkeypatch.setattr(tool_service, "TICKET_STORE_PATH", ticket_store_path)

        draft_response = tool_service.execute_tool_request(
            ToolExecutionRequest(
                tool_name="ticketing",
                action="draft",
                target="payment-service",
                arguments={
                    "environment": "production",
                    "severity": "high",
                    "supporting_summary": "Timeout rate is elevated and needs operator review.",
                },
            )
        )

        draft_output = draft_response.output
        markdown_path = Path(draft_output["ticket_artifact_path"])
        json_path = Path(draft_output["ticket_artifact_json_path"])

        assert draft_output["status"] == "draft"
        assert markdown_path.exists()
        assert json_path.exists()
        assert markdown_path.parent == tmp_path / "tickets"
        assert "TICKET-0001" in markdown_path.read_text(encoding="utf-8")
        assert "- Status: draft" in markdown_path.read_text(encoding="utf-8")

        submit_response = tool_service.execute_tool_request(
            ToolExecutionRequest(
                tool_name="ticketing",
                action="submit",
                target="payment-service",
                arguments={"ticket_id": draft_output["ticket_id"]},
            )
        )

        submit_output = submit_response.output
        submitted_markdown = markdown_path.read_text(encoding="utf-8")
        submitted_json = json.loads(json_path.read_text(encoding="utf-8"))
        stored_tickets = json.loads(ticket_store_path.read_text(encoding="utf-8"))

        assert submit_output["submission_state"] == "submitted"
        assert submit_output["status"] == "open"
        assert "- Status: open" in submitted_markdown
        assert "- Submission State: submitted" in submitted_markdown
        assert "- Submitted At:" in submitted_markdown
        assert submitted_json["submission_state"] == "submitted"
        assert stored_tickets[0]["ticket_artifact_path"] == str(markdown_path)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
