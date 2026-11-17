# Source : flows/traversal_anglelem_cp_flap_door.py
# Analogy: Flow entry point — anglelem (PARTTYPE='D', DOOR_CATEGORY=1, Flap Door) -> MANINFO/terminal cols (IMOS) + CPNAME -> DOOR (NOD=1,DJOIN=2) -> DOORSING (TUER_L + TUER_R) -> GRIFF -> PULLHEIGHT.
"""anglelem_cp_flap_door flow: articles.NAME -> anglelem.NAME (PARTTYPE='D', DOOR_CATEGORY=1) -> MANINFO/terminal cols + CPNAME -> DOOR (NOD=1,DJOIN=2) -> DOORSING (TUER_L/TUER_R) -> GRIFF -> PULLHEIGHT"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from core.branches import STATE_TERMINAL, STATE_IDENT, STATE_DOOR_FLAP
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


class TraversalAnglelemCpFlapDoor(AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        select_cols = ", ".join(
            f"ae.[{c}]" for c in ["PARTTYPE", "DOOR_CATEGORY", "MANINFO", "CPNAME"] + _TERMINAL_COLS
        )
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

            parttype = (normalize(row.get("PARTTYPE")) or "").upper()
            if parttype == "D" and self._int_in(row.get("DOOR_CATEGORY"), (1,)):
                cpname = normalize(row.get("CPNAME"))
                if cpname:
                    self._classify(cpname, STATE_DOOR_FLAP, path + [f"anglelem.CPNAME={cpname}"],
                                   "anglelem", "CPNAME")
        return self.result


def extract_anglelem_cp_flap_door(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglelemCpFlapDoor(article, max_depth).run()


FLOW_NAME = "anglelem_cp_flap_door"
extract = extract_anglelem_cp_flap_door


def extract_all_anglelem_cp_flap_door(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_anglelem_cp_flap_door(name, max_depth))
    return results


extract_all = extract_all_anglelem_cp_flap_door