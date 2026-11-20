# Source : flows/traversal_drawerzone_ix_properties_pd.py
# Analogy: Flow entry point — articles.NAME -> DRAWERZONE.NAME -> DIVISION/BMODEVAR/ONSETVAR
#   + INSETFRONT.. (terminal) + FRONTDEF=0 AND FRONTDEFVERT=0 -> ONSETLEFT/ONSETRIGHT
#   -> same NAME matched into DRAWERSING.NAME -> FRONTTHK/INSET.. (terminal)
#      + DRMANINFO/FRONTINFO -> ident, + FRONTPARTDEF -> $ -> IMOS -> raw -> KMS.NAME.
"""DRAWERZONE_IX_Properties_PD flow: articles.NAME -> DRAWERZONE.NAME
   -> DIVISION, BMODEVAR, ONSETVAR (terminal)
   -> INSETFRONT, INSETBACK, INSETLEFT, INSETRIGHT, INSETTOP, INSETBOT (terminal)
   -> FRONTDEF=0 AND FRONTDEFVERT=0 -> ONSETLEFT, ONSETRIGHT (terminal)
   -> same NAME -> DRAWERSING.NAME
      -> FRONTTHK, INSETFRONT, INSETBACK, INSETLEFT, INSETRIGHT, INSETTOP, INSETBOT (terminal)
      -> DRMANINFO, FRONTINFO -> ident
      -> FRONTPARTDEF -> $ -> IMOS -> raw -> KMS.NAME"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin


class TraversalDrawerzoneIxPropertiesPd(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT dz.NAME "
            "FROM dbo.articles a "
            "JOIN dbo.[DRAWERZONE] dz "
            "  ON dz.NAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(a.INORDER)), N'') IS NULL "
            "  AND NULLIF(LTRIM(RTRIM(dz.INORDER)), N'') IS NULL",
            (self.article,)
        )
        for row in rows:
            path = [f"DRAWERZONE({self.article})"]
            nm = normalize(row.get("NAME"))
            if nm:
                self._drawerzone_branch(nm, path + [f"DRAWERZONE.NAME={nm}"])
        return self.result


def extract_drawerzone_ix_properties_pd(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalDrawerzoneIxPropertiesPd(article, max_depth).run()


FLOW_NAME = "DRAWERZONE_IX_PROPERTIES_PD"
extract = extract_drawerzone_ix_properties_pd


def extract_all_drawerzone_ix_properties_pd(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_drawerzone_ix_properties_pd(name, max_depth))
    return results


extract_all = extract_all_drawerzone_ix_properties_pd