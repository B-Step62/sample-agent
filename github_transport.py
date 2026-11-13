"""Credential-free public GitHub reads via the caller's managed MCP connection.

Transport adapter only: preserve the baseline's search query, sort, limits and
README truncation. No query reformulation, reranking or prompt changes.
"""
import base64
import contextvars
import json
import re

import requests

credential = contextvars.ContextVar("github_mcp_credential", default=None)
_original_get = requests.get
HOST = "https://e2-dogfood.staging.cloud.databricks.com"


def call(name, args):
    from databricks.sdk import WorkspaceClient
    authorization = credential.get()
    headers = ({"Authorization": authorization} if authorization else WorkspaceClient().config.authenticate())
    r = requests.post(HOST + "/ai-gateway/mcp-services/system.ai.github",
        headers={**headers, "Accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": name, "arguments": args}}, timeout=90)
    r.raise_for_status()
    body = r.json()
    result = body.get("result", {})
    if body.get("error") or result.get("isError"):
        text = json.dumps(body)
        if any(s in text.lower() for s in ["404", "not found"]):
            raise FileNotFoundError(name)
        # Never include the request or its authorization header in errors.
        raise RuntimeError("Managed GitHub request failed for " + name)
    blocks = result.get("content", [])
    texts = [b["text"] for b in blocks if b.get("type") == "text"]
    if len(texts) == 1:
        try:
            return json.loads(texts[0])
        except ValueError:
            return texts[0]
    raise RuntimeError("Unexpected managed GitHub response")


def readme(owner, repo):
    for directory in [".github", "", "docs"]:
        try:
            entries = call("get_file_contents", {"owner": owner, "repo": repo, "path": directory})
        except FileNotFoundError:
            continue
        if not isinstance(entries, list):
            raise RuntimeError("GitHub directory listing did not return entries")
        candidates = [e for e in entries if e.get("type") == "file" and
                      re.fullmatch(r"readme(?:\..*)?", e.get("name", ""), re.I)]
        if not candidates:
            continue
        # Use the common markdown name first, then deterministic GitHub filename order.
        candidates.sort(key=lambda x: (x["name"].lower() != "readme.md", x["name"].lower()))
        result = call("get_file_contents", {"owner": owner, "repo": repo, "path": candidates[0]["path"]})
        if isinstance(result, dict) and "content" in result:
            return result
        if isinstance(result, str) and result.startswith("successfully downloaded text file (SHA:"):
            content = result.split("\n", 1)[1]
            return {"encoding": "base64", "content": base64.b64encode(content.encode()).decode()}
        raise RuntimeError("GitHub README content unavailable")
    raise FileNotFoundError("README")


def install():
    def get(url, **kwargs):
        if url == "https://api.github.com/search/repositories":
            p = kwargs.get("params") or {}
            payload = call("search_repositories", {"query": p["q"], "sort": p.get("sort", "stars"),
                "order": p.get("order", "desc"), "perPage": p.get("per_page", 6), "minimal_output": False})
        elif re.fullmatch(r"https://api\.github\.com/repos/[^/]+/[^/]+/readme", url):
            owner, repo = url.split("/")[-3:-1]
            try:
                payload = readme(owner, repo)
            except FileNotFoundError:
                response = requests.Response()
                response.status_code = 404
                response.url = url
                response._content = b'{"message":"Not Found"}'
                return response
        else:
            return _original_get(url, **kwargs)
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response.encoding = "utf-8"
        response.headers["Content-Type"] = "application/json"
        response.headers["X-Caj-Source-Transport"] = "system.ai.github"
        response._content = json.dumps(payload).encode()
        return response
    requests.get = get
