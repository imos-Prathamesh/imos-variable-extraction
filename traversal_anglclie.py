"""anglclie flow: articles.NAME → anglclie.TAGVALUE → IMOS loop"""
from __future__ import annotations

from db import query, normalize
from traversal_base import BaseTraversal, ExtractionResult
from traversal_mixins import ImosMixin


class TraversalAnglclie(ImosMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT ac.TAGVALUE "
            "FROM dbo.articles a "
            "JOIN dbo.anglclie ac "
            "  ON ac.NAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(ac.INORDER)), N'') IS NULL",
            (self.article,)
        )
        for row in rows:
            tagvalue = normalize(row["TAGVALUE"])
            if tagvalue:
                path = [f"anglclie({self.article})", f"TAGVALUE={tagvalue}"]
                self._classify_imos_loop(tagvalue, path)
        return self.result


def extract_anglclie(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglclie(article, max_depth).run()