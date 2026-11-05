# Source : flows/traversal_artcat_lightvalance.py
# Analogy: Flow entry point — article category Lichtleiste (Light Valance) → lnglichl tree, plus the EinfuegeHoehe branch.
"""artcat_lightvalance flow: articles → ARTICLECATEGORY → ARTICLECATEGORYATTRVALUE (EinfuegeHoehe, Lichtleiste) → lnglichl"""
from __future__ import annotations

from core.db import normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_LNGLICHL
from flows.traversal_mixins import ArticleCategoryMixin, AnglprimMixin, ConnectionTreeMixin


class TraversalArtcatLightValance(ArticleCategoryMixin, AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        self._run_article_category("Lichtleiste", STATE_LNGLICHL)
        return self.result


def extract_artcat_lightvalance(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalArtcatLightValance(article, max_depth).run()


FLOW_NAME = "artcat_lightvalance"
extract = extract_artcat_lightvalance


def extract_all_artcat_lightvalance(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_artcat_lightvalance(name, max_depth))
    return results


extract_all = extract_all_artcat_lightvalance