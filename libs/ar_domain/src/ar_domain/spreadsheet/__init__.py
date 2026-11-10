"""Spreadsheet SQL.

Queries run in memory-only DuckDB with external access disabled (OQ-60).
"""

from ar_domain.spreadsheet.engine import SheetQueryError, query_loaded

__all__ = ["SheetQueryError", "query_loaded"]
