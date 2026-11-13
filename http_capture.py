"""Capture public source responses without storing authorization/request headers."""
import contextvars
import hashlib
import json
import time
import uuid
from pathlib import Path

import requests

directory = contextvars.ContextVar("http_capture_directory", default=None)
_original = requests.get


def install():
    def get(url, **kwargs):
        folder = directory.get()
        if folder is None:
            return _original(url, **kwargs)
        started = time.time()
        record = {"url": url, "params": kwargs.get("params"), "started_at": started}
        try:
            response = _original(url, **kwargs)
            body = response.content
            record.update({"status_code": response.status_code,
                           "rate_limit": {k: response.headers[k] for k in
                               ["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset", "Retry-After"]
                               if k in response.headers},
                           "content_type": response.headers.get("Content-Type"),
                           "body_sha256": hashlib.sha256(body).hexdigest(),
                           "body_bytes": len(body), "body_truncated": len(body) > 2_000_000,
                           "body_text": body[:2_000_000].decode(response.encoding or "utf-8", errors="replace")})
            return response
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            record["elapsed_seconds"] = time.time() - started
            Path(folder).mkdir(parents=True, exist_ok=True)
            (Path(folder)/(uuid.uuid4().hex+".json")).write_text(json.dumps(record, ensure_ascii=False)+"\n")
    requests.get = get
