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
    Branch,
)


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
    cols = ", ".join([branch.match_column] + branch.value_columns)
    sql = (
        f"SELECT {cols} FROM dbo.[{branch.match_table}] "
        f"WHERE [{branch.match_column}] = ? "
        f"  AND {_blank_filter(branch.filter_column)} "
        f"{order}"
    )
    return query(sql, (value,))


def _fetch_imos(name: str) -> list[str]:
    rows = query(
        "SELECT WERT FROM dbo.[IMOS] "
        "WHERE NAME = ? AND NULLIF(LTRIM(RTRIM(ORDERID)), N'') IS NULL",
        (name,)
    )
    return [normalize(r["WERT"]) for r in rows if normalize(r["WERT"]) is not None]


def _fetch_descriptor(name: str) -> list[str]:
    rows = query(
        "SELECT LINDIV FROM dbo.[DESCRIPTORVALUES] "
        "WHERE NAME = ? "
        "ORDER BY NODENUM, CONDITIONID",
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
            if not wert_values:
                self._record(varname, "[NOT IN IMOS]", new_path, "IMOS", "WERT", "UNRESOLVED")
            for wert in wert_values:
                rec_path = new_path + [f"WERT={wert}"]
                self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                self._classify(wert, STATE_CONNECTIONS, rec_path, "IMOS", "WERT")
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
                self._classify(lindiv, STATE_CONNECTIONS, rec_path,
                               "DESCRIPTORVALUES", "LINDIV")
            self._active.discard(state_key)

        if pv.is_raw:
            if state == STATE_CONNECTIONS:
                self._enter_connections(value, path, source_table, source_column)
            elif state == STATE_TERMINAL:
                pass
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