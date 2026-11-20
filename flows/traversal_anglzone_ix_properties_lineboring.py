# Source : flows/traversal_anglzone_ix_properties_lineboring.py
# Analogy: Flow entry point — anglzone.NAME -> LRFROMPAR=1 -> LRRADSHELF/LRRADCONN/LRRADSHEL2/LRRADCON2 (terminal).
"""anglzone_iX_Properties_Lineboring flow: articles.NAME -> anglzone.NAME -> LRFROMPAR=1
   -> LRRADSHELF, LRRADCONN, LRRADSHEL2, LRRADCON2 (terminal)"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_TERMINAL
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin


class TraversalAnglzoneIxPropertiesLineboring(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT az.NAME, az.LRFROMPAR, "
            "       az.LRRADSHELF, az.LRRADCONN, az.LRRADSHEL2, az.LRRADCON2 "
            "FROM dbo.articles a "
            "JOIN dbo.anglzone az "
            "  ON az.NAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(a.INORDER)), N'') IS NULL "
            "  AND NULLIF(LTRIM(RTRIM(az.INORDER)), N'') IS NULL",
            (self.article,)
        )
        for row in rows:
            path = [f"anglzone({self.article})"]

            if not self._int_in(row.get("LRFROMPAR"), (1,)):
                continue

            for col in ("LRRADSHELF", "LRRADCONN", "LRRADSHEL2", "LRRADCON2"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"anglzone.{col}={val}"], "anglzone", col)
        return self.result


def extract_anglzone_ix_properties_lineboring(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglzoneIxPropertiesLineboring(article, max_depth).run()


FLOW_NAME = "anglzone_iX_Properties_Lineboring"
extract = extract_anglzone_ix_properties_lineboring


def extract_all_anglzone_ix_properties_lineboring(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_anglzone_ix_properties_lineboring(name, max_depth))
    return results


extract_all = extract_all_anglzone_ix_properties_lineboring