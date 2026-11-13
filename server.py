"""Authenticated Databricks App wrapper with revision receipts and async requests."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import threading
import uuid

import mlflow
from databricks.sdk import WorkspaceClient
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "plain"))
os.environ.setdefault("BRIEF_AGENT_OUTPUT_DIR", "/tmp/caj-briefs")
os.environ.setdefault("MLFLOW_TRACKING_URI", "databricks")
os.environ["MLFLOW_DISABLE_AGENT_HINT"] = "1"
from brief_agent import llm
from brief_agent.conversation import reply, TurnFailure
import github_transport
import http_capture

llm._workspace_client = lambda: WorkspaceClient()
github_transport.install()
http_capture._original = __import__("requests").get
http_capture.install()
mlflow.set_tracking_uri("databricks")
mlflow.set_experiment(experiment_id=os.environ["CAJ_EXPERIMENT_ID"])
mlflow.langchain.autolog()

DEPLOYMENT = json.loads((ROOT / "deployment.json").read_text())
BOOT = uuid.uuid4().hex
POOL = ThreadPoolExecutor(max_workers=1)
LOCK = threading.Lock()
RECEIPTS = {}
app = FastAPI()


class Turn(BaseModel):
    request_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{1,100}$")
    session_id: str
    user_id: str
    task_id: str
    turn_index: int = Field(ge=1, le=10)
    topic: str
    messages: list[dict[str, str]]
    date: str | None = None
    role: str = "deployed_traffic"


@app.get("/health")
def health():
    return {**DEPLOYMENT, "boot_id": BOOT, "experiment_id": os.environ["CAJ_EXPERIMENT_ID"]}


def execute(turn, authorization):
    # Authorization is used only in memory for this caller's GitHub MCP requests.
    token = github_transport.credential.set(authorization)
    folder = Path("/tmp/caj-evidence") / turn.request_id
    folder.mkdir(parents=True, exist_ok=True)
    capture_token = http_capture.directory.set(folder)
    record = RECEIPTS[turn.request_id]
    record["status"] = "running"
    def started(trace_id):
        record["trace_id"] = trace_id
        mlflow.update_current_trace(tags={"dataset_role": turn.role, "caj.run_id": DEPLOYMENT["run_id"]},
            metadata={"caj.deployment_id": DEPLOYMENT["deployment_id"], "caj.request_id": turn.request_id})
    try:
        result = reply(turn.messages, session_id=turn.session_id, user_id=turn.user_id,
            turn_index=turn.turn_index, task_id=turn.task_id, source_commit=DEPLOYMENT["revision"],
            topic=turn.topic, date=turn.date, on_trace_started=started)
        # reply sets baseline dataset tags after its start callback; correct runtime role explicitly.
        mlflow.set_trace_tag(result["trace_id"], "dataset_role", turn.role)
        record.update(result, status="completed")
    except TurnFailure as error:
        record.update(status="failed", trace_id=error.trace_id, response=error.response,
                      error_type=type(error.__cause__).__name__)
    except Exception as error:
        record.update(status="failed", error_type=type(error).__name__)
    finally:
        mlflow.flush_trace_async_logging()
        record["sources"] = [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]
        github_transport.credential.reset(token)
        http_capture.directory.reset(capture_token)


@app.post("/conversations", status_code=202)
def conversation(turn: Turn, x_caj_github_authorization: str | None = Header(default=None)):
    if not x_caj_github_authorization or not x_caj_github_authorization.startswith("Bearer "):
        raise HTTPException(400, "Use the supplied traffic runner to authenticate GitHub source reads")
    fingerprint = hashlib.sha256(turn.model_dump_json().encode()).hexdigest()
    with LOCK:
        previous = RECEIPTS.get(turn.request_id)
        if previous:
            if previous["request_sha256"] != fingerprint:
                raise HTTPException(409, "Request ID was already used for different input")
            return {k: previous[k] for k in ["request_id", "status", "boot_id", "revision"]}
        RECEIPTS[turn.request_id] = {"request_id": turn.request_id, "status": "queued", "boot_id": BOOT,
            "revision": DEPLOYMENT["revision"], "request_sha256": fingerprint}
    POOL.submit(execute, turn, x_caj_github_authorization)
    return {"request_id": turn.request_id, "status": "queued", "boot_id": BOOT, "revision": DEPLOYMENT["revision"]}


@app.get("/requests/{request_id}")
def receipt(request_id: str):
    if request_id not in RECEIPTS:
        raise HTTPException(404, "Unknown request; do not replay automatically after an app restart")
    return RECEIPTS[request_id]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("DATABRICKS_APP_PORT", "8000")), access_log=False)
