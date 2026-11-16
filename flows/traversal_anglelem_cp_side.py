# Source : flows/traversal_anglelem_cp_side.py
# Analogy: Flow entry point — anglelem (PARTTYPE='S', Side adder panel) → MANINFO/terminal cols (IMOS) + CPNAME → IMOS / DESCRIPTOR / CSIDE.
"""anglelem_cp_side flow: articles.NAME -> anglelem.NAME (PARTTYPE='S') -> MANINFO/terminal cols + CPNAME -> IMOS / DESCRIPTOR / CSIDE"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_TERMINAL, STATE_IDENT, STATE_CSIDE
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin

_TERMINAL_COLS = [
    "INSET", "SHELFINSET", "STARTOFFS", "ENDOFFS", "TOPOFFS", "BOTOFFS",
    "TOPSHOFF", "BOTSHOFF", "STATRVAR", "ENDTRVAR", "TOPTRVAR", "BOTTRVAR",
    "STATREAB", "TOPTREAB", "ENDTREAB", "BOTTREAB", "TOPOFFFOR", "BOTOFFFOR",
    "TSHOFFFOR", "BSHOFFFOR", "INCLINFOR", "ENDOFFFOR", "STAOFFFOR", "INSETFOR",
    "SHELFINFOR", "DIVIDINFOR", "FRATRVAR", "LFORMULA", "LFORMULA_FRA",
    "TS_OFFSET_FROM_ANGL", "BS_OFFSET_FROM_ANGL", "BOTOFF_FA", "TOPOFF_FA",
    "ENDOFF_FA", "STAOFF_FA", "INSET_FA",
]


class TraversalAnglelemCpSide(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        select_cols = ", ".join(f"ae.[{c}]" for c in ["PARTTYPE", "MANINFO", "CPNAME"] + _TERMINAL_COLS)
        rows = query(
            f"SELECT {select_cols} "
            "FROM dbo.articles a "
            "JOIN dbo.anglelem ae "
            "  ON ae.NAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(a.INORDER)), N'') IS NULL "
            "  AND NULLIF(LTRIM(RTRIM(ae.INORDER)), N'') IS NULL",
            (self.article,)
        )
        for row in rows:
            path = [f"anglelem({self.article})"]

            maninfo = normalize(row.get("MANINFO"))
            if maninfo:
                self._generic_branch(maninfo, STATE_IDENT, path + [f"anglelem.MANINFO={maninfo}"])

            for col in _TERMINAL_COLS:
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"anglelem.{col}={val}"], "anglelem", col)

            if (normalize(row.get("PARTTYPE")) or "").upper() == "S":
                cpname = normalize(row.get("CPNAME"))
                if cpname:
                    self._classify(cpname, STATE_CSIDE, path + [f"anglelem.CPNAME={cpname}"],
                                   "anglelem", "CPNAME")
        return self.result


def extract_anglelem_cp_side(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglelemCpSide(article, max_depth).run()


FLOW_NAME = "anglelem_cp_side"
extract = extract_anglelem_cp_side


def extract_all_anglelem_cp_side(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_anglelem_cp_side(name, max_depth))
    return results


extract_all = extract_all_anglelem_cp_side