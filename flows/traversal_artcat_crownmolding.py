# Source : flows/traversal_artcat_crownmolding.py
# Analogy: Flow entry point — article category Kranzleiste (Crown Molding / Cornice) → lngkranl tree, plus the EinfuegeHoehe branch.
"""artcat_crownmolding flow: articles → ARTICLECATEGORY → ARTICLECATEGORYATTRVALUE (EinfuegeHoehe, Kranzleiste) → lngkranl"""
from __future__ import annotations

from core.db import normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_LNGKRANL
from flows.traversal_mixins import ArticleCategoryMixin, AnglprimMixin, ConnectionTreeMixin


class TraversalArtcatCrownMolding(ArticleCategoryMixin, AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        self._run_article_category("Kranzleiste", STATE_LNGKRANL)
        return self.result


def extract_artcat_crownmolding(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalArtcatCrownMolding(article, max_depth).run()


FLOW_NAME = "artcat_crownmolding"
extract = extract_artcat_crownmolding


def extract_all_artcat_crownmolding(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_artcat_crownmolding(name, max_depth))
    return results


extract_all = extract_all_artcat_crownmolding