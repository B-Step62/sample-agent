# Conversational research assistant

A LangGraph application that searches GitHub and Hacker News to answer developer research requests. The conversation entry point is `plain/brief_agent/conversation.py:reply`.

The Databricks App wrapper exposes authenticated `/health`, `/conversations`, and `/requests/{id}` endpoints. Use the benchmark assignment commands to evaluate, publish and deploy a revision, and generate simulated conversations. The deployed revision is returned by `/health` and included in every trace.

The wrapper supplies standard Databricks service-principal credentials for model access and tracing. Public GitHub source reads use the caller's existing managed `system.ai.github` OAuth connection. The traffic runner forwards the caller's workspace authorization to this isolated App in memory for that request; it is never logged or persisted. The adapter preserves queries, sort order, result limits and README truncation. It chooses README files in `.github`, the repository root, then `docs`, preferring README.md. Hacker News and linked pages are fetched directly.

Application dependencies are pinned in `requirements-app.lock`. Install with `pip install --require-hashes -r requirements-app.lock`. This differs from the captured `requirements.lock` only in the certifi CA-bundle patch required by Databricks Apps (2026.10.19).

The captured application source is derived from `adamgurary/claude-skills-brief-agent`, revision a880574a83ccf27e498339bd7ac9c35cc2aa0bca, with the conversational entry point captured at f053802cf1b109f87cd85699394a00431a649002. The baseline graph, research logic, prompts and model are preserved. `baseline-provenance.json` records the captured source hash. The serving/authentication transport is additional infrastructure.

All benchmark users and reactions are simulated. Their reactions are evidence to investigate, not human feedback or correctness ground truth.

Databricks Apps uses `pyproject.toml` and `uv.lock` to select Python 3.12, matching the captured runtime. The lock targets the E2 workspace package registry and retains exact package hashes. There is intentionally no `requirements.txt`, which would select the platform Python 3.11 installer.
