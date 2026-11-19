# Source : flows/traversal_anglzone_cp_top_bot_rail.py
# Analogy: Flow entry point — anglzone.NAME -> MANINFOTS/MANINFOBS (ident) + TOPSHELF/BOTSHELF -> CABIN (KONSTTYP=8) -> SHOEHE/CPINFO/CPCONNPRIM(TYPE=3)->CPCONNLIST(TYPE=3)->CONNECTIONS + TRAVERSE -> KMS_VORNE/KMS_HINTEN -> KMS.
"""anglzone_cp_top_bot_rail flow: articles.NAME -> anglzone.NAME -> MANINFOTS/MANINFOBS + TOPSHELF/BOTSHELF -> CABIN (KONSTTYP=8) -> SHOEHE/CPINFO/CONNECTIONS + TRAVERSE -> KMS"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_ANGLZONE_RAIL
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin


class TraversalAnglzoneCpTopBotRail(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

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
                self._classify(nm, STATE_ANGLZONE_RAIL, path + [f"anglzone.NAME={nm}"], "anglzone", "NAME")
        return self.result


def extract_anglzone_cp_top_bot_rail(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglzoneCpTopBotRail(article, max_depth).run()


FLOW_NAME = "anglzone_cp_top_bot_rail"
extract = extract_anglzone_cp_top_bot_rail


def extract_all_anglzone_cp_top_bot_rail(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_anglzone_cp_top_bot_rail(name, max_depth))
    return results


extract_all = extract_all_anglzone_cp_top_bot_rail