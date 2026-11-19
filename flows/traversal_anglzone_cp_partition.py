# Source : flows/traversal_anglzone_cp_partition.py
# Analogy: Flow entry point — anglzone.NAME -> MANINFODI (ident) + DIVIDER (DIVTYPE='P') -> CABIN + HORDEFTYPE=2 ? LINDIV1+LINDIV2 : HORDEFTYPE=A ? LINDIV1+SDIVANGLE : LINDIV1 -> terminal.
"""anglzone_cp_partition flow: articles.NAME -> anglzone.NAME -> MANINFODI + DIVIDER (DIVTYPE=P) -> CABIN + HORDEFTYPE based LINDIV1/LINDIV2/SDIVANGLE"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_ANGLZONE_PARTITION
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin


class TraversalAnglzoneCpPartition(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT az.NAME "
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
            nm = normalize(row.get("NAME"))
            if nm:
                self._classify(nm, STATE_ANGLZONE_PARTITION, path + [f"anglzone.NAME={nm}"], "anglzone", "NAME")
        return self.result


def extract_anglzone_cp_partition(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglzoneCpPartition(article, max_depth).run()


FLOW_NAME = "anglzone_cp_partition"
extract = extract_anglzone_cp_partition


def extract_all_anglzone_cp_partition(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_anglzone_cp_partition(name, max_depth))
    return results


extract_all = extract_all_anglzone_cp_partition