# Source : flows/traversal_anglprim.py
# Analogy: Flow entry point — starts from anglprim, routes ARTCALC / CONTOUR / FRONTNAME / BASECP into the KMS tree and the shared connection tree.
"""anglprim flow: articles.NAME → anglprim.NAME → ARTCALC / DIMCALC / CONTOUR / FRONTNAME / BASECP / BAFIXHFOR"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_TERMINAL
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin


class TraversalAnglprim(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT ap.ARTCALC1, ap.ARTCALC2, ap.ARTCALC3, ap.BAINSERT, ap.BAHEIGHT, "
            "       ap.BASECP, ap.BAFIXHFOR, ap.CONTOUR, "
            "       ap.DIMCALCFX, ap.DIMCALCFY, ap.DIMCALCFZ, ap.FRONTNAME "
            "FROM dbo.articles a "
            "JOIN dbo.anglprim ap "
            "  ON ap.NAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(a.INORDER)), N'') IS NULL "
            "  AND NULLIF(LTRIM(RTRIM(ap.INORDER)), N'') IS NULL",
            (self.article,)
        )
        for row in rows:
            base = [f"anglprim({self.article})"]

            for col in ("DIMCALCFX", "DIMCALCFY", "DIMCALCFZ"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, base + [f"anglprim.{col}={val}"], "anglprim", col)

            for col in ("ARTCALC1", "ARTCALC2", "ARTCALC3"):
                val = normalize(row.get(col))
                if val:
                    self._artcalc_branch(val, base + [f"anglprim.{col}={val}"])

            contour = normalize(row.get("CONTOUR"))
            if contour:
                self._contelem_branch(contour, base + [f"anglprim.CONTOUR={contour}"])

            front = normalize(row.get("FRONTNAME"))
            if front:
                self._resolve_then(front, base + [f"anglprim.FRONTNAME={front}"], self._design_branch)

            if self._int_in(row.get("BAINSERT"), (2,)):
                basecp = normalize(row.get("BASECP"))
                if basecp:
                    self._resolve_then(basecp, base + [f"anglprim.BASECP={basecp}"], self._lngsockl_branch)

            if self._int_in(row.get("BAHEIGHT"), (2,)):
                fixh = normalize(row.get("BAFIXHFOR"))
                if fixh:
                    self._classify(fixh, STATE_TERMINAL, base + [f"anglprim.BAFIXHFOR={fixh}"], "anglprim", "BAFIXHFOR")
        return self.result


def extract_anglprim(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglprim(article, max_depth).run()


FLOW_NAME = "anglprim"
extract = extract_anglprim


def extract_all_anglprim(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_anglprim(name, max_depth))
    return results


extract_all = extract_all_anglprim