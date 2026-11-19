# Source : flows/traversal_anglzone_cp_virtual_shelf.py
# Analogy: Flow entry point — anglzone.NAME -> LINDIV1 ($ variable / #descriptor resolution).
"""anglzone_cp_virtual_shelf flow: articles.NAME -> anglzone.NAME -> LINDIV1 (IMOS variable / DESCRIPTOR resolution)"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_TERMINAL
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin


class TraversalAnglzoneCpVirtualShelf(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT az.LINDIV1 "
            "FROM dbo.articles a "
            "JOIN dbo.anglzone az "
            "  ON az.NAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(a.INORDER)), N'') IS NULL "
            "  AND NULLIF(LTRIM(RTRIM(az.INORDER)), N'') IS NULL",
            (self.article,)
        )
        for row in rows:
            path = [f"anglzone({self.article})"]
            lindiv1 = normalize(row.get("LINDIV1"))
            if lindiv1:
                self._classify(lindiv1, STATE_TERMINAL, path + [f"anglzone.LINDIV1={lindiv1}"], "anglzone", "LINDIV1")
        return self.result


def extract_anglzone_cp_virtual_shelf(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglzoneCpVirtualShelf(article, max_depth).run()


FLOW_NAME = "anglzone_cp_virtual_shelf"
extract = extract_anglzone_cp_virtual_shelf


def extract_all_anglzone_cp_virtual_shelf(max_depth: int = 40) -> list[ExtractionResult]:
    from core.db import query as _query
    rows = _query(
        "SELECT DISTINCT NAME FROM dbo.articles "
        "WHERE NULLIF(LTRIM(RTRIM(INORDER)), N'') IS NULL ORDER BY NAME"
    )
    results = []
    for row in rows:
        name = normalize(row["NAME"])
        if name:
            print(f"  Extracting: {name}")
            results.append(extract_anglzone_cp_virtual_shelf(name, max_depth))
    return results


extract_all = extract_all_anglzone_cp_virtual_shelf