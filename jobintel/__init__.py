"""Job-intelligence pipeline for buy-side / quant / market-trading roles in Europe.

0-budget design: deterministic Python (no paid LLM/proxy at runtime),
runs on free GitHub Actions cron, persists git-diffable JSON state, serves a
static frontend. See README.md for the full architecture.
"""

__version__ = "0.1.0"
