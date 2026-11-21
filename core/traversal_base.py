# Source : core/traversal_base.py
# Analogy: Car engine — the core recursive logic (IMOS lookup, descriptor lookup, cycle detection) that powers every flow. Never runs alone.
"""
Shared base for all IMOS traversal flows.
Each flow subclasses BaseTraversal and implements only run().
"""
from __future__ import annotations

from dataclasses import dataclass, field

from core.db import query, normalize
from core.parser import parse
from core.branches import (
    BRANCHES,
    STATE_CONISITU, STATE_CONNECTIONS,
    STATE_CONNSELTREE, STATE_CONNDESC, STATE_CONNEXTRA,
    STATE_CONNGROUPS, STATE_WORKGROUP_PRF, STATE_WORKGROUP_CONT,
    STATE_PROFIL, STATE_PROFIL_GEOM, STATE_RENDER,
    STATE_CONTELEM, STATE_NUT_ERB, STATE_EXTRUPAR, STATE_EXTRUCON,
    STATE_IDENT, STATE_DESCRIPTOR, STATE_IMOS, STATE_TERMINAL,
    STATE_ANGLELFR_CP, STATE_CSIDE, STATE_CABBACK,
    STATE_DOOR, STATE_DOORSING, STATE_GRIFF, STATE_PULLHEIGHT,
    STATE_DOOR_FLAP, STATE_DOOR_DOUBLE,
    STATE_IMOSDOORSINFO, STATE_IMOSDOORSINGLE,
    STATE_IMOSDOORSINFO_BIFOLD, STATE_IMOSDOORSINGLE_BIFOLD,
    STATE_IMOSDOORSINFO_FOLDSLIDE, STATE_IMOSDOORSINGLE_FOLDSLIDE,
    STATE_IMOSDOORSINFO_TAMBOUR_V, STATE_IMOSDOORSINFO_TAMBOUR_H,
    STATE_ANGLZONE, STATE_CABIN,
    STATE_ANGLZONE_RAIL, STATE_CABIN_RAIL, STATE_TRAVERSE_RAIL,
    STATE_ANGLZONE_PANEL_SHELF, STATE_ANGLZONE_RAIL_SHELF,
    STATE_ANGLZONE_FIX_PANEL_SHELF, STATE_ANGLZONE_FIX_RAIL_SHELF,
    STATE_CABIN_FIX_PANEL_SHELF, STATE_CABIN_FIX_RAIL_SHELF,
    STATE_TRAVERSE_FIX_RAIL_SHELF,
    STATE_ANGLZONE_ADJUSTABLE_SHELF, STATE_CABIN_ADJUSTABLE_SHELF,
    STATE_ANGLZONE_PARTITION,
    STATE_ANGLZONE_SIDE_PARTITION,
    Branch,
)

# Module-level call stack for article re-entry (used only by flows that
# explicitly call BaseTraversal._reenter_as_article). Shared across nested
# extract() calls so cycles are caught even though each re-entered flow run
# creates a brand-new BaseTraversal instance. No existing flow touches this.
_ARTICLE_REENTRY_STACK: list[str] = []


# ─── result records ───────────────────────────────────────────────────────────

@dataclass
class OccurrenceRow:
    article: str
    path: list[str]
    variable_name: str
    value: str
    source_table: str
    source_column: str
    resolved_via: str   # DIRECT / IMOS / DESCRIPTOR
    flow_name: str = ""  # which flow produced this occurrence (set by the UI/CLI caller)

    def path_str(self) -> str:
        return " → ".join(self.path)


@dataclass
class ExtractionResult:
    article: str
    occurrences: list[OccurrenceRow] = field(default_factory=list)
    unique_vars: dict[str, str] = field(default_factory=dict)
    cycles: list[str] = field(default_factory=list)


# ─── shared DB helpers ────────────────────────────────────────────────────────

def _blank_filter(col: str) -> str:
    return f"NULLIF(LTRIM(RTRIM({col})), N'') IS NULL"


def _fetch_branch(branch: Branch, value: str) -> list[dict]:
    order = ""
    if branch.order_columns:
        order = "ORDER BY " + ", ".join(branch.order_columns)
    cols = ", ".join(f"[{c}]" for c in [branch.match_column] + branch.value_columns)
    sql = (
        f"SELECT {cols} FROM dbo.[{branch.match_table}] "
        f"WHERE [{branch.match_column}] = ? "
        f"  AND {_blank_filter(branch.filter_column)} "
        f"{order}"
    )
    return query(sql, (value,))


def _fetch_imos(name: str) -> list[str] | None:
    rows = query(
        "SELECT WERT FROM dbo.[IMOS] "
        "WHERE NAME = ? AND NULLIF(LTRIM(RTRIM(ORDERID)), N'') IS NULL",
        (name,)
    )
    if not rows:
        return None
    return [normalize(r["WERT"]) or "[BLANK]" for r in rows]


def _fetch_descriptor(name: str) -> list[str]:
    desc_rows = query(
        "SELECT DESC_TYPE FROM dbo.[DESCRIPTOR] "
        "WHERE NAME = ? AND NULLIF(LTRIM(RTRIM(INORDER)), N'') IS NULL",
        (name,)
    )
    if not desc_rows:
        return []

    try:
        is_type_11 = int(desc_rows[0].get("DESC_TYPE")) == 11
    except (TypeError, ValueError):
        is_type_11 = False

    if is_type_11:
        rows = query(
            "SELECT dv.LINDIV FROM dbo.[DESCRIPTORVALUES] dv "
            "WHERE dv.NAME = ? "
            "ORDER BY dv.NODENUM, dv.CONDITIONID",
            (name,)
        )
    else:
        rows = query(
            "SELECT dv.LINDIV FROM dbo.[DESCRIPTORVALUES] dv "
            "WHERE dv.NAME = ? AND dv.COMMENT = 'DEFAULT' "
            "ORDER BY dv.NODENUM, dv.CONDITIONID",
            (name,)
        )

    out = []
    for r in rows:
        v = normalize(r["LINDIV"])
        if v:
            out.append(v)
    return out


# ─── base traversal engine ────────────────────────────────────────────────────

class BaseTraversal:
    """
    Subclass this for each flow. Override run() with the flow-specific
    entry query. Mix in ConnectionTreeMixin or ImosMixin from traversal_mixins
    for shared traversal patterns.
    """

    def __init__(self, article: str, max_depth: int = 40):
        self.article = article
        self.max_depth = max_depth
        self.result = ExtractionResult(article=article)
        self._active: set[tuple[str, str]] = set()

    def run(self) -> ExtractionResult:
        raise NotImplementedError("Subclass must implement run()")

    # ── classify: the recursive heart ─────────────────────────────────────────

    def _classify(
        self,
        value: str,
        state: str,
        path: list[str],
        source_table: str,
        source_column: str,
    ) -> None:
        if len(path) > self.max_depth:
            return

        pv = parse(value)
        if pv is None:
            return

        for varname in pv.variables:
            state_key = (STATE_IMOS, varname)
            if state_key in self._active:
                self.result.cycles.append(
                    f"CYCLE: {' → '.join(path)} → $IMOS({varname})"
                )
                continue
            self._active.add(state_key)
            new_path = path + [f"$IMOS({varname})"]
            wert_values = _fetch_imos(varname)
            if wert_values is None:
                self._record(varname, "[NOT IN IMOS]", new_path, "IMOS", "WERT", "UNRESOLVED")
            else:
                for wert in wert_values:
                    rec_path = new_path + [f"WERT={wert}"]
                    self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                    if wert != "[BLANK]":
                        self._classify(wert, state, rec_path, "IMOS", "WERT")
            self._active.discard(state_key)

        for descname in pv.descriptors:
            state_key = (STATE_DESCRIPTOR, descname)
            if state_key in self._active:
                self.result.cycles.append(
                    f"CYCLE: {' → '.join(path)} → #DESCRIPTOR({descname})"
                )
                continue
            self._active.add(state_key)
            new_path = path + [f"#DESCRIPTOR({descname})"]
            lindiv_values = _fetch_descriptor(descname)
            for lindiv in lindiv_values:
                rec_path = new_path + [f"LINDIV={lindiv}"]
                self._classify(lindiv, state, rec_path,
                               "DESCRIPTORVALUES", "LINDIV")
            self._active.discard(state_key)

        if pv.is_raw:
            self._classify_raw_dispatch(value, state, path, source_table, source_column)

    def _classify_raw_dispatch(
        self,
        value: str,
        state: str,
        path: list[str],
        source_table: str,
        source_column: str,
    ) -> None:
        if True:
            if state == STATE_CONNECTIONS:
                self._enter_connections(value, path, source_table, source_column)
            elif state == STATE_TERMINAL:
                pass
            elif state == STATE_ANGLELFR_CP:
                self._blende_branch(value, path)
                self._cpconnlist_branch(value, path)
            elif state == STATE_CSIDE:
                self._cside_branch(value, path)
            elif state == STATE_CABBACK:
                self._cabback_branch(value, path)
                self._cpconnlist_branch_type4(value, path)
            elif state == STATE_DOOR:
                self._door_branch(value, path)
            elif state == STATE_DOOR_FLAP:
                self._door_branch_flap(value, path)
            elif state == STATE_DOOR_DOUBLE:
                self._door_branch_double(value, path)
            elif state == STATE_IMOSDOORSINFO:
                self._imosdoorsinfo_branch(value, path)
            elif state == STATE_IMOSDOORSINFO_BIFOLD:
                self._imosdoorsinfo_branch_bifold(value, path)
            elif state == STATE_IMOSDOORSINFO_FOLDSLIDE:
                self._imosdoorsinfo_branch_foldslide(value, path)
            elif state == STATE_IMOSDOORSINFO_TAMBOUR_V:
                self._imosdoorsinfo_branch_tambour(value, path, 3)
            elif state == STATE_IMOSDOORSINFO_TAMBOUR_H:
                self._imosdoorsinfo_branch_tambour(value, path, 4)
            elif state == STATE_ANGLZONE:
                self._anglzone_branch(value, path)
            elif state == STATE_CABIN:
                self._cabin_branch(value, path)
            elif state == STATE_ANGLZONE_RAIL:
                self._anglzone_branch_rail(value, path)
            elif state == STATE_CABIN_RAIL:
                self._cabin_branch_rail(value, path)
            elif state == STATE_ANGLZONE_PANEL_SHELF:
                self._anglzone_branch_panel_shelf(value, path)
            elif state == STATE_ANGLZONE_RAIL_SHELF:
                self._anglzone_branch_rail_shelf(value, path)
            elif state == STATE_ANGLZONE_FIX_PANEL_SHELF:
                self._anglzone_branch_fix_panel_shelf(value, path)
            elif state == STATE_ANGLZONE_FIX_RAIL_SHELF:
                self._anglzone_branch_fix_rail_shelf(value, path)
            elif state == STATE_CABIN_FIX_PANEL_SHELF:
                self._cabin_branch_fix_panel_shelf(value, path)
            elif state == STATE_CABIN_FIX_RAIL_SHELF:
                self._cabin_branch_fix_rail_shelf(value, path)
            elif state == STATE_ANGLZONE_ADJUSTABLE_SHELF:
                self._anglzone_branch_adjustable_shelf(value, path)
            elif state == STATE_CABIN_ADJUSTABLE_SHELF:
                self._cabin_branch_adjustable_shelf(value, path)
            elif state == STATE_ANGLZONE_PARTITION:
                self._anglzone_branch_partition(value, path)
            elif state == STATE_ANGLZONE_SIDE_PARTITION:
                self._anglzone_branch_side_partition(value, path)
            elif state == STATE_DOORSING:
                self._doorsing_branch(value, path)
            elif state == STATE_GRIFF:
                self._griff_branch(value, path)
            elif state == STATE_PULLHEIGHT:
                self._pullheight_branch(value, path)
            else:
                branch = BRANCHES.get(state)
                if branch is not None:
                    self._generic_branch(value, state, path)
                else:
                    self._enter_connections(value, path, source_table, source_column)

    # ── record helper ─────────────────────────────────────────────────────────

    def _record(
        self,
        varname: str,
        value: str,
        path: list[str],
        source_table: str,
        source_column: str,
        resolved_via: str,
    ) -> None:
        self.result.occurrences.append(OccurrenceRow(
            article=self.article,
            path=list(path),
            variable_name=varname,
            value=value,
            source_table=source_table,
            source_column=source_column,
            resolved_via=resolved_via,
        ))
        self.result.unique_vars[varname] = value

    # ── article re-entry: opt-in only, no other flow calls this ──────────────

    def _reenter_as_article(self, value: str, path: list[str]) -> None:
        """
        Treat `value` as a brand-new articles.NAME and run it through every
        flow currently registered in core.flow_registry (existing ones today,
        and any new articles.NAME-starting flow added later with zero code
        change here). Results are merged into this same self.result.
        Purely additive: no existing flow calls this, so no existing flow's
        behavior changes.
        """
        if not value:
            return
        if value in _ARTICLE_REENTRY_STACK:
            self.result.cycles.append(f"CYCLE: {' → '.join(path)} → ARTICLE({value})")
            return
        if len(_ARTICLE_REENTRY_STACK) >= self.max_depth:
            return

        _ARTICLE_REENTRY_STACK.append(value)
        try:
            from core.flow_registry import get_registry
            registry = get_registry()
            for flow_name, info in sorted(registry.items()):
                try:
                    sub_result = info.extract(value, self.max_depth)
                except Exception:
                    continue
                self.result.occurrences.extend(sub_result.occurrences)
                self.result.unique_vars.update(sub_result.unique_vars)
                self.result.cycles.extend(sub_result.cycles)
        finally:
            _ARTICLE_REENTRY_STACK.pop()