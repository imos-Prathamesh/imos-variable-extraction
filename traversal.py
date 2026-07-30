"""
State-aware IMOS graph traversal engine.

Flow summary
─────────────
articles.NAME
  → anglconi (INORDER blank/NULL)
      → anglconi.CONISITU
          → classify()
              ├── $ → IMOS.NAME (ORDERID blank/NULL) → IMOS.WERT → classify()
              ├── # → DESCRIPTOR → DESCRIPTORVALUES.LINDIV → classify()
              └── raw → CONNECTIONS.NAME (INORDER blank/NULL)
                          → typed sub-branches
                              → extrucon.CONNAME raw → back to CONNECTIONS
                              → extrucon.CONNAME $  → IMOS → classify()

Outputs
───────
occurrences : every (article, path, variable, value) row in traversal order
unique_vars : per article, deduplicated {variable_name: last_value}
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from db import query, normalize
from parser import parse, ParsedValue
from branches import (
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


# ─── helpers ──────────────────────────────────────────────────────────────────

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


# ─── traversal engine ─────────────────────────────────────────────────────────

class Traversal:
    def __init__(self, article: str, max_depth: int = 40):
        self.article = article
        self.max_depth = max_depth
        self.result = ExtractionResult(article=article)
        # active-path state set: (state, value) tuples on current DFS stack
        self._active: set[tuple[str, str]] = set()

    # ── public entry ──────────────────────────────────────────────────────────

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT ac.CONISITU, ac.ELEMID, ac.SEQUENCENUM, ac.REVERSE "
            "FROM dbo.articles a "
            "JOIN dbo.anglconi ac "
            "  ON ac.NAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(ac.INORDER)), N'') IS NULL "
            "ORDER BY ac.SEQUENCENUM, ac.ELEMID",
            (self.article,)
        )
        if not rows:
            return self.result

        for row in rows:
            conisitu = normalize(row["CONISITU"])
            if conisitu is None:
                continue
            path = [f"anglconi({self.article})", f"CONISITU={conisitu}"]
            self._classify(conisitu, STATE_CONISITU, path, "anglconi", "CONISITU")

        return self.result

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

        # ── $ variable(s) ─────────────────────────────────────────────────────
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

        # ── # descriptor(s) ───────────────────────────────────────────────────
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

        # ── raw value → CONNECTIONS.NAME ──────────────────────────────────────
        if pv.is_raw:
            self._enter_connections(value, path, source_table, source_column)

    # ── connection entry ──────────────────────────────────────────────────────

    def _enter_connections(
        self,
        value: str,
        path: list[str],
        source_table: str,
        source_column: str,
    ) -> None:
        state_key = (STATE_CONNECTIONS, value)
        if state_key in self._active:
            self.result.cycles.append(
                f"CYCLE: {' → '.join(path)} → CONNECTIONS({value})"
            )
            return
        self._active.add(state_key)

        conn_rows = query(
            "SELECT * FROM dbo.[CONNECTIONS] "
            "WHERE NAME = ? AND NULLIF(LTRIM(RTRIM(INORDER)), N'') IS NULL "
            "ORDER BY CONNUM",
            (value,)
        )
        new_path = path + [f"CONNECTIONS({value})"]

        for row in conn_rows:
            self._process_connections_row(row, new_path)

        self._active.discard(state_key)

    def _process_connections_row(self, row: dict, path: list[str]) -> None:
        name = normalize(row.get("NAME"))

        # CONNSELTREE
        self._branch_lookup(
            name, STATE_CONNSELTREE, path,
            lambda child_rows: [
                (normalize(r["CHILDID"]), r)
                for r in child_rows
                if normalize(r.get("CHILDID"))
            ],
        )

        # CONNDESC
        self._generic_branch(name, STATE_CONNDESC, path)

        # CONNEXTRA
        self._generic_branch(name, STATE_CONNEXTRA, path)

        # CONNGROUPS → WORKGROUP
        self._conngroups_to_workgroup(name, path)

        # Groove → nut_erb
        groove = normalize(row.get("GROOVE"))
        if groove:
            groove_path = path + [f"GROOVE={groove}"]
            self._generic_branch(groove, STATE_NUT_ERB, groove_path)

        # LINDIV / LINDIV2 / ROTATION / POSPART0VAR / SNAPRADI / VARIANT
        for col in ("LINDIV", "LINDIV2", "ROTATION", "POSPART0VAR", "SNAPRADI", "VARIANT"):
            val = normalize(row.get(col))
            if val:
                sub_path = path + [f"{col}={val}"]
                self._classify(val, STATE_CONNECTIONS, sub_path, "CONNECTIONS", col)

        # extrupar branch
        self._generic_branch(name, STATE_EXTRUPAR, path)

    # ── generic branch helper ─────────────────────────────────────────────────

    def _generic_branch(self, name: str | None, state_key: str, path: list[str]) -> None:
        if not name:
            return
        branch = BRANCHES.get(state_key)
        if branch is None:
            return
        rows = _fetch_branch(branch, name)
        for row in rows:
            for col in branch.value_columns:
                val = normalize(row.get(col))
                if val:
                    sub_path = path + [f"{branch.label}.{col}={val}"]
                    self._classify(val, branch.next_state, sub_path,
                                   branch.match_table, col)

    def _branch_lookup(self, name, state_key, path, row_extractor):
        """Generic branch with custom row-value extractor."""
        if not name:
            return
        branch = BRANCHES.get(state_key)
        if branch is None:
            return
        rows = _fetch_branch(branch, name)
        for val, row in row_extractor(rows):
            sub_path = path + [f"{branch.label}={val}"]
            self._classify(val, branch.next_state, sub_path,
                           branch.match_table, branch.value_columns[0])

    # ── CONNGROUPS → WORKGROUP ────────────────────────────────────────────────

    def _conngroups_to_workgroup(self, name: str | None, path: list[str]) -> None:
        if not name:
            return
        branch = BRANCHES[STATE_CONNGROUPS]
        rows = _fetch_branch(branch, name)
        for row in rows:
            grp = normalize(row.get("CONNGROUP"))
            if not grp:
                continue
            grp_path = path + [f"CONNGROUPS.CONNGROUP={grp}"]

            # WORKGROUP PRF → PROFIL
            wg_rows = query(
                "SELECT NAME, PRF, CONTOUR FROM dbo.[WORKGROUP] "
                "WHERE NAME = ? AND NULLIF(LTRIM(RTRIM(INORDER)), N'') IS NULL",
                (grp,)
            )
            for wrow in wg_rows:
                prf = normalize(wrow.get("PRF"))
                contour = normalize(wrow.get("CONTOUR"))

                if prf:
                    prf_path = grp_path + [f"WORKGROUP.PRF={prf}"]
                    self._profil_branch(prf, prf_path)

                if contour:
                    cont_path = grp_path + [f"WORKGROUP.CONTOUR={contour}"]
                    self._generic_branch(contour, STATE_CONTELEM, cont_path)

    # ── PROFIL branch ─────────────────────────────────────────────────────────

    def _profil_branch(self, name: str, path: list[str]) -> None:
        branch = BRANCHES[STATE_PROFIL]
        rows = _fetch_branch(branch, name)
        for row in rows:
            for col in branch.value_columns:
                val = normalize(row.get(col))
                if val:
                    sub_path = path + [f"PROFIL.{col}={val}"]
                    self._classify(val, STATE_CONNECTIONS, sub_path, "PROFIL", col)

            prfdescr = normalize(row.get("PRFDESCR"))
            if prfdescr:
                self._generic_branch(prfdescr, STATE_CONTELEM,
                                     path + [f"PROFIL.PRFDESCR={prfdescr}"])

            render_prz = normalize(row.get("RENDER_PRZ"))
            if render_prz:
                self._generic_branch(render_prz, STATE_RENDER,
                                     path + [f"PROFIL.RENDER_PRZ={render_prz}"])

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
        occ = OccurrenceRow(
            article=self.article,
            path=list(path),
            variable_name=varname,
            value=value,
            source_table=source_table,
            source_column=source_column,
            resolved_via=resolved_via,
        )
        self.result.occurrences.append(occ)
        self.result.unique_vars[varname] = value


# ─── public API ───────────────────────────────────────────────────────────────

def extract_article(article: str, max_depth: int = 40) -> ExtractionResult:
    t = Traversal(article, max_depth=max_depth)
    return t.run()


def extract_all_articles(max_depth: int = 40) -> list[ExtractionResult]:
    rows = query(
        "SELECT DISTINCT NAME FROM dbo.articles ORDER BY NAME"
    )
    results = []
    for row in rows:
        name = normalize(row["NAME"])
        if name:
            print(f"  Extracting: {name}")
            results.append(extract_article(name, max_depth=max_depth))
    return results