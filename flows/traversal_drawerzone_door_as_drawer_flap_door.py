# Source : flows/traversal_drawerzone_door_as_drawer_flap_door.py
# Analogy: Flow entry point — articles.NAME -> DRAWERSING.NAME (FRONTTYPE=1) -> DRAWER -> $ -> IMOS -> raw -> DOOR.NAME (reuses existing _door_branch_flap).
"""DRAWERZONE_DOOR_AS_DRAWER_PRINCIPLE_Flap_Door flow:
   articles.NAME -> DRAWERSING.NAME
   -> WHERE DRAWERSING.FRONTTYPE=1 -> DRAWER
   -> $ -> IMOS -> raw -> DOOR.NAME (existing DOOR(flap)/DOORSING/GRIFF/PULLHEIGHT logic)"""
from __future__ import annotations

from core.db import query, normalize
from core.traversal_base import BaseTraversal, ExtractionResult
from flows.traversal_mixins import AnglprimMixin, ConnectionTreeMixin, DescType26Mixin


class TraversalDrawerzoneDoorAsDrawerFlapDoor(DescType26Mixin, AnglprimMixin, ConnectionTreeMixin, BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT ds.[DRAWER] "
            "FROM dbo.articles a "
            "JOIN dbo.[DRAWERSING] ds "
            "  ON ds.NAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(a.INORDER)), N'') IS NULL "
            "  AND NULLIF(LTRIM(RTRIM(ds.INORDER)), N'') IS NULL "
            "  AND ds.FRONTTYPE = 1",
            (self.article,)
        )
        for row in rows:
            path = [f"DRAWERSING({self.article})"]
            drawer = normalize(row.get("DRAWER"))
            if drawer:
                self._resolve_then_type26(drawer, path + [f"DRAWERSING.DRAWER={drawer}"], self._door_branch_flap)
        return self.result


def extract_drawerzone_door_as_drawer_flap_door(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalDrawerzoneDoorAsDrawerFlapDoor(article, max_depth).run()


FLOW_NAME = "DRAWERZONE_DOOR_AS_DRAWER_PRINCIPLE_Flap_Door"
extract = extract_drawerzone_door_as_drawer_flap_door


def extract_all_drawerzone_door_as_drawer_flap_door(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_drawerzone_door_as_drawer_flap_door(name, max_depth))
    return results


extract_all = extract_all_drawerzone_door_as_drawer_flap_door