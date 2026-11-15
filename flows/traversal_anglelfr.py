# Source : flows/traversal_anglelfr.py
# Analogy: Flow entry point — starts from ANGLELFR.NAME, splits into EN/TR/LFORMULA (IMOS-only) and CP (IMOS / DESCRIPTOR / BLENDE+CPCONNLIST) columns.
"""anglelfr flow: articles.NAME → ANGLELFR.NAME → EN/TR/LFORMULA cols (IMOS) + CP cols (IMOS / DESCRIPTOR / BLENDE+CPCONNLIST)"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_TERMINAL, STATE_ANGLELFR_CP
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin

_EN_TR_LFORMULA_COLS = [
    "LEFT_EN", "LEFT_TR", "RIGHT_EN", "RIGHT_TR", "BOTTOM_EN", "BOTTOM_TR",
    "TOP_EN", "TOP_TR", "DIVIDER_EN",
    "LFORMULA_LEF", "LFORMULA_TOP", "LFORMULA_RIG", "LFORMULA_BOT", "LFORMULA_DIV",
]

_CP_COLS = ["LEFT_CP", "RIGHT_CP", "BOTTOM_CP", "TOP_CP", "DIVIDER_CP"]


class TraversalAnglelfr(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        select_cols = ", ".join(f"ae.[{c}]" for c in _EN_TR_LFORMULA_COLS + _CP_COLS)
        rows = query(
            f"SELECT {select_cols} "
            "FROM dbo.articles a "
            "JOIN dbo.ANGLELFR ae "
            "  ON ae.NAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(a.INORDER)), N'') IS NULL "
            "  AND NULLIF(LTRIM(RTRIM(ae.INORDER)), N'') IS NULL",
            (self.article,)
        )
        for row in rows:
            path = [f"ANGLELFR({self.article})"]
            for col in _EN_TR_LFORMULA_COLS:
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"ANGLELFR.{col}={val}"], "ANGLELFR", col)
            for col in _CP_COLS:
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_ANGLELFR_CP, path + [f"ANGLELFR.{col}={val}"], "ANGLELFR", col)
        return self.result


def extract_anglelfr(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglelfr(article, max_depth).run()


FLOW_NAME = "anglelfr"
extract = extract_anglelfr


def extract_all_anglelfr(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_anglelfr(name, max_depth))
    return results


extract_all = extract_all_anglelfr