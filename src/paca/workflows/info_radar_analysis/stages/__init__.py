"""Per-stage modules for the info-radar-analysis pipeline.

Each stage owns one node in the pipeline (tier1 → fetch → tier2 → dedup).
The orchestrator (``runner.py``) wires them together with per-item failure
isolation.
"""
