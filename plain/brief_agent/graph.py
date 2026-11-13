"""Assemble the brief pipeline."""
from langgraph.graph import END, START, StateGraph

from . import nodes
from .state import BriefState


def build_graph():
    g = StateGraph(BriefState)

    g.add_node("plan_queries", nodes.plan_queries)
    g.add_node("web_research", nodes.web_research)
    g.add_node("enrich_findings", nodes.enrich_findings)
    g.add_node("write_brief", nodes.write_brief)

    g.add_edge(START, "plan_queries")
    g.add_edge("plan_queries", "web_research")
    g.add_edge("web_research", "enrich_findings")
    g.add_edge("enrich_findings", "write_brief")
    g.add_edge("write_brief", END)

    return g.compile()
