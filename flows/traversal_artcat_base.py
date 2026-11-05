# Source : flows/traversal_artcat_base.py
# Analogy: Flow entry point — article category Sockel (Base) → lngsockl tree, plus the EinfuegeHoehe branch.
"""artcat_base flow: articles → ARTICLECATEGORY → ARTICLECATEGORYATTRVALUE (EinfuegeHoehe, Sockel) → lngsockl"""
from __future__ import annotations

from core.db import normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_LNGSOCKL
from flows.traversal_mixins import ArticleCategoryMixin, AnglprimMixin, ConnectionTreeMixin


class TraversalArtcatBase(ArticleCategoryMixin, AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        self._run_article_category("Sockel", STATE_LNGSOCKL)
        return self.result


def extract_artcat_base(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalArtcatBase(article, max_depth).run()


FLOW_NAME = "artcat_base"
extract = extract_artcat_base


def extract_all_artcat_base(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_artcat_base(name, max_depth))
    return results


extract_all = extract_all_artcat_base