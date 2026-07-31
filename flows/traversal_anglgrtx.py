# Source : flows/traversal_anglgrtx.py
# Analogy: Flow 3 entry point — starts from anglgrtx.TEXT, runs IMOS-only loop with no connection tree.
"""anglgrtx flow: articles.NAME → anglgrtx.TEXT → IMOS loop"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from flows.traversal_mixins import ImosMixin


class TraversalAnglgrtx(ImosMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT ag.TEXT "
            "FROM dbo.articles a "
            "JOIN dbo.anglgrtx ag "
            "  ON ag.NAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(ag.INORDER)), N'') IS NULL",
            (self.article,)
        )
        for row in rows:
            text = normalize(row["TEXT"])
            if text:
                path = [f"anglgrtx({self.article})", f"TEXT={text}"]
                self._classify_imos_loop(text, path)
        return self.result


def extract_anglgrtx(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglgrtx(article, max_depth).run()