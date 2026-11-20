# Source : flows/traversal_anglelem_cp_side_adder_panel_partition.py
# Analogy: Flow entry point — anglzone.NAME -> MANINFODI (ident) + DIVIDER (DIVTYPE='S'/'D') -> CSIDE + HORDEFTYPE based LINDIV1/LINDIV2/SDIVANGLE.
"""anglelem_cp_side_adder_panel_partition flow: articles.NAME -> anglzone.NAME -> MANINFODI + DIVIDER (DIVTYPE=S/D) -> CSIDE + HORDEFTYPE based LINDIV1/LINDIV2/SDIVANGLE"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_ANGLZONE_SIDE_PARTITION
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin


class TraversalAnglelemCpSideAdderPanelPartition(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

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
                self._classify(nm, STATE_ANGLZONE_SIDE_PARTITION, path + [f"anglzone.NAME={nm}"], "anglzone", "NAME")
        return self.result


def extract_anglelem_cp_side_adder_panel_partition(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglelemCpSideAdderPanelPartition(article, max_depth).run()


FLOW_NAME = "anglelem_cp_side_adder_panel_partition"
extract = extract_anglelem_cp_side_adder_panel_partition


def extract_all_anglelem_cp_side_adder_panel_partition(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_anglelem_cp_side_adder_panel_partition(name, max_depth))
    return results


extract_all = extract_all_anglelem_cp_side_adder_panel_partition