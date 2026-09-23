# Source : flows/traversal_anglmach.py
# Analogy: New flow entry point — starts from ANGLMACH.ANGLNAME, extracts SDIAMETER/SDEEPNES directly and routes NAME into the existing PROFIL resolution chain.
"""anglmach flow: articles.NAME → ANGLMACH.ANGLNAME → SDIAMETER/SDEEPNES + PROFIL"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from flows.traversal_mixins import ConnectionTreeMixin
from core.branches import STATE_TERMINAL


class TraversalAnglmach(ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT am.ANGLNAME, am.SDIAMETER, am.SDEEPNES, am.NAME "
            "FROM dbo.articles a "
            "JOIN dbo.ANGLMACH am "
            "  ON am.ANGLNAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(a.INORDER)), N'') IS NULL "
            "  AND NULLIF(LTRIM(RTRIM(am.INORDER)), N'') IS NULL",
            (self.article,)
        )
        for row in rows:
            path = [f"ANGLMACH({self.article})"]
            for col in ("SDIAMETER", "SDEEPNES"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"ANGLMACH.{col}={val}"], "ANGLMACH", col)
            nm = normalize(row.get("NAME"))
            if nm:
                self._resolve_then_profil(nm, path + [f"ANGLMACH.NAME={nm}"])
        return self.result


def extract_article(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglmach(article, max_depth).run()


FLOW_NAME = "anglmach"
extract = extract_article


def extract_all_articles(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_article(name, max_depth))
    return results


extract_all = extract_all_articles