# Source : flows/traversal_anglzone_dwg.py
# Analogy: Flow entry point — anglzone.NAME -> DIVDIR='D' -> DWG_STRETCH=0
#   -> LINDIV1/LINDIV2/LINDIVZ (plain terminal values) AND
#   -> anglzone.NAME matched into ANGLMACH.ANGLNAME -> FACTOR=1 -> SDIAMETER/SDEEPNES
#      + ANGLMACH.NAME matched into PROFIL.NAME (reuses the existing PROFIL/contelem/RENDER/MAT chain).
"""anglzone_DWG flow: articles.NAME -> anglzone.NAME -> DIVDIR='D' -> DWG_STRETCH=0
   -> anglzone.LINDIV1/LINDIV2/LINDIVZ (terminal)
   -> anglzone.NAME -> ANGLMACH.ANGLNAME -> FACTOR=1 -> SDIAMETER/SDEEPNES (terminal)
      + ANGLMACH.NAME -> PROFIL.NAME (existing _profil_branch chain: contelem/RENDER/MAT)"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_TERMINAL
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin


class TraversalAnglzoneDwg(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT az.NAME, az.DIVDIR, az.DWG_STRETCH, "
            "       az.LINDIV1, az.LINDIV2, az.LINDIVZ "
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

            divdir = (normalize(row.get("DIVDIR")) or "").upper()
            if divdir != "D":
                continue

            if not self._int_in(row.get("DWG_STRETCH"), (0,)):
                continue

            for col in ("LINDIV1", "LINDIV2", "LINDIVZ"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"anglzone.{col}={val}"], "anglzone", col)

            nm = normalize(row.get("NAME"))
            if nm:
                self._anglmach_branch(nm, path + [f"anglzone.NAME={nm}"])
        return self.result


def extract_anglzone_dwg(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglzoneDwg(article, max_depth).run()


FLOW_NAME = "anglzone_DWG"
extract = extract_anglzone_dwg


def extract_all_anglzone_dwg(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_anglzone_dwg(name, max_depth))
    return results


extract_all = extract_all_anglzone_dwg