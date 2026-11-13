"""Prompts for planning searches and writing the brief."""

DEFAULT_TOPIC = "cool new Claude Code skills and plugins"

PLAN_SYSTEM = """You plan web research. Given a topic, you produce a short list of \
search queries that find the most popular and well-known projects and tools for \
that topic.

The queries run against KEYWORD search APIs (Hacker News and GitHub), which match \
all words as an AND. So each query must be SHORT: 2 to 4 plain keywords, no full \
sentences, no years, no site: operators, no punctuation. Use the core keywords of \
the topic.

Output ONLY the queries, one per line, no numbering, no commentary, no preamble."""

PLAN_USER_TEMPLATE = """Topic: {topic}
Today's date: {date}

Write 4 short keyword queries (2 to 4 words each) for the most popular, well-known \
projects on this topic. One query per line.

Example of the right shape for a different topic (Rust web frameworks):
rust web framework
rust framework
rust web
rust http server"""


WRITE_SYSTEM = """You write a short brief listing what is popular in a technical \
topic right now. You are given a list of search findings (titles, links, popularity \
signals) from Hacker News and GitHub.

Write the brief in Markdown with this exact shape:

# {title}

_Brief generated {date}_

## Notable projects and releases
List the most popular items, ordered by popularity (stars and points). One bullet \
each, a bold-linked name and a few words naming what it is. Keep each bullet to a \
single short line.

## Also worth a look
A few more bullets, name linked, one short line each.

Rules:
- Use ONLY what the findings support. Do not invent projects, versions, dates, or \
star counts.
- No em dashes, no semicolons. Use periods and commas.
- Keep it short.
Output ONLY the Markdown brief, no preamble."""

WRITE_USER_TEMPLATE = """Topic: {topic}
Today's date: {date}

=== SEARCH FINDINGS (all items found) ===

{findings}

=== DEEP CONTENT (fetched README / page text for the top items) ===

{enriched}

Write the brief now. Draw the specific detail in your writeups from the deep \
content above."""
