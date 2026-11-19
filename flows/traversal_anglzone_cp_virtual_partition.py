# Source : flows/traversal_anglzone_cp_virtual_partition.py
# Analogy: Flow entry point — anglzone.NAME -> HORDEFTYPE=2 ? LINDIV1+LINDIV2 : LINDIV1 -> IMOS variable / #DESCRIPTOR resolution (terminal).
"""anglzone_cp_virtual_partition flow: articles.NAME -> anglzone.NAME -> HORDEFTYPE=2 ? LINDIV1+LINDIV2 : LINDIV1 -> IMOS variable / DESCRIPTOR resolution"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_TERMINAL
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin


class TraversalAnglzoneCpVirtualPartition(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT az.HORDEFTYPE, az.LINDIV1, az.LINDIV2, az.SDIVANGLE "
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

            hordeftype = row.get("HORDEFTYPE")
            if self._int_in(hordeftype, (2,)):
                cols = ("LINDIV1", "LINDIV2")
            elif (normalize(hordeftype) or "").upper() == "A":
                cols = ("LINDIV1", "SDIVANGLE")
            else:
                cols = ("LINDIV1",)
            for col in cols:
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"anglzone.{col}={val}"], "anglzone", col)
        return self.result


def extract_anglzone_cp_virtual_partition(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglzoneCpVirtualPartition(article, max_depth).run()


FLOW_NAME = "anglzone_cp_virtual_partition"
extract = extract_anglzone_cp_virtual_partition


def extract_all_anglzone_cp_virtual_partition(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_anglzone_cp_virtual_partition(name, max_depth))
    return results


extract_all = extract_all_anglzone_cp_virtual_partition