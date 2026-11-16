# Source : flows/traversal_anglelem_cp_back.py
# Analogy: Flow entry point — anglelem (PARTTYPE='B', Back panel) → MANINFO/terminal cols (IMOS) + CPNAME → IMOS / DESCRIPTOR / CABBACK + CPCONNLIST.
"""anglelem_cp_back flow: articles.NAME -> anglelem.NAME (PARTTYPE='B') -> MANINFO/terminal cols + CPNAME -> IMOS / DESCRIPTOR / CABBACK + CPCONNLIST"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_TERMINAL, STATE_IDENT, STATE_CABBACK
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


class TraversalAnglelemCpBack(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

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

            if (normalize(row.get("PARTTYPE")) or "").upper() == "B":
                cpname = normalize(row.get("CPNAME"))
                if cpname:
                    self._classify(cpname, STATE_CABBACK, path + [f"anglelem.CPNAME={cpname}"],
                                   "anglelem", "CPNAME")
        return self.result


def extract_anglelem_cp_back(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglelemCpBack(article, max_depth).run()


FLOW_NAME = "anglelem_cp_back"
extract = extract_anglelem_cp_back


def extract_all_anglelem_cp_back(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_anglelem_cp_back(name, max_depth))
    return results


extract_all = extract_all_anglelem_cp_back