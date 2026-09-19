# Source : flows/traversal_mixins.py
# Analogy: Plug-in attachments — ConnectionTreeMixin for full connection tree walk, ImosMixin for IMOS-only loop. Pick only what your flow needs.
"""
Reusable traversal patterns shared across flows.
Pick only the mixins your flow needs.
"""
from __future__ import annotations

from core.db import query, normalize
from core.branches import (
    BRANCHES,
    STATE_CONNECTIONS, STATE_CONNDESC, STATE_CONNEXTRA,
    STATE_CONNGROUPS, STATE_PROFIL, STATE_RENDER,
    STATE_CONTELEM, STATE_NUT_ERB, STATE_EXTRUPAR, STATE_EXTRUCON,
    STATE_IDENT, STATE_IMOS, STATE_MAT, STATE_SURF,
)
from core.parser import parse


class ConnectionTreeMixin:
    """Full connection-tree walk: CONNECTIONS → sub-branches → extrupar/extrucon/profil/etc."""

    def _enter_connections(self, value, path, source_table, source_column):
        state_key = (STATE_CONNECTIONS, value)
        if state_key in self._active:
            self.result.cycles.append(f"CYCLE: {' → '.join(path)} → CONNECTIONS({value})")
            return
        self._active.add(state_key)
        conn_rows = query(
            "SELECT * FROM dbo.[CONNECTIONS] WHERE NAME = ? "
            "AND NULLIF(LTRIM(RTRIM(INORDER)), N'') IS NULL "
            "ORDER BY CONNUM", (value,)
        )
        new_path = path + [f"CONNECTIONS({value})"]
        for row in conn_rows:
            self._process_connections_row(row, new_path)
        self._active.discard(state_key)

    def _process_connections_row(self, row, path):
        conndirect = normalize(row.get("CONNDIRECT"))
        if conndirect:
            cst_rows = query(
                "SELECT CHILDID FROM dbo.[CONNSELTREE] WHERE NAME = ? "
                "AND NULLIF(LTRIM(RTRIM(INORDER)), N'') IS NULL "
                "ORDER BY COMPONENT, PARENTNUM, CHILDNUM, POSNUM", (conndirect,)
            )
            for r in cst_rows:
                child = normalize(r.get("CHILDID"))
                if child:
                    child_path = path + [f"CONNDIRECT={conndirect} → CONNSELTREE.CHILDID={child}"]
                    self._resolve_then_branch(child, child_path)
        groove = normalize(row.get("GROOVE"))
        if groove:
            groove_path = path + [f"GROOVE={groove}"]
            self._resolve_then_groove(groove, groove_path)
        for col in ("LINDIV", "LINDIV2", "ROTATION", "POSPART0VAR", "POSPART1VAR", "SNAPRADI", "VARIANT"):
            val = normalize(row.get(col))
            if val:
                self._classify(val, STATE_CONNECTIONS, path + [f"{col}={val}"], "CONNECTIONS", col)

    def _resolve_then_groove(self, value, path):
        pv = parse(value)
        if pv is None:
            return
        for varname in pv.variables:
            state_key = (STATE_IMOS, varname)
            if state_key in self._active:
                self.result.cycles.append(f"CYCLE: {' → '.join(path)} → $IMOS({varname})")
                continue
            self._active.add(state_key)
            from core.traversal_base import _fetch_imos
            wert_values = _fetch_imos(varname)
            if not wert_values:
                self._record(varname, "[NOT IN IMOS]", path + [f"$IMOS({varname})"], "IMOS", "WERT", "UNRESOLVED")
            for wert in wert_values:
                rec_path = path + [f"$IMOS({varname})", f"WERT={wert}"]
                self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                self._resolve_then_groove(wert, rec_path)
            self._active.discard(state_key)
        if pv.is_raw:
            self._nut_erb_branch(value, path)
            self._extrupar_branch(value, path)
            self._extrucon_branch(value, path)

    def _resolve_then_render(self, value, path):
        pv = parse(value)
        if pv is None:
            return
        for varname in pv.variables:
            state_key = (STATE_IMOS, varname)
            if state_key in self._active:
                self.result.cycles.append(f"CYCLE: {' → '.join(path)} → $IMOS({varname})")
                continue
            self._active.add(state_key)
            from core.traversal_base import _fetch_imos
            wert_values = _fetch_imos(varname)
            if not wert_values:
                self._record(varname, "[NOT IN IMOS]", path + [f"$IMOS({varname})"], "IMOS", "WERT", "UNRESOLVED")
            for wert in wert_values:
                rec_path = path + [f"$IMOS({varname})", f"WERT={wert}"]
                self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                self._resolve_then_render(wert, rec_path)
            self._active.discard(state_key)
        if pv.is_raw:
            self._generic_branch(value, STATE_RENDER, path)

    def _resolve_then_branch(self, value, path):
        pv = parse(value)
        if pv is None:
            return
        for varname in pv.variables:
            state_key = (STATE_IMOS, varname)
            if state_key in self._active:
                self.result.cycles.append(f"CYCLE: {' → '.join(path)} → $IMOS({varname})")
                continue
            self._active.add(state_key)
            from core.traversal_base import _fetch_imos
            wert_values = _fetch_imos(varname)
            if not wert_values:
                self._record(varname, "[NOT IN IMOS]", path + [f"$IMOS({varname})"], "IMOS", "WERT", "UNRESOLVED")
            for wert in wert_values:
                rec_path = path + [f"$IMOS({varname})", f"WERT={wert}"]
                self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                self._resolve_then_branch(wert, rec_path)
            self._active.discard(state_key)
        if pv.is_raw:
            self._direct_sub_branches(value, path)

    def _direct_sub_branches(self, name, path):
        self._generic_branch(name, STATE_CONNDESC, path)
        self._generic_branch(name, STATE_CONNEXTRA, path)
        self._conngroups_to_workgroup(name, path)

    def _generic_branch(self, name, state_key, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES.get(state_key)
        if branch is None:
            return
        rows = _fetch_branch(branch, name)
        for row in rows:
            for col in branch.value_columns:
                val = normalize(row.get(col))
                if val:
                    self._classify(val, branch.next_state, path + [f"{branch.label}.{col}={val}"],
                                   branch.match_table, col)

    def _extrupar_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_EXTRUPAR]
        rows = _fetch_branch(branch, name)
        for row in rows:
            groove = normalize(row.get("GROOVE"))
            if groove:
                self._nut_erb_branch(groove, path + [f"extrupar.GROOVE={groove}"])
            render = normalize(row.get("RENDER"))
            if render:
                self._resolve_then_render(render, path + [f"extrupar.RENDER={render}"])
            cont = normalize(row.get("CONT"))
            if cont:
                self._generic_branch(cont, STATE_CONTELEM, path + [f"extrupar.CONT={cont}"])
            sectname = normalize(row.get("SECTNAME"))
            if sectname:
                self._generic_branch(sectname, STATE_CONTELEM, path + [f"extrupar.SECTNAME={sectname}"])
            mat = normalize(row.get("MAT"))
            if mat:
                pv = parse(mat)
                if pv and pv.is_raw:
                    self._mat_branch(mat, path + [f"extrupar.MAT={mat}"])
                else:
                    self._resolve_then_mat(mat, path + [f"extrupar.MAT={mat}"])
            surf = normalize(row.get("SURF"))
            if surf:
                pv = parse(surf)
                if pv and pv.is_raw:
                    self._surf_branch(surf, path + [f"extrupar.SURF={surf}"])
                else:
                    self._resolve_then_surf(surf, path + [f"extrupar.SURF={surf}"])
            if_folder = normalize(row.get("INFOFOLDER"))
            if if_folder:
                self._generic_branch(if_folder, STATE_IDENT, path + [f"extrupar.INFOFOLDER={if_folder}"])
            for col in ("GAP", "ARTIKELNR", "SCFACTOR", "SLWEIGHT", "SAUFMASS",
                        "SCOST", "SSIZEX", "SSIZEY", "SREFX", "SREFY", "SWALLSTREN",
                        "TEXT", "TEXT2", "MATOR", "SURFOR"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_CONNECTIONS, path + [f"extrupar.{col}={val}"], "extrupar", col)

    def _extrucon_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_EXTRUCON]
        rows = _fetch_branch(branch, name)
        for row in rows:
            for col in branch.value_columns:
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_CONNECTIONS, path + [f"extrucon.{col}={val}"], "extrucon", col)

    def _conngroups_to_workgroup(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_CONNGROUPS]
        rows = _fetch_branch(branch, name)
        for row in rows:
            grp = normalize(row.get("CONNGROUP"))
            if not grp:
                continue
            grp_path = path + [f"CONNGROUPS.CONNGROUP={grp}"]
            wg_rows = query(
                "SELECT NAME, PRF, CONTOUR FROM dbo.[WORKGROUP] "
                "WHERE NAME = ? AND NULLIF(LTRIM(RTRIM(INORDER)), N'') IS NULL", (grp,)
            )
            for wrow in wg_rows:
                prf = normalize(wrow.get("PRF"))
                contour = normalize(wrow.get("CONTOUR"))
                if prf:
                    pv = parse(prf)
                    if pv and pv.is_raw:
                        self._profil_branch(prf, grp_path + [f"WORKGROUP.PRF={prf}"])
                    else:
                        self._resolve_then_profil(prf, grp_path + [f"WORKGROUP.PRF={prf}"])
                if contour:
                    self._generic_branch(contour, STATE_CONTELEM, grp_path + [f"WORKGROUP.CONTOUR={contour}"])

    def _nut_erb_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_NUT_ERB]
        rows = _fetch_branch(branch, name)
        _profile_cols = {"PRFNAMEBO", "PRFNAMESE"}
        for row in rows:
            for col in branch.value_columns:
                val = normalize(row.get(col))
                if not val:
                    continue
                if col in _profile_cols:
                    self._resolve_then_profil(val, path + [f"nut_erb.{col}={val}"])
                else:
                    self._classify(val, branch.next_state, path + [f"nut_erb.{col}={val}"], "nut_erb", col)

    def _mat_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_MAT]
        rows = _fetch_branch(branch, name)
        for row in rows:
            for col in branch.value_columns:
                if col == "RENDER_PRZ":
                    continue
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_CONNECTIONS, path + [f"MAT.{col}={val}"], "MAT", col)
            render_prz = normalize(row.get("RENDER_PRZ"))
            if render_prz:
                self._resolve_then_render(render_prz, path + [f"MAT.RENDER_PRZ={render_prz}"])

    def _surf_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_SURF]
        rows = _fetch_branch(branch, name)
        for row in rows:
            for col in branch.value_columns:
                if col in ("RENDER_PRZ", "VPART_MAT"):
                    continue
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_CONNECTIONS, path + [f"SURF.{col}={val}"], "SURF", col)
            render_prz = normalize(row.get("RENDER_PRZ"))
            if render_prz:
                self._resolve_then_render(render_prz, path + [f"SURF.RENDER_PRZ={render_prz}"])
            vpart_mat = normalize(row.get("VPART_MAT"))
            if vpart_mat:
                pv = parse(vpart_mat)
                if pv and pv.is_raw:
                    self._mat_branch(vpart_mat, path + [f"SURF.VPART_MAT={vpart_mat}"])
                else:
                    self._resolve_then_mat(vpart_mat, path + [f"SURF.VPART_MAT={vpart_mat}"])

    def _resolve_then_mat(self, value, path):
        pv = parse(value)
        if pv is None:
            return
        for varname in pv.variables:
            state_key = (STATE_IMOS, varname)
            if state_key in self._active:
                self.result.cycles.append(f"CYCLE: {' → '.join(path)} → $IMOS({varname})")
                continue
            self._active.add(state_key)
            from core.traversal_base import _fetch_imos
            wert_values = _fetch_imos(varname)
            if not wert_values:
                self._record(varname, "[NOT IN IMOS]", path + [f"$IMOS({varname})"], "IMOS", "WERT", "UNRESOLVED")
            for wert in wert_values:
                rec_path = path + [f"$IMOS({varname})", f"WERT={wert}"]
                self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                self._resolve_then_mat(wert, rec_path)
            self._active.discard(state_key)
        if pv.is_raw:
            self._mat_branch(value, path)

    def _resolve_then_surf(self, value, path):
        pv = parse(value)
        if pv is None:
            return
        for varname in pv.variables:
            state_key = (STATE_IMOS, varname)
            if state_key in self._active:
                self.result.cycles.append(f"CYCLE: {' → '.join(path)} → $IMOS({varname})")
                continue
            self._active.add(state_key)
            from core.traversal_base import _fetch_imos
            wert_values = _fetch_imos(varname)
            if not wert_values:
                self._record(varname, "[NOT IN IMOS]", path + [f"$IMOS({varname})"], "IMOS", "WERT", "UNRESOLVED")
            for wert in wert_values:
                rec_path = path + [f"$IMOS({varname})", f"WERT={wert}"]
                self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                self._resolve_then_surf(wert, rec_path)
            self._active.discard(state_key)
        if pv.is_raw:
            self._surf_branch(value, path)

    def _resolve_then_profil(self, value, path):
        pv = parse(value)
        if pv is None:
            return
        for varname in pv.variables:
            state_key = (STATE_IMOS, varname)
            if state_key in self._active:
                self.result.cycles.append(f"CYCLE: {' → '.join(path)} → $IMOS({varname})")
                continue
            self._active.add(state_key)
            from core.traversal_base import _fetch_imos
            wert_values = _fetch_imos(varname)
            if not wert_values:
                self._record(varname, "[NOT IN IMOS]", path + [f"$IMOS({varname})"], "IMOS", "WERT", "UNRESOLVED")
            for wert in wert_values:
                rec_path = path + [f"$IMOS({varname})", f"WERT={wert}"]
                self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                self._resolve_then_profil(wert, rec_path)
            self._active.discard(state_key)
        if pv.is_raw:
            self._profil_branch(value, path)

    def _profil_branch(self, name, path):
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_PROFIL]
        rows = _fetch_branch(branch, name)
        _skip = {"PRFDESCR", "RENDER_PRZ"}
        for row in rows:
            for col in branch.value_columns:
                if col in _skip:
                    continue
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_CONNECTIONS, path + [f"PROFIL.{col}={val}"], "PROFIL", col)
            prfdescr = normalize(row.get("PRFDESCR"))
            if prfdescr:
                self._generic_branch(prfdescr, STATE_CONTELEM, path + [f"PROFIL.PRFDESCR={prfdescr}"])
            render_prz = normalize(row.get("RENDER_PRZ"))
            if render_prz:
                self._resolve_then_render(render_prz, path + [f"PROFIL.RENDER_PRZ={render_prz}"])


class ImosMixin:
    """IMOS-only loop — no connection tree. Used by anglclie-style flows."""

    def _classify_imos_loop(self, value, path):
        from core.traversal_base import _fetch_imos, _fetch_descriptor
        from core.branches import STATE_IMOS, STATE_DESCRIPTOR
        if len(path) > self.max_depth:
            return
        pv = parse(value)
        if pv is None:
            return
        for varname in pv.variables:
            state_key = (STATE_IMOS, varname)
            if state_key in self._active:
                self.result.cycles.append(f"CYCLE: {' → '.join(path)} → $IMOS({varname})")
                continue
            self._active.add(state_key)
            new_path = path + [f"$IMOS({varname})"]
            wert_values = _fetch_imos(varname)
            if not wert_values:
                self._record(varname, "[NOT IN IMOS]", new_path, "IMOS", "WERT", "UNRESOLVED")
            for wert in wert_values:
                rec_path = new_path + [f"WERT={wert}"]
                self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                self._classify_imos_loop(wert, rec_path)
            self._active.discard(state_key)
        for descname in pv.descriptors:
            state_key = (STATE_DESCRIPTOR, descname)
            if state_key in self._active:
                continue
            self._active.add(state_key)
            new_path = path + [f"#DESCRIPTOR({descname})"]
            for lindiv in _fetch_descriptor(descname):
                self._classify_imos_loop(lindiv, new_path + [f"LINDIV={lindiv}"])
            self._active.discard(state_key)