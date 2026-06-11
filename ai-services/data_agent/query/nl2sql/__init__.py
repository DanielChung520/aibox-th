"""
NL→SQL Pipeline - Natural language to SQL query generation.

Provides a 3-tier hybrid SQL generation strategy:
- Template: Simple queries via SQL template substitution (no LLM)
- Small LLM: Medium complexity with focused schema context
- Large LLM: Complex multi-table joins with full LLM reasoning

# Last Update: 2026-03-23 18:40:25
# Author: Daniel Chung
# Version: 1.0.0
"""

from data_agent.query.nl2sql.orchestrator import run_nl2sql_pipeline

__all__ = ["run_nl2sql_pipeline"]
