"""Conversational entry point for the PE77 baseline research application."""
import datetime

import mlflow

from .graph import build_graph

FAILURE_RESPONSE = "I couldn't complete this research request because a source or model request failed. Please try again."


class TurnFailure(RuntimeError):
    def __init__(self, trace_id, cause):
        super().__init__(str(cause))
        self.trace_id = trace_id
        self.response = FAILURE_RESPONSE


def reply(messages, *, session_id, user_id, turn_index, task_id, source_commit,
          topic, date=None, on_trace_started=None):
    """Execute a real research turn; return its response and trace identity."""
    trace_id = None
    try:
        with mlflow.start_span(name="brief_agent_conversation", span_type="AGENT") as root:
            trace_id = root.trace_id
            if on_trace_started:
                on_trace_started(trace_id)
            root.set_inputs({"messages": messages, "topic": topic})
            root.set_attributes({"session.id": session_id, "user.id": user_id})
            mlflow.update_current_trace(
                metadata={"mlflow.trace.session": session_id, "mlflow.trace.user": user_id,
                          "application.commit": source_commit, "task.id": task_id,
                          "turn.index": str(turn_index), "traffic.origin": "simulated_user"},
                tags={"traffic_origin": "simulated_user", "dataset_role": "reference",
                      "application": "pe77_conversational_brief_agent"},
                request_preview=messages[-1]["content"],
            )
            try:
                state = build_graph().invoke({
                    "topic": topic, "date": date or datetime.date.today().isoformat(),
                    "messages": messages, "session_id": session_id, "turn_index": turn_index,
                })
            except Exception:
                root.set_outputs({"messages": [{"role": "assistant", "content": FAILURE_RESPONSE}]})
                mlflow.update_current_trace(response_preview=FAILURE_RESPONSE)
                raise
            response = state.get("brief", "")
            root.set_outputs({"messages": [{"role": "assistant", "content": response}]})
            mlflow.update_current_trace(response_preview=response)
            return {"trace_id": trace_id, "response": response,
                    "result_count": state.get("result_count"),
                    "enriched_count": state.get("enriched_count"),
                    "output_path": state.get("output_path")}
    except Exception as exc:
        raise TurnFailure(trace_id, exc) from exc
