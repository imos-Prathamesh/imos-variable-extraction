# Source : flows/traversal_drawersing_inhouse_drawer.py
# Analogy: Flow entry point — articles.NAME -> DRAWERSING.NAME (FRONTTYPE=0) -> DRAWER -> $ -> IMOS -> raw -> DR_FRONT + dranglelem (new tables).
"""DRAWERSING_INHOUSE_DRAWER flow:
   articles.NAME -> DRAWERSING.NAME
   -> WHERE DRAWERSING.FRONTTYPE=0 -> DRAWER
   -> $ -> IMOS -> raw -> DR_FRONT.NAME (SET_FRONT=1 gated: THKSTR/PART_INFO/PART_DEF/CONNSIT_PULL*)
                 + dranglelem.NAME (CPNAME -> CSIDE)"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin, DescType26Mixin


class TraversalDrawersingInhouseDrawer(DescType26Mixin, AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

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
                self._resolve_then_type26(drawer, path + [f"DRAWERSING.DRAWER={drawer}"],
                                           self._inhouse_drawer_branch)
        return self.result

    def _inhouse_drawer_branch(self, value: str, path: list[str]) -> None:
        self._dr_front_branch(value, path)
        self._dranglelem_branch(value, path)


def extract_drawersing_inhouse_drawer(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalDrawersingInhouseDrawer(article, max_depth).run()


FLOW_NAME = "DRAWERSING_INHOUSE_DRAWER"
extract = extract_drawersing_inhouse_drawer


def extract_all_drawersing_inhouse_drawer(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_drawersing_inhouse_drawer(name, max_depth))
    return results


extract_all = extract_all_drawersing_inhouse_drawer