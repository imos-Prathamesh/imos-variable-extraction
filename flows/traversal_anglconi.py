# Source : flows/traversal_anglconi.py
# Analogy: Flow 1 entry point — starts from anglconi.CONISITU, walks the full connection tree with IMOS and DESCRIPTOR resolution.
"""anglconi flow: articles.NAME → anglconi.CONISITU → IMOS/DESCRIPTOR/CONNECTIONS"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from flows.traversal_mixins import ConnectionTreeMixin
from core.branches import STATE_CONISITU


class TraversalAnglconi(ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT ac.CONISITU, ac.ELEMID, ac.SEQUENCENUM, ac.REVERSE "
            "FROM dbo.articles a "
            "JOIN dbo.anglconi ac "
            "  ON ac.NAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(a.INORDER)), N'') IS NULL "
            "  AND NULLIF(LTRIM(RTRIM(ac.INORDER)), N'') IS NULL "
            "ORDER BY ac.SEQUENCENUM, ac.ELEMID",
            (self.article,)
        )
        for row in rows:
            conisitu = normalize(row["CONISITU"])
            if conisitu is None:
                continue
            path = [f"anglconi({self.article})", f"CONISITU={conisitu}"]
            self._classify(conisitu, STATE_CONISITU, path, "anglconi", "CONISITU")
        return self.result


def extract_article(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglconi(article, max_depth).run()


FLOW_NAME = "anglconi"
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