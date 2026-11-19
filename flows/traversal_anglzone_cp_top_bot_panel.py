# Source : flows/traversal_anglzone_cp_top_bot_panel.py
# Analogy: Flow entry point — anglzone.NAME -> MANINFOTS/MANINFOBS (ident) + TOPSHELF/BOTSHELF -> CABIN -> KMS/nut_erb/ident/CPCONNPRIM(TYPE=3)->CPCONNLIST(TYPE=4)->CONNECTIONS.
"""anglzone_cp_top_bot_panel flow: articles.NAME -> anglzone.NAME -> MANINFOTS/MANINFOBS + TOPSHELF/BOTSHELF -> CABIN -> KMS/nut_erb/ident/CONNECTIONS"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_ANGLZONE
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin


class TraversalAnglzoneCpTopBotPanel(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

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
                self._classify(nm, STATE_ANGLZONE, path + [f"anglzone.NAME={nm}"], "anglzone", "NAME")
        return self.result


def extract_anglzone_cp_top_bot_panel(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglzoneCpTopBotPanel(article, max_depth).run()


FLOW_NAME = "anglzone_cp_top_bot_panel"
extract = extract_anglzone_cp_top_bot_panel


def extract_all_anglzone_cp_top_bot_panel(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_anglzone_cp_top_bot_panel(name, max_depth))
    return results


extract_all = extract_all_anglzone_cp_top_bot_panel