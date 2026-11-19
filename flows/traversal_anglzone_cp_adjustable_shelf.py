# Source : flows/traversal_anglzone_cp_adjustable_shelf.py
# Analogy: Flow entry point — anglzone.NAME -> MANINFODI (ident) + LINDIV1 + DIVIDER (DIVTYPE='A') -> CABIN (KONSTTYP=8 stop) -> UEBERST_*/SX_WINKEL/SY_WINKEL/CPINFO/NUT_ERB/KMS/CPCONNPRIM(TYPE=3)->CPCONNLIST(TYPE=3)->CONNECTIONS.
"""anglzone_cp_adjustable_shelf flow: articles.NAME -> anglzone.NAME -> MANINFODI + LINDIV1 + DIVIDER (DIVTYPE=A) -> CABIN -> UEBERST_*/SX_WINKEL/SY_WINKEL/CPINFO/NUT_ERB/KMS/CONNECTIONS"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_ANGLZONE_ADJUSTABLE_SHELF
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin


class TraversalAnglzoneCpAdjustableShelf(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

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
                self._classify(nm, STATE_ANGLZONE_ADJUSTABLE_SHELF, path + [f"anglzone.NAME={nm}"], "anglzone", "NAME")
        return self.result


def extract_anglzone_cp_adjustable_shelf(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglzoneCpAdjustableShelf(article, max_depth).run()


FLOW_NAME = "anglzone_cp_adjustable_shelf"
extract = extract_anglzone_cp_adjustable_shelf


def extract_all_anglzone_cp_adjustable_shelf(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_anglzone_cp_adjustable_shelf(name, max_depth))
    return results


extract_all = extract_all_anglzone_cp_adjustable_shelf