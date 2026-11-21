# Source : flows/traversal_drawersing_purchase_drawer.py
# Analogy: Flow entry point — articles.NAME -> DRAWERSING.NAME (FRONTTYPE=0) -> DRAWER -> $ -> IMOS -> raw -> DR_FRONT + DR_MAIN (purchase drawer).
"""DRAWERSING_PURCHASE_DRAWER flow:
   articles.NAME -> DRAWERSING.NAME
   -> WHERE DRAWERSING.FRONTTYPE=0 -> DRAWER
   -> $ -> IMOS -> raw -> DR_FRONT.NAME (SET_FRONT=1 gated: THKSTR/PART_INFO/PART_DEF/CONNSIT_PULL*)
                 + DR_MAIN.NAME (TYPE=4 gated: DR_X/DR_Z; ungated: DRDS_BEFR/DRDS_TEFR,
                   IGNORE_DRDSTOSH->DRDS_TOSH, IGNORE_DRDSBOSH->DRDS_BOSH, DRMANINFO, CONNSIT_SLIDE)"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin, DescType29Mixin


class TraversalDrawersingPurchaseDrawer(DescType29Mixin, AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT ds.[DRAWER] "
            "FROM dbo.articles a "
            "JOIN dbo.[DRAWERSING] ds "
            "  ON ds.NAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(a.INORDER)), N'') IS NULL "
            "  AND NULLIF(LTRIM(RTRIM(ds.INORDER)), N'') IS NULL "
            "  AND ds.FRONTTYPE = 0",
            (self.article,)
        )
        for row in rows:
            path = [f"DRAWERSING({self.article})"]
            drawer = normalize(row.get("DRAWER"))
            if drawer:
                self._resolve_then_type29(drawer, path + [f"DRAWERSING.DRAWER={drawer}"],
                                           self._purchase_drawer_branch)
        return self.result

    def _purchase_drawer_branch(self, value: str, path: list[str]) -> None:
        self._dr_front_branch_purchase(value, path)


def extract_drawersing_purchase_drawer(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalDrawersingPurchaseDrawer(article, max_depth).run()


FLOW_NAME = "DRAWERSING_PURCHASE_DRAWER"
extract = extract_drawersing_purchase_drawer


def extract_all_drawersing_purchase_drawer(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_drawersing_purchase_drawer(name, max_depth))
    return results


extract_all = extract_all_drawersing_purchase_drawer