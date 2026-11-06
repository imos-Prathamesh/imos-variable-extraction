# Source : flows/traversal_anglmach.py
# Analogy: Flow entry point — starts from ANGLMACH.ANGLNAME, extracts the value columns and routes NAME into PROFIL (or WORKGROUP when TYPE=4 and ZETYPE<>Z).
"""anglmach flow: articles.NAME → ANGLMACH.ANGLNAME → value columns + NAME → PROFIL / WORKGROUP"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin

_VALUE_COLS = [
    "DIAMETER", "WIDTH", "DEEPNES", "OFFSET", "FACTOR", "ENDFORM", "GRANGLE", "ZEICHN",
    "SPLINX", "SPLINY", "SPLINZ", "EPLINX", "EPLINY", "EPLINZ", "DISTANCE", "ANGLE",
    "SDIAMETER", "SDEEPNES", "COUNTERSINK_H", "COUNTERSINK_B",
    "SCOUNTERSINK_H", "SCOUNTERSINK_B", "SWIDTH",
]


class TraversalAnglmach(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        select_cols = ", ".join(f"am.[{c}]" for c in ["NAME", "ZETYPE", "TYPE"] + _VALUE_COLS)
        rows = query(
            f"SELECT am.ANGLNAME, {select_cols} "
            "FROM dbo.articles a "
            "JOIN dbo.ANGLMACH am "
            "  ON am.ANGLNAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(a.INORDER)), N'') IS NULL "
            "  AND NULLIF(LTRIM(RTRIM(am.INORDER)), N'') IS NULL",
            (self.article,)
        )
        for row in rows:
            path = [f"ANGLMACH({self.article})"]
            self._terminal_cols(row, _VALUE_COLS, "ANGLMACH", path)
            nm = normalize(row.get("NAME"))
            if not nm:
                continue
            npath = path + [f"ANGLMACH.NAME={nm}"]
            is_z = (normalize(row.get("ZETYPE")) or "").upper() == "Z"
            typ = row.get("TYPE")
            if is_z:
                self._resolve_then_profil(nm, npath)
            elif self._int_in(typ, (4,)):
                self._workgroup_branch(nm, npath)
            else:
                self._resolve_then_profil(nm, npath)
                if self._int_in(typ, (10,)):
                    self._contelem_branch(nm, npath, include_profile=True)
        return self.result


def extract_article(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglmach(article, max_depth).run()


FLOW_NAME = "anglmach"
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