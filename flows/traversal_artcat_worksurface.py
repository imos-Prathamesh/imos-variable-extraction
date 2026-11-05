# Source : flows/traversal_artcat_worksurface.py
# Analogy: Flow entry point — article category Arbeitsplatte (Worksurface) → lngarbpl tree, plus the EinfuegeHoehe branch.
"""artcat_worksurface flow: articles → ARTICLECATEGORY → ARTICLECATEGORYATTRVALUE (EinfuegeHoehe, Arbeitsplatte) → lngarbpl"""
from __future__ import annotations

from core.db import normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_LNGARBPL
from flows.traversal_mixins import ArticleCategoryMixin, AnglprimMixin, ConnectionTreeMixin


class TraversalArtcatWorksurface(ArticleCategoryMixin, AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        self._run_article_category("Arbeitsplatte", STATE_LNGARBPL)
        return self.result


def extract_artcat_worksurface(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalArtcatWorksurface(article, max_depth).run()


FLOW_NAME = "artcat_worksurface"
extract = extract_artcat_worksurface


def extract_all_artcat_worksurface(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_artcat_worksurface(name, max_depth))
    return results


extract_all = extract_all_artcat_worksurface