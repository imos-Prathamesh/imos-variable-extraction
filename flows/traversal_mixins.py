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
    STATE_CONNECTIONS, STATE_CONNDESC, STATE_CONNEXTRA, STATE_CONNSELATTR,
    STATE_CONNGROUPS, STATE_PROFIL, STATE_RENDER,
    STATE_CONTELEM, STATE_NUT_ERB, STATE_EXTRUPAR, STATE_EXTRUCON,
    STATE_IDENT, STATE_IMOS, STATE_MAT, STATE_SURF, STATE_TERMINAL,
    STATE_CONNECTIONSATTR, STATE_BLENDE, STATE_CSIDE, STATE_CABBACK,
    STATE_DOOR, STATE_DOORSING, STATE_GRIFF, STATE_PULLHEIGHT, STATE_DOOR_FLAP,
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
        if conn_rows:
            self._generic_branch(value, STATE_CONNECTIONSATTR, new_path)
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
            if cst_rows:
                self._generic_branch(conndirect, STATE_CONNSELATTR, path + [f"CONNDIRECT={conndirect}"])
            for r in cst_rows:
                child = normalize(r.get("CHILDID"))
                if child:
                    child_path = path + [f"CONNDIRECT={conndirect} → CONNSELTREE.CHILDID={child}"]
                    self._resolve_then_branch(child, child_path)
        groove = normalize(row.get("GROOVE"))
        if groove:
            tongue_raw = row.get("TONGUE")
            tongue_equals_one = tongue_raw in (1, True, "1") or normalize(tongue_raw) == "1"
            groove_path = path + [f"GROOVE={groove}"]
            self._resolve_then_groove(groove, groove_path, tongue_equals_one=tongue_equals_one)
        for col in ("LINDIV", "LINDIV2", "ROTATION", "POSPART0VAR", "POSPART1VAR", "SNAPRADI", "VARIANT"):
            val = normalize(row.get(col))
            if val:
                self._classify(val, STATE_TERMINAL, path + [f"{col}={val}"], "CONNECTIONS", col)

    def _resolve_then_groove(self, value, path, tongue_equals_one=False):
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
            if wert_values is None:
                self._record(varname, "[NOT IN IMOS]", path + [f"$IMOS({varname})"], "IMOS", "WERT", "UNRESOLVED")
            else:
                for wert in wert_values:
                    rec_path = path + [f"$IMOS({varname})", f"WERT={wert}"]
                    self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                    if wert != "[BLANK]":
                        self._resolve_then_groove(wert, rec_path, tongue_equals_one)
            self._active.discard(state_key)
        if pv.is_raw:
            if tongue_equals_one:
                self._extrupar_branch(value, path)
                self._extrucon_branch(value, path)
            else:
                self._nut_erb_branch(value, path)

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
            if wert_values is None:
                self._record(varname, "[NOT IN IMOS]", path + [f"$IMOS({varname})"], "IMOS", "WERT", "UNRESOLVED")
            else:
                for wert in wert_values:
                    rec_path = path + [f"$IMOS({varname})", f"WERT={wert}"]
                    self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                    if wert != "[BLANK]":
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
            if wert_values is None:
                self._record(varname, "[NOT IN IMOS]", path + [f"$IMOS({varname})"], "IMOS", "WERT", "UNRESOLVED")
            else:
                for wert in wert_values:
                    rec_path = path + [f"$IMOS({varname})", f"WERT={wert}"]
                    self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                    if wert != "[BLANK]":
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

    def _contelem_branch(self, name, path, include_profile=False):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_CONTELEM]
        rows = _fetch_branch(branch, name)
        _profile_cols = {"PROFILE"}
        for row in rows:
            for col in branch.value_columns:
                if col == "PROFILE" and not include_profile:
                    continue
                val = normalize(row.get(col))
                if not val:
                    continue
                if col in _profile_cols:
                    self._resolve_then_profil(val, path + [f"contelem.{col}={val}"])
                else:
                    self._classify(val, branch.next_state, path + [f"contelem.{col}={val}"], "contelem", col)

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
                self._contelem_branch(cont, path + [f"extrupar.CONT={cont}"])
            sectname = normalize(row.get("SECTNAME"))
            if sectname:
                self._contelem_branch(sectname, path + [f"extrupar.SECTNAME={sectname}"])
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
            for col in ("GAP", "ORDERID", "ARTIKELNR", "SCFACTOR", "SLWEIGHT", "SAUFMASS",
                        "SCOST", "SSIZEX", "SSIZEY", "SREFX", "SREFY", "SWALLSTREN",
                        "TEXT", "TEXT2", "MATOR", "SURFOR"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"extrupar.{col}={val}"], "extrupar", col)

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
                    _st = STATE_CONNECTIONS if col == "CONNAME" else STATE_TERMINAL
                    self._classify(val, _st, path + [f"extrucon.{col}={val}"], "extrucon", col)

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
                    self._contelem_branch(contour, grp_path + [f"WORKGROUP.CONTOUR={contour}"], include_profile=True)

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
                    self._classify(val, STATE_TERMINAL, path + [f"MAT.{col}={val}"], "MAT", col)
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
                    self._classify(val, STATE_TERMINAL, path + [f"SURF.{col}={val}"], "SURF", col)
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
            if wert_values is None:
                self._record(varname, "[NOT IN IMOS]", path + [f"$IMOS({varname})"], "IMOS", "WERT", "UNRESOLVED")
            else:
                for wert in wert_values:
                    rec_path = path + [f"$IMOS({varname})", f"WERT={wert}"]
                    self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                    if wert != "[BLANK]":
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
            if wert_values is None:
                self._record(varname, "[NOT IN IMOS]", path + [f"$IMOS({varname})"], "IMOS", "WERT", "UNRESOLVED")
            else:
                for wert in wert_values:
                    rec_path = path + [f"$IMOS({varname})", f"WERT={wert}"]
                    self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                    if wert != "[BLANK]":
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
            if wert_values is None:
                self._record(varname, "[NOT IN IMOS]", path + [f"$IMOS({varname})"], "IMOS", "WERT", "UNRESOLVED")
            else:
                for wert in wert_values:
                    rec_path = path + [f"$IMOS({varname})", f"WERT={wert}"]
                    self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                    if wert != "[BLANK]":
                        self._resolve_then_profil(wert, rec_path)
            self._active.discard(state_key)
        if pv.is_raw:
            self._profil_branch(value, path)

    def _anglmach_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_ANGLMACH, STATE_TERMINAL
        branch = BRANCHES[STATE_ANGLMACH]
        rows = _fetch_branch(branch, name)
        for row in rows:
            if not self._int_in(row.get("FACTOR"), (1,)):
                continue
            for col in ("SDIAMETER", "SDEEPNES"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"ANGLMACH.{col}={val}"], "ANGLMACH", col)
            prof_name = normalize(row.get("NAME"))
            if prof_name:
                self._resolve_then_profil(prof_name, path + [f"ANGLMACH.NAME={prof_name}"])

    def _profil_branch(self, name, path):
        state_key = (STATE_PROFIL, name)
        if state_key in self._active:
            self.result.cycles.append(f"CYCLE: {' → '.join(path)} → PROFIL({name})")
            return
        self._active.add(state_key)
        try:
            self._profil_branch_inner(name, path)
        finally:
            self._active.discard(state_key)

    def _profil_branch_inner(self, name, path):
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_PROFIL]
        rows = _fetch_branch(branch, name)
        _skip = {"PRFDESCR", "RENDER_PRZ", "VPART_MAT"}
        for row in rows:
            for col in branch.value_columns:
                if col in _skip:
                    continue
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"PROFIL.{col}={val}"], "PROFIL", col)
            prfdescr = normalize(row.get("PRFDESCR"))
            if prfdescr:
                self._contelem_branch(prfdescr, path + [f"PROFIL.PRFDESCR={prfdescr}"])
            render_prz = normalize(row.get("RENDER_PRZ"))
            if render_prz:
                self._resolve_then_render(render_prz, path + [f"PROFIL.RENDER_PRZ={render_prz}"])
            vpart_mat = normalize(row.get("VPART_MAT"))
            if vpart_mat:
                pv = parse(vpart_mat)
                if pv and pv.is_raw:
                    self._mat_branch(vpart_mat, path + [f"PROFIL.VPART_MAT={vpart_mat}"])
                else:
                    self._resolve_then_mat(vpart_mat, path + [f"PROFIL.VPART_MAT={vpart_mat}"])


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
            if wert_values is None:
                self._record(varname, "[NOT IN IMOS]", new_path, "IMOS", "WERT", "UNRESOLVED")
            else:
                for wert in wert_values:
                    rec_path = new_path + [f"WERT={wert}"]
                    self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                    if wert != "[BLANK]":
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


from core.branches import (  # noqa: E402
    STATE_ARTCALC, STATE_DESIGN, STATE_LNGSOCKL, STATE_KMS, STATE_KMSPROF,
    STATE_KMSBEARB, STATE_KMSCONNECTIONS, STATE_MPPCPNTS, STATE_MPPSUBPA,
    STATE_MPPEXTRU, STATE_MPPSPNTS,
)


class AnglprimMixin:
    """anglprim tree: ARTCALC, design, lngsockl, KMS and its sub-tables.
    List BEFORE ConnectionTreeMixin so the _extrupar_branch override below wins."""

    @staticmethod
    def _int_in(value, targets):
        if isinstance(value, bool):
            return int(value) in targets
        v = normalize(value)
        if v is None:
            return False
        try:
            return int(float(v)) in targets
        except ValueError:
            return False

    @staticmethod
    def _num_gt(value, limit):
        if isinstance(value, bool):
            return int(value) > limit
        v = normalize(value)
        if v is None:
            return False
        try:
            return float(v) > limit
        except ValueError:
            return False

    def _resolve_then(self, value, path, handler):
        from core.traversal_base import _fetch_imos
        pv = parse(value)
        if pv is None:
            return
        for varname in pv.variables:
            state_key = (STATE_IMOS, varname)
            if state_key in self._active:
                self.result.cycles.append(f"CYCLE: {' → '.join(path)} → $IMOS({varname})")
                continue
            self._active.add(state_key)
            wert_values = _fetch_imos(varname)
            if wert_values is None:
                self._record(varname, "[NOT IN IMOS]", path + [f"$IMOS({varname})"], "IMOS", "WERT", "UNRESOLVED")
            else:
                for wert in wert_values:
                    rec_path = path + [f"$IMOS({varname})", f"WERT={wert}"]
                    self._record(varname, wert, rec_path, "IMOS", "WERT", "IMOS")
                    if wert != "[BLANK]":
                        self._resolve_then(wert, rec_path, handler)
            self._active.discard(state_key)
        if pv.is_raw:
            handler(value, path)

    def _rows(self, state, name):
        if not name:
            return []
        from core.traversal_base import _fetch_branch
        return _fetch_branch(BRANCHES[state], name)

    def _terminal_cols(self, row, cols, label, path):
        for col in cols:
            val = normalize(row.get(col))
            if val:
                self._classify(val, STATE_TERMINAL, path + [f"{label}.{col}={val}"], label, col)

    def _spp_branch(self, value, path, with_mat=True):
        self._extrupar_branch(value, path, with_mat)
        self._extrucon_branch(value, path)

    def _spp_no_mat(self, value, path):
        self._spp_branch(value, path, with_mat=False)

    def _extrupar_branch(self, name, path, with_mat=True):
        for row in self._rows(STATE_EXTRUPAR, name):
            groove = normalize(row.get("GROOVE"))
            if groove:
                self._nut_erb_branch(groove, path + [f"extrupar.GROOVE={groove}"])
            render = normalize(row.get("RENDER"))
            if render:
                self._resolve_then_render(render, path + [f"extrupar.RENDER={render}"])
            for col in ("CONT", "SECTNAME"):
                val = normalize(row.get(col))
                if val:
                    self._contelem_branch(val, path + [f"extrupar.{col}={val}"])
            if with_mat:
                mat = normalize(row.get("MAT"))
                if mat:
                    self._resolve_then_mat(mat, path + [f"extrupar.MAT={mat}"])
                surf = normalize(row.get("SURF"))
                if surf:
                    self._resolve_then_surf(surf, path + [f"extrupar.SURF={surf}"])
            info = normalize(row.get("INFOFOLDER"))
            if info:
                self._generic_branch(info, STATE_IDENT, path + [f"extrupar.INFOFOLDER={info}"])
            cols = ["GAP", "ORDERID", "ARTIKELNR", "SCFACTOR", "SLWEIGHT", "SAUFMASS",
                    "SCOST", "SSIZEX", "SSIZEY", "SREFX", "SREFY", "SWALLSTREN"]
            if with_mat:
                cols += ["MATOR", "SURFOR"]
            self._terminal_cols(row, cols, "extrupar", path)

    def _artcalc_branch(self, name, path):
        for row in self._rows(STATE_ARTCALC, name):
            self._terminal_cols(row, ["FORMULA"], "ARTCALC", path)

    def _design_branch(self, name, path):
        _gated_cols = {
            "SFRONTDIST", "SBACKDIST", "SSOCKETHGT",
            "SINSETGAPT", "SINSETGAPB", "SINSETGAPR", "SINSETGAPL", "SINSETGAPI",
            "SONSETLAYT", "SONSETLAYB", "SONSETLAYR", "SONSETLAYL", "SONSETLAYI",
        }
        _excluded = _gated_cols | {"GROOVE", "SOCKET", "ONEQUALINS", "ONEQUALLAY"}
        for row in self._rows(STATE_DESIGN, name):
            groove = normalize(row.get("GROOVE"))
            if groove:
                self._nut_erb_branch(groove, path + [f"design.GROOVE={groove}"])

            cols = [c for c in BRANCHES[STATE_DESIGN].value_columns if c not in _excluded]
            self._terminal_cols(row, cols, "design", path)

            if self._int_in(row.get("SOCKET"), (1,)):
                self._terminal_cols(row, ["SFRONTDIST", "SBACKDIST", "SSOCKETHGT"], "design", path)

            if self._int_in(row.get("ONEQUALINS"), (0,)):
                self._terminal_cols(row, ["SINSETGAPT", "SINSETGAPB", "SINSETGAPR",
                                           "SINSETGAPL", "SINSETGAPI"], "design", path)

            if self._int_in(row.get("ONEQUALLAY"), (0,)):
                self._terminal_cols(row, ["SONSETLAYT", "SONSETLAYB", "SONSETLAYR",
                                           "SONSETLAYL", "SONSETLAYI"], "design", path)

    def _workgroup_branch(self, name, path):
        rows = query(
            "SELECT NAME, PRF, CONTOUR FROM dbo.[WORKGROUP] "
            "WHERE NAME = ? AND NULLIF(LTRIM(RTRIM(INORDER)), N'') IS NULL", (name,)
        )
        for wrow in rows:
            prf = normalize(wrow.get("PRF"))
            if prf:
                self._resolve_then_profil(prf, path + [f"WORKGROUP.PRF={prf}"])
            contour = normalize(wrow.get("CONTOUR"))
            if contour:
                self._contelem_branch(contour, path + [f"WORKGROUP.CONTOUR={contour}"], include_profile=True)

    def _lngsockl_branch(self, name, path):
        self._lng_branch(name, path, STATE_LNGSOCKL)

    def _lng_branch(self, name, path, state):
        label = BRANCHES[state].match_table
        skip = {"ARTCALC1", "ARTCALC2", "ARTCALC3", "CPINFO", "KMS_PLATTE", "KMS_LEI_VO",
                "KMS_LEI_HI", "KMS_LEI_RE", "KMS_LEI_LI", "KMS_STZ", "PK_PRINZIP"}
        for row in self._rows(state, name):
            for col in ("ARTCALC1", "ARTCALC2", "ARTCALC3"):
                val = normalize(row.get(col))
                if val:
                    self._artcalc_branch(val, path + [f"{label}.{col}={val}"])
            info = normalize(row.get("CPINFO"))
            if info:
                self._generic_branch(info, STATE_IDENT, path + [f"{label}.CPINFO={info}"])
            for col in ("KMS_PLATTE", "KMS_LEI_VO", "KMS_LEI_HI", "KMS_LEI_RE", "KMS_LEI_LI", "KMS_STZ"):
                val = normalize(row.get(col))
                if val:
                    self._resolve_then(val, path + [f"{label}.{col}={val}"], self._kms_branch)
            prinzip = normalize(row.get("PK_PRINZIP"))
            if prinzip:
                self._resolve_then(prinzip, path + [f"{label}.PK_PRINZIP={prinzip}"], self._spp_branch)
            cols = [c for c in BRANCHES[state].value_columns if c not in skip]
            self._terminal_cols(row, cols, label, path)

    def _kms_branch(self, name, path):
        state_key = (STATE_KMS, name)
        if state_key in self._active:
            self.result.cycles.append(f"CYCLE: {' → '.join(path)} → KMS({name})")
            return
        self._active.add(state_key)
        try:
            self._kms_branch_inner(name, path)
        finally:
            self._active.discard(state_key)

    def _kms_branch_inner(self, name, path):
        rows = self._rows(STATE_KMS, name)
        for row in rows:
            for col in ("BENDCONT", "PLANNAME"):
                val = normalize(row.get(col))
                if val:
                    self._contelem_branch(val, path + [f"KMS.{col}={val}"])
            info = normalize(row.get("INFONAME"))
            if info:
                self._generic_branch(info, STATE_IDENT, path + [f"KMS.INFONAME={info}"])
            mat = normalize(row.get("MATERIAL"))
            if mat:
                self._resolve_then_mat(mat, path + [f"KMS.MATERIAL={mat}"])
            for col in ("SURF0", "SURF1"):
                val = normalize(row.get(col))
                if val:
                    self._resolve_then_surf(val, path + [f"KMS.{col}={val}"])
            self._terminal_cols(
                row,
                ["GRAIN", "GRAINOR", "SUR0_GRNOR", "SUR1_GRNOR", "COLORTOP", "COLORBOTTOM", "SVIRTTHK"],
                "KMS", path,
            )
        if rows:
            self._kmsconnections_branch(name, path)
            self._kmsprof_branch(name, path)
            self._kmsbearb_branch(name, path)
            self._mppcpnts_branch(name, path)
            self._mppspnts_branch(name, path)
            self._mppextru_branch(name, path)
            self._mppsubpa_branch(name, path)

    def _kmsconnections_branch(self, name, path):
        for row in self._rows(STATE_KMSCONNECTIONS, name):
            cid = normalize(row.get("CONNECTID"))
            if cid:
                self._classify(cid, STATE_CONNECTIONS, path + [f"KMSCONNECTIONS.CONNECTID={cid}"],
                               "KMSCONNECTIONS", "CONNECTID")

    def _kmsprof_branch(self, name, path):
        for row in self._rows(STATE_KMSPROF, name):
            cid = normalize(row.get("CONNECTID"))
            if cid:
                self._classify(cid, STATE_CONNECTIONS, path + [f"kmsprof.CONNECTID={cid}"],
                               "kmsprof", "CONNECTID")
            contour = normalize(row.get("CONTOUR"))
            if contour:
                self._contelem_branch(contour, path + [f"kmsprof.CONTOUR={contour}"])
            info = normalize(row.get("INFONAME"))
            if info:
                self._generic_branch(info, STATE_IDENT, path + [f"kmsprof.INFONAME={info}"])
            color = normalize(row.get("KMSPRFCOLOR"))
            if color:
                self._resolve_then_render(color, path + [f"kmsprof.KMSPRFCOLOR={color}"])
            prinzip = normalize(row.get("MVKPRINZIP"))
            if prinzip:
                self._resolve_then(prinzip, path + [f"kmsprof.MVKPRINZIP={prinzip}"], self._spp_branch)
            profile = normalize(row.get("PROFILE"))
            if profile:
                self._resolve_then_profil(profile, path + [f"kmsprof.PROFILE={profile}"])

    def _kmsbearb_branch(self, name, path):
        for row in self._rows(STATE_KMSBEARB, name):
            cols = [c for c in BRANCHES[STATE_KMSBEARB].value_columns if c not in ("TYPE", "NAME")]
            self._terminal_cols(row, cols, "kmsbearb", path)
            nm = normalize(row.get("NAME"))
            if not nm:
                continue
            npath = path + [f"kmsbearb.NAME={nm}"]
            typ = row.get("TYPE")
            if self._int_in(typ, (4,)):
                self._workgroup_branch(nm, npath)
            elif self._int_in(typ, (1, 2, 3, 5, 6, 7)):
                self._resolve_then_profil(nm, npath)
            elif self._int_in(typ, (10,)):
                self._contelem_branch(nm, npath, include_profile=True)

    def _mppcpnts_branch(self, name, path):
        for row in self._rows(STATE_MPPCPNTS, name):
            self._terminal_cols(row, ["LIN_X", "LIN_Y"], "mppcpnts", path)

    def _mppspnts_branch(self, name, path):
        for row in self._rows(STATE_MPPSPNTS, name):
            self._terminal_cols(row, ["DISTANCE", "OFFSET"], "mppspnts", path)

    def _mppextru_branch(self, name, path):
        for row in self._rows(STATE_MPPEXTRU, name):
            prinzip = normalize(row.get("PRINZIP"))
            if prinzip:
                self._resolve_then(prinzip, path + [f"mppextru.PRINZIP={prinzip}"], self._spp_branch)
            cols = [c for c in BRANCHES[STATE_MPPEXTRU].value_columns if c != "PRINZIP"]
            self._terminal_cols(row, cols, "mppextru", path)

    def _mppsubpa_branch(self, name, path):
        for row in self._rows(STATE_MPPSUBPA, name):
            sub = normalize(row.get("SUBKMS"))
            if sub:
                spath = path + [f"mppsubpa.SUBKMS={sub}"]
                if self._int_in(row.get("CPNUM"), (3,)) or self._num_gt(row.get("SINGLE_LAYER_PART"), 0):
                    self._resolve_then_surf(sub, spath)
                else:
                    self._resolve_then(sub, spath, self._kms_branch)
            cols = [c for c in BRANCHES[STATE_MPPSUBPA].value_columns
                    if c not in ("SUBKMS", "CPNUM", "SINGLE_LAYER_PART")]
            self._terminal_cols(row, cols, "mppsubpa", path)

    def _blende_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_BLENDE]
        rows = _fetch_branch(branch, name)
        for row in rows:
            for col in ("SBREITE", "SUEBERST_O", "SUEBERST_U", "SEINRUECKG", "SUEBERST_F"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"BLENDE.{col}={val}"], "BLENDE", col)
            info = normalize(row.get("CPINFO"))
            if info:
                self._generic_branch(info, STATE_IDENT, path + [f"BLENDE.CPINFO={info}"])
            kms = normalize(row.get("KMS"))
            if kms:
                self._resolve_then(kms, path + [f"BLENDE.KMS={kms}"], self._kms_branch)

    def _cpconnlist_branch(self, name, path):
        if not name:
            return
        rows = query(
            "SELECT CONNECTID FROM dbo.[CPCONNLIST] WHERE NAME = ?",
            (name,)
        )
        for row in rows:
            cid = normalize(row.get("CONNECTID"))
            if cid:
                self._classify(cid, STATE_CONNECTIONS, path + [f"CPCONNLIST.CONNECTID={cid}"],
                               "CPCONNLIST", "CONNECTID")

    def _cpconnlist_branch_type4(self, name, path):
        if not name:
            return
        rows = query(
            "SELECT CONNECTID FROM dbo.[CPCONNLIST] WHERE NAME = ? AND TYPE = 4",
            (name,)
        )
        for row in rows:
            cid = normalize(row.get("CONNECTID"))
            if cid:
                self._classify(cid, STATE_CONNECTIONS, path + [f"CPCONNLIST.CONNECTID={cid}"],
                               "CPCONNLIST", "CONNECTID")

    def _cpconnprim_gated_cpconnlist_branch(self, name, path):
        if not name:
            return
        prim_rows = query(
            "SELECT ONLYONECON FROM dbo.[CPCONNPRIM] WHERE NAME = ? AND TYPE = 4",
            (name,)
        )
        if not prim_rows:
            return

        if self._int_in(prim_rows[0].get("ONLYONECON"), (1,)):
            rows = query(
                "SELECT CONNECTID FROM dbo.[CPCONNLIST] "
                "WHERE NAME = ? AND TYPE = 4 AND CONNNUM IN (0, 1, 2)",
                (name,)
            )
        else:
            rows = query(
                "SELECT CONNECTID FROM dbo.[CPCONNLIST] WHERE NAME = ? AND TYPE = 4",
                (name,)
            )

        for row in rows:
            cid = normalize(row.get("CONNECTID"))
            if cid:
                self._classify(cid, STATE_CONNECTIONS, path + [f"CPCONNLIST.CONNECTID={cid}"],
                               "CPCONNLIST", "CONNECTID")

    def _cside_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_CSIDE]
        rows = _fetch_branch(branch, name)
        for row in rows:
            kms = normalize(row.get("KMS"))
            if kms:
                self._resolve_then(kms, path + [f"CSIDE.KMS={kms}"], self._kms_branch)

            info = normalize(row.get("CPINFO"))
            if info:
                self._generic_branch(info, STATE_IDENT, path + [f"CSIDE.CPINFO={info}"])

            if self._int_in(row.get("MDRFLAG"), (4,)):
                continue

            if self._int_in(row.get("MDRFLAG"), (3,)):
                mdr_cols = ("SRASTER", "SDIAMETER", "SDISTSTART", "SDISTSEND", "SWGTYPE", "SMACHCLASS")
            else:
                mdr_cols = ("SRASTER", "SDIAMETER", "SDISTSTART", "SDISTSEND", "SWGTYPE", "SMACHCLASS", "SDEPTH")
            for col in mdr_cols:
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"CSIDE.{col}={val}"], "CSIDE", col)

            if self._int_in(row.get("REF_VER"), (3,)):
                lt_ver = normalize(row.get("LT_VER"))
                if lt_ver:
                    self._classify(lt_ver, STATE_TERMINAL, path + [f"CSIDE.LT_VER={lt_ver}"], "CSIDE", "LT_VER")
            else:
                for col in ("SDISTFRONT", "SDISTBACK"):
                    val = normalize(row.get(col))
                    if val:
                        self._classify(val, STATE_TERMINAL, path + [f"CSIDE.{col}={val}"], "CSIDE", col)

    def _cabback_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_CABBACK]
        rows = _fetch_branch(branch, name)
        _plain_cols = [
            "CONDIST", "NUTUSTLAEN", "NUTUSTL_KR", "NUTUSTL_UB", "NUTUSTL_OB",
            "NUTUSTQUER", "NUTUSTTIEF", "FLNUT_AUS", "FLNUT_A_KR", "FLNUT_A_UB",
            "FLNUT_A_OB", "FLVERB_KS", "FLVERB_BOD", "FLNUT_TDEF", "DISTUP",
            "DISTLR", "THKINCLDED", "CONDSTART", "CONDEND", "RGRDEL", "RGRDER",
            "RGRDET", "RGRDEB", "SRGRDEL", "SRGRDER", "SRGRDET", "SRGRDEB",
            "SDISTLR", "SCONDIST", "SCONDSTART", "SCONDEND",
        ]
        for row in rows:
            for col in _plain_cols:
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"CABBACK.{col}={val}"], "CABBACK", col)
            info = normalize(row.get("CPINFO"))
            if info:
                self._generic_branch(info, STATE_IDENT, path + [f"CABBACK.CPINFO={info}"])
            kms = normalize(row.get("KMS"))
            if kms:
                self._resolve_then(kms, path + [f"CABBACK.KMS={kms}"], self._kms_branch)
            nut = normalize(row.get("NUT_ERB"))
            if nut:
                self._nut_erb_branch(nut, path + [f"CABBACK.NUT_ERB={nut}"])

    def _cpconnlist_branch_connnum0_type4(self, name, path):
        if not name:
            return
        rows = query(
            "SELECT CONNECTID FROM dbo.[CPCONNLIST] WHERE NAME = ? AND CONNNUM = 0 AND TYPE = 4",
            (name,)
        )
        for row in rows:
            cid = normalize(row.get("CONNECTID"))
            if cid:
                self._classify(cid, STATE_CONNECTIONS, path + [f"CPCONNLIST.CONNECTID={cid}"],
                               "CPCONNLIST", "CONNECTID")

    def _door_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_DOOR]
        rows = _fetch_branch(branch, name)
        for row in rows:
            for col in ("SFRONTDIS", "SFRONTDISR"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"DOOR.{col}={val}"], "DOOR", col)

            if self._int_in(row.get("FR_ABW_AKT"), (0,)):
                for col in ("DISTC", "DISTJ", "DISTUP", "DISTDN",
                            "SDISTC", "SDISTJ", "SDISTUP", "SDISTDN"):
                    val = normalize(row.get(col))
                    if val:
                        self._classify(val, STATE_TERMINAL, path + [f"DOOR.{col}={val}"], "DOOR", col)

            if self._int_in(row.get("NOD"), (1,)) and self._int_in(row.get("DJOIN"), (1,)):
                info = normalize(row.get("CPINFO"))
                if info:
                    self._generic_branch(info, STATE_IDENT, path + [f"DOOR.CPINFO={info}"])
                nut = normalize(row.get("NUT_ERB"))
                if nut:
                    self._nut_erb_branch(nut, path + [f"DOOR.NUT_ERB={nut}"])
                tuer = normalize(row.get("TUER_L"))
                if tuer:
                    self._classify(tuer, STATE_DOORSING, path + [f"DOOR.TUER_L={tuer}"], "DOOR", "TUER_L")
                self._cpconnlist_branch_connnum0_type4(name, path)

    def _door_branch_flap(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_DOOR_FLAP]
        rows = _fetch_branch(branch, name)
        for row in rows:
            for col in ("SFRONTDIS", "SFRONTDISR"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"DOOR.{col}={val}"], "DOOR", col)

            if self._int_in(row.get("FR_ABW_AKT"), (0,)):
                for col in ("DISTC", "DISTJ", "DISTUP", "DISTDN",
                            "SDISTC", "SDISTJ", "SDISTUP", "SDISTDN"):
                    val = normalize(row.get(col))
                    if val:
                        self._classify(val, STATE_TERMINAL, path + [f"DOOR.{col}={val}"], "DOOR", col)

            if self._int_in(row.get("NOD"), (1,)) and self._int_in(row.get("DJOIN"), (2,)):
                info = normalize(row.get("CPINFO"))
                if info:
                    self._generic_branch(info, STATE_IDENT, path + [f"DOOR.CPINFO={info}"])
                nut = normalize(row.get("NUT_ERB"))
                if nut:
                    self._nut_erb_branch(nut, path + [f"DOOR.NUT_ERB={nut}"])
                tuer_l = normalize(row.get("TUER_L"))
                if tuer_l:
                    self._classify(tuer_l, STATE_DOORSING, path + [f"DOOR.TUER_L={tuer_l}"], "DOOR", "TUER_L")
                tuer_r = normalize(row.get("TUER_R"))
                if tuer_r:
                    self._classify(tuer_r, STATE_DOORSING, path + [f"DOOR.TUER_R={tuer_r}"], "DOOR", "TUER_R")
                self._cpconnprim_gated_cpconnlist_branch(name, path)

    def _door_branch_double(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_DOOR_DOUBLE
        branch = BRANCHES[STATE_DOOR_DOUBLE]
        rows = _fetch_branch(branch, name)
        for row in rows:
            for col in ("SFRONTDIS", "SFRONTDISR"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"DOOR.{col}={val}"], "DOOR", col)

            if self._int_in(row.get("FR_ABW_AKT"), (0,)):
                for col in ("DISTC", "DISTJ", "DISTUP", "DISTDN",
                            "SDISTC", "SDISTJ", "SDISTUP", "SDISTDN", "FUGE2_FORM"):
                    val = normalize(row.get(col))
                    if val:
                        self._classify(val, STATE_TERMINAL, path + [f"DOOR.{col}={val}"], "DOOR", col)

            if self._int_in(row.get("NOD"), (2,)) and self._int_in(row.get("DJOIN"), (1,)):
                nut = normalize(row.get("NUT_ERB"))
                if nut:
                    self._nut_erb_branch(nut, path + [f"DOOR.NUT_ERB={nut}"])

                tuer_l = normalize(row.get("TUER_L"))
                if tuer_l:
                    self._classify(tuer_l, STATE_DOORSING, path + [f"DOOR.TUER_L={tuer_l}"], "DOOR", "TUER_L")
                tuer_r = normalize(row.get("TUER_R"))
                if tuer_r:
                    self._classify(tuer_r, STATE_DOORSING, path + [f"DOOR.TUER_R={tuer_r}"], "DOOR", "TUER_R")

                if self._int_in(row.get("SEP_INFOLR"), (1,)):
                    info = normalize(row.get("CPINFO"))
                    if info:
                        self._generic_branch(info, STATE_IDENT, path + [f"DOOR.CPINFO={info}"])
                    infor = normalize(row.get("CPINFOR"))
                    if infor:
                        self._generic_branch(infor, STATE_IDENT, path + [f"DOOR.CPINFOR={infor}"])
                else:
                    info = normalize(row.get("CPINFO"))
                    if info:
                        self._generic_branch(info, STATE_IDENT, path + [f"DOOR.CPINFO={info}"])

                sl_kms = normalize(row.get("SL_KMS"))
                if sl_kms:
                    for col in ("SL_TIEFENV", "SL_SAUFLAG", "SL_SBREITE", "SL_SABOBEN", "SL_SABUNT"):
                        val = normalize(row.get(col))
                        if val:
                            self._classify(val, STATE_TERMINAL, path + [f"DOOR.{col}={val}"], "DOOR", col)
                    self._resolve_then(sl_kms, path + [f"DOOR.SL_KMS={sl_kms}"], self._kms_branch)
                    groove = normalize(row.get("GROOVE"))
                    if groove:
                        self._nut_erb_branch(groove, path + [f"DOOR.GROOVE={groove}"])

                self._door_double_cpconnprim_branch(name, path)

    def _door_double_cpconnprim_branch(self, name, path):
        prim_rows = query(
            "SELECT ONLYONECON FROM dbo.[CPCONNPRIM] WHERE NAME = ? AND TYPE = 4",
            (name,)
        )
        if not prim_rows:
            return

        connnums = (0,) if self._int_in(prim_rows[0].get("ONLYONECON"), (1,)) else (0, 1)
        rows = query(
            "SELECT CONNECTID FROM dbo.[CPCONNLIST] "
            "WHERE NAME = ? AND TYPE = 4 AND CONNNUM IN (" + ",".join("?" * len(connnums)) + ")",
            (name, *connnums)
        )
        for row in rows:
            cid = normalize(row.get("CONNECTID"))
            if cid:
                self._classify(cid, STATE_CONNECTIONS, path + [f"CPCONNLIST.CONNECTID={cid}"],
                               "CPCONNLIST", "CONNECTID")

    def _imosdoorsinfo_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_IMOSDOORSINFO, STATE_IMOSDOORSINGLE
        branch = BRANCHES[STATE_IMOSDOORSINFO]
        rows = _fetch_branch(branch, name)
        for row in rows:
            if not self._int_in(row.get("TYPE"), (0,)):
                continue

            if self._int_in(row.get("LANECHANGING"), (1,)):
                val = normalize(row.get("MIDDLEGAP2"))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"IMOSDOORSINFO.MIDDLEGAP2={val}"],
                                   "IMOSDOORSINFO", "MIDDLEGAP2")

            if self._int_in(row.get("FRONTABW"), (0,)):
                for col in ("SABSTANDOBEN", "SABSTANDUNTEN", "SABSTANDLINKS", "SABSTANDRECHTS"):
                    val = normalize(row.get(col))
                    if val:
                        self._classify(val, STATE_TERMINAL, path + [f"IMOSDOORSINFO.{col}={val}"],
                                       "IMOSDOORSINFO", col)

            for col in ("SEINRUECKUNG1", "SEINRUECKUNG2", "SUEBERLAPPUNG"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"IMOSDOORSINFO.{col}={val}"],
                                   "IMOSDOORSINFO", col)

            frontaufteilung = normalize(row.get("FRONTAUFTEILUNG"))
            if frontaufteilung:
                self._classify(frontaufteilung, STATE_TERMINAL, path + [f"IMOSDOORSINFO.FRONTAUFTEILUNG={frontaufteilung}"],
                               "IMOSDOORSINFO", "FRONTAUFTEILUNG")

            if self._int_in(row.get("KONSTRART"), (2,)):
                for col in ("SBLENDEHOEHE", "SBLENDEEINR", "SBLENDEUEBERSTOBEN",
                            "SBLENDEUEBERSTLINKS", "SBLENDEUEBERSTRECHTS"):
                    val = normalize(row.get(col))
                    if val:
                        self._classify(val, STATE_TERMINAL, path + [f"IMOSDOORSINFO.{col}={val}"],
                                       "IMOSDOORSINFO", col)
                blendekms = normalize(row.get("BLENDEKMS"))
                if blendekms:
                    self._resolve_then(blendekms, path + [f"IMOSDOORSINFO.BLENDEKMS={blendekms}"], self._kms_branch)

            for col in ("SITUNAMEOBEN", "SITUNAMEUNTEN"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_CONNECTIONS, path + [f"IMOSDOORSINFO.{col}={val}"],
                                   "IMOSDOORSINFO", col)

            self._imosdoorsingle_branch(name, path)

    def _imosdoorsingle_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_IMOSDOORSINGLE
        branch = BRANCHES[STATE_IMOSDOORSINGLE]
        rows = _fetch_branch(branch, name)
        for row in rows:
            btausp = normalize(row.get("BTAUSP"))
            if btausp:
                self._resolve_then(btausp, path + [f"IMOSDOORSINGLE.BTAUSP={btausp}"], self._kms_branch)
            for col in ("SITUNAMEGRIFF", "SITUNAMEGRIFF1", "SITUNAMEGRIFF2"):
                val = normalize(row.get(col))
                if val:
                    self._resolve_then(val, path + [f"IMOSDOORSINGLE.{col}={val}"], self._griff_branch)

    def _imosdoorsinfo_branch_bifold(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_IMOSDOORSINFO_BIFOLD, STATE_IMOSDOORSINGLE_BIFOLD
        branch = BRANCHES[STATE_IMOSDOORSINFO_BIFOLD]
        rows = _fetch_branch(branch, name)
        for row in rows:
            if not self._int_in(row.get("TYPE"), (1,)):
                continue

            if self._int_in(row.get("FRONTABW"), (0,)):
                for col in ("SABSTANDOBEN", "SABSTANDUNTEN", "SABSTANDLINKS", "SABSTANDRECHTS"):
                    val = normalize(row.get(col))
                    if val:
                        self._classify(val, STATE_TERMINAL, path + [f"IMOSDOORSINFO.{col}={val}"],
                                       "IMOSDOORSINFO", col)

            for col in ("SEINRUECKUNG1", "SUEBERLAPPUNG"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"IMOSDOORSINFO.{col}={val}"],
                                   "IMOSDOORSINFO", col)

            for col in ("FRONTAUFTRECHTS", "FRONTAUFTLINKS"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"IMOSDOORSINFO.{col}={val}"],
                                   "IMOSDOORSINFO", col)

            for col in ("SITUNAME", "SITUNAMELINKS", "SITUNAMERECHTS"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_CONNECTIONS, path + [f"IMOSDOORSINFO.{col}={val}"],
                                   "IMOSDOORSINFO", col)

            self._imosdoorsingle_branch_bifold(name, path)

    def _imosdoorsingle_branch_bifold(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_IMOSDOORSINGLE_BIFOLD
        branch = BRANCHES[STATE_IMOSDOORSINGLE_BIFOLD]
        rows = _fetch_branch(branch, name)
        for row in rows:
            btausp = normalize(row.get("BTAUSP"))
            if btausp:
                self._resolve_then(btausp, path + [f"IMOSDOORSINGLE.BTAUSP={btausp}"], self._kms_branch)
            for col in ("SITUNAMEGRIFF", "SITUNAMEGRIFF1", "SITUNAMEGRIFF2"):
                val = normalize(row.get(col))
                if val:
                    self._resolve_then(val, path + [f"IMOSDOORSINGLE.{col}={val}"], self._griff_branch)

    def _imosdoorsinfo_branch_foldslide(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_IMOSDOORSINFO_FOLDSLIDE, STATE_IMOSDOORSINGLE_FOLDSLIDE
        branch = BRANCHES[STATE_IMOSDOORSINFO_FOLDSLIDE]
        rows = _fetch_branch(branch, name)
        for row in rows:
            if not self._int_in(row.get("TYPE"), (2,)):
                continue

            if self._int_in(row.get("FRONTABW"), (0,)):
                for col in ("SABSTANDOBEN", "SABSTANDUNTEN", "SABSTANDLINKS", "SABSTANDRECHTS"):
                    val = normalize(row.get(col))
                    if val:
                        self._classify(val, STATE_TERMINAL, path + [f"IMOSDOORSINFO.{col}={val}"],
                                       "IMOSDOORSINFO", col)

            for col in ("SEINRUECKUNG1", "SUEBERLAPPUNG"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"IMOSDOORSINFO.{col}={val}"],
                                   "IMOSDOORSINFO", col)

            frontaufteilung = normalize(row.get("FRONTAUFTEILUNG"))
            if frontaufteilung:
                self._classify(frontaufteilung, STATE_TERMINAL, path + [f"IMOSDOORSINFO.FRONTAUFTEILUNG={frontaufteilung}"],
                               "IMOSDOORSINFO", "FRONTAUFTEILUNG")

            situname = normalize(row.get("SITUNAME"))
            if situname:
                self._classify(situname, STATE_CONNECTIONS, path + [f"IMOSDOORSINFO.SITUNAME={situname}"],
                               "IMOSDOORSINFO", "SITUNAME")

            self._imosdoorsingle_branch_foldslide(name, path)

    def _imosdoorsingle_branch_foldslide(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_IMOSDOORSINGLE_FOLDSLIDE
        branch = BRANCHES[STATE_IMOSDOORSINGLE_FOLDSLIDE]
        rows = _fetch_branch(branch, name)
        for row in rows:
            btausp = normalize(row.get("BTAUSP"))
            if btausp:
                self._resolve_then(btausp, path + [f"IMOSDOORSINGLE.BTAUSP={btausp}"], self._kms_branch)
            for col in ("SITUNAMEGRIFF", "SITUNAMEGRIFF1", "SITUNAMEGRIFF2"):
                val = normalize(row.get(col))
                if val:
                    self._resolve_then(val, path + [f"IMOSDOORSINGLE.{col}={val}"], self._griff_branch)

    def _imosdoorsinfo_branch_tambour(self, name, path, type_value):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_IMOSDOORSINFO_TAMBOUR_V
        branch = BRANCHES[STATE_IMOSDOORSINFO_TAMBOUR_V]
        rows = _fetch_branch(branch, name)
        for row in rows:
            if not self._int_in(row.get("TYPE"), (type_value,)):
                continue

            situname = normalize(row.get("SITUNAME"))
            if situname:
                self._classify(situname, STATE_CONNECTIONS, path + [f"IMOSDOORSINFO.SITUNAME={situname}"],
                               "IMOSDOORSINFO", "SITUNAME")

            left = self._int_in(row.get("USETUERLINKS"), (0,))
            left1 = self._int_in(row.get("USETUERLINKS"), (1,))
            right = self._int_in(row.get("USETUERRECHTS"), (0,))
            right1 = self._int_in(row.get("USETUERRECHTS"), (1,))

            if left and right1:
                tuerpos_filter = "AND TUERPOS = 2"
            elif left1 and right:
                tuerpos_filter = "AND TUERPOS = 1"
            elif left1 and right1:
                tuerpos_filter = ""
            else:
                continue

            single_rows = query(
                "SELECT SITUNAMEGRIFF, SITUNAMEGRIFF1, SITUNAMEGRIFF2 FROM dbo.[IMOSDOORSINGLE] "
                "WHERE NAME = ? AND (NULLIF(LTRIM(RTRIM(INORDER)), N'') IS NULL) " + tuerpos_filter,
                (name,)
            )
            for srow in single_rows:
                for col in ("SITUNAMEGRIFF", "SITUNAMEGRIFF1", "SITUNAMEGRIFF2"):
                    val = normalize(srow.get(col))
                    if val:
                        self._resolve_then(val, path + [f"IMOSDOORSINGLE.{col}={val}"], self._griff_branch)

    def _anglzone_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_ANGLZONE, STATE_IDENT, STATE_CABIN
        branch = BRANCHES[STATE_ANGLZONE]
        rows = _fetch_branch(branch, name)
        for row in rows:
            for col in ("MANINFOTS", "MANINFOBS"):
                val = normalize(row.get(col))
                if val:
                    self._generic_branch(val, STATE_IDENT, path + [f"anglzone.{col}={val}"])
            for col in ("TOPSHELF", "BOTSHELF"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_CABIN, path + [f"anglzone.{col}={val}"], "anglzone", col)

    def _cabin_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_CABIN
        branch = BRANCHES[STATE_CABIN]
        rows = _fetch_branch(branch, name)
        for row in rows:
            if self._int_in(row.get("KONSTTYP"), (8,)):
                continue

            for col in ("UEBERST_R", "UEBERST_L", "UEBERST_V", "UEBERST_H", "SHOEHE"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"CABIN.{col}={val}"], "CABIN", col)

            cpinfo = normalize(row.get("CPINFO"))
            if cpinfo:
                self._generic_branch(cpinfo, STATE_IDENT, path + [f"CABIN.CPINFO={cpinfo}"])

            nut = normalize(row.get("NUT_ERB"))
            if nut:
                self._nut_erb_branch(nut, path + [f"CABIN.NUT_ERB={nut}"])

            kms = normalize(row.get("KMS"))
            if kms:
                self._resolve_then(kms, path + [f"CABIN.KMS={kms}"], self._kms_branch)

            self._cabin_cpconnprim_branch(name, path)

    def _cabin_cpconnprim_branch(self, name, path):
        prim_rows = query(
            "SELECT ONLYONECON FROM dbo.[CPCONNPRIM] WHERE NAME = ? AND TYPE = 3",
            (name,)
        )
        if not prim_rows:
            return

        if self._int_in(prim_rows[0].get("ONLYONECON"), (1,)):
            rows = query(
                "SELECT CONNECTID FROM dbo.[CPCONNLIST] "
                "WHERE NAME = ? AND TYPE = 3 AND CONNNUM = 0",
                (name,)
            )
        else:
            rows = query(
                "SELECT CONNECTID FROM dbo.[CPCONNLIST] "
                "WHERE NAME = ? AND TYPE = 3 AND CONNNUM IN (0, 1)",
                (name,)
            )

        for row in rows:
            cid = normalize(row.get("CONNECTID"))
            if cid:
                self._resolve_then(cid, path + [f"CPCONNLIST.CONNECTID={cid}"], self._connections_match)

    def _connections_match(self, value, path):
        self._classify(value, STATE_CONNECTIONS, path, "CPCONNLIST", "CONNECTID")

    def _anglzone_branch_rail(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_ANGLZONE_RAIL, STATE_IDENT, STATE_CABIN_RAIL
        branch = BRANCHES[STATE_ANGLZONE_RAIL]
        rows = _fetch_branch(branch, name)
        for row in rows:
            for col in ("MANINFOTS", "MANINFOBS"):
                val = normalize(row.get(col))
                if val:
                    self._generic_branch(val, STATE_IDENT, path + [f"anglzone.{col}={val}"])
            for col in ("TOPSHELF", "BOTSHELF"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_CABIN_RAIL, path + [f"anglzone.{col}={val}"], "anglzone", col)

    def _cabin_branch_rail(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_CABIN_RAIL, STATE_IDENT
        branch = BRANCHES[STATE_CABIN_RAIL]
        rows = _fetch_branch(branch, name)
        for row in rows:
            if not self._int_in(row.get("KONSTTYP"), (8,)):
                continue

            val = normalize(row.get("SHOEHE"))
            if val:
                self._classify(val, STATE_TERMINAL, path + [f"CABIN.SHOEHE={val}"], "CABIN", "SHOEHE")

            cpinfo = normalize(row.get("CPINFO"))
            if cpinfo:
                self._generic_branch(cpinfo, STATE_IDENT, path + [f"CABIN.CPINFO={cpinfo}"])

            self._cabin_cpconnprim_branch_rail(name, path)
            self._traverse_branch_rail(name, path)

    def _cabin_cpconnprim_branch_rail(self, name, path):
        prim_rows = query(
            "SELECT ONLYONECON FROM dbo.[CPCONNPRIM] WHERE NAME = ? AND TYPE = 3",
            (name,)
        )
        if not prim_rows:
            return

        if self._int_in(prim_rows[0].get("ONLYONECON"), (1,)):
            rows = query(
                "SELECT CONNECTID FROM dbo.[CPCONNLIST] "
                "WHERE NAME = ? AND TYPE = 3 AND CONNNUM = 0",
                (name,)
            )
        else:
            rows = query(
                "SELECT CONNECTID FROM dbo.[CPCONNLIST] "
                "WHERE NAME = ? AND TYPE = 3",
                (name,)
            )

        for row in rows:
            cid = normalize(row.get("CONNECTID"))
            if cid:
                self._resolve_then(cid, path + [f"CPCONNLIST.CONNECTID={cid}"], self._connections_match)

    def _traverse_branch_rail(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_TRAVERSE_RAIL
        branch = BRANCHES[STATE_TRAVERSE_RAIL]
        rows = _fetch_branch(branch, name)
        for row in rows:
            kms_vorne = normalize(row.get("KMS_VORNE"))
            if kms_vorne:
                self._resolve_then(kms_vorne, path + [f"TRAVERSE.KMS_VORNE={kms_vorne}"], self._kms_branch)
                for col in ("UEBERST_RV", "UEBERST_LV", "SCONDFRON", "STIEF_VORN"):
                    val = normalize(row.get(col))
                    if val:
                        self._classify(val, STATE_TERMINAL, path + [f"TRAVERSE.{col}={val}"], "TRAVERSE", col)

            kms_hinten = normalize(row.get("KMS_HINTEN"))
            if kms_hinten:
                self._resolve_then(kms_hinten, path + [f"TRAVERSE.KMS_HINTEN={kms_hinten}"], self._kms_branch)
                for col in ("UEBERST_RH", "UEBERST_LH", "SCONDBACK", "STIEF_HINT"):
                    val = normalize(row.get(col))
                    if val:
                        self._classify(val, STATE_TERMINAL, path + [f"TRAVERSE.{col}={val}"], "TRAVERSE", col)

    def _anglzone_branch_panel_shelf(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_ANGLZONE_PANEL_SHELF, STATE_IDENT, STATE_CABIN
        branch = BRANCHES[STATE_ANGLZONE_PANEL_SHELF]
        rows = _fetch_branch(branch, name)
        for row in rows:
            maninfodi = normalize(row.get("MANINFODI"))
            if maninfodi:
                self._generic_branch(maninfodi, STATE_IDENT, path + [f"anglzone.MANINFODI={maninfodi}"])

            lindiv1 = normalize(row.get("LINDIV1"))
            if lindiv1:
                self._classify(lindiv1, STATE_TERMINAL, path + [f"anglzone.LINDIV1={lindiv1}"], "anglzone", "LINDIV1")

            divtype = (normalize(row.get("DIVTYPE")) or "").upper()
            if divtype in ("T", "B"):
                divider = normalize(row.get("DIVIDER"))
                if divider:
                    self._classify(divider, STATE_CABIN, path + [f"anglzone.DIVIDER={divider}"], "anglzone", "DIVIDER")

    def _anglzone_branch_rail_shelf(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_ANGLZONE_RAIL_SHELF, STATE_IDENT, STATE_CABIN_RAIL
        branch = BRANCHES[STATE_ANGLZONE_RAIL_SHELF]
        rows = _fetch_branch(branch, name)
        for row in rows:
            maninfodi = normalize(row.get("MANINFODI"))
            if maninfodi:
                self._generic_branch(maninfodi, STATE_IDENT, path + [f"anglzone.MANINFODI={maninfodi}"])

            lindiv1 = normalize(row.get("LINDIV1"))
            if lindiv1:
                self._classify(lindiv1, STATE_TERMINAL, path + [f"anglzone.LINDIV1={lindiv1}"], "anglzone", "LINDIV1")

            divtype = (normalize(row.get("DIVTYPE")) or "").upper()
            if divtype in ("T", "B"):
                divider = normalize(row.get("DIVIDER"))
                if divider:
                    self._classify(divider, STATE_CABIN_RAIL, path + [f"anglzone.DIVIDER={divider}"], "anglzone", "DIVIDER")

    def _anglzone_branch_fix_panel_shelf(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_ANGLZONE_FIX_PANEL_SHELF, STATE_IDENT, STATE_CABIN_FIX_PANEL_SHELF
        branch = BRANCHES[STATE_ANGLZONE_FIX_PANEL_SHELF]
        rows = _fetch_branch(branch, name)
        for row in rows:
            maninfodi = normalize(row.get("MANINFODI"))
            if maninfodi:
                self._generic_branch(maninfodi, STATE_IDENT, path + [f"anglzone.MANINFODI={maninfodi}"])

            lindiv1 = normalize(row.get("LINDIV1"))
            if lindiv1:
                self._classify(lindiv1, STATE_TERMINAL, path + [f"anglzone.LINDIV1={lindiv1}"], "anglzone", "LINDIV1")

            divtype = (normalize(row.get("DIVTYPE")) or "").upper()
            if divtype == "F":
                divider = normalize(row.get("DIVIDER"))
                if divider:
                    self._classify(divider, STATE_CABIN_FIX_PANEL_SHELF, path + [f"anglzone.DIVIDER={divider}"],
                                   "anglzone", "DIVIDER")

    def _anglzone_branch_fix_rail_shelf(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_ANGLZONE_FIX_RAIL_SHELF, STATE_IDENT, STATE_CABIN_FIX_RAIL_SHELF
        branch = BRANCHES[STATE_ANGLZONE_FIX_RAIL_SHELF]
        rows = _fetch_branch(branch, name)
        for row in rows:
            maninfodi = normalize(row.get("MANINFODI"))
            if maninfodi:
                self._generic_branch(maninfodi, STATE_IDENT, path + [f"anglzone.MANINFODI={maninfodi}"])

            lindiv1 = normalize(row.get("LINDIV1"))
            if lindiv1:
                self._classify(lindiv1, STATE_TERMINAL, path + [f"anglzone.LINDIV1={lindiv1}"], "anglzone", "LINDIV1")

            divtype = (normalize(row.get("DIVTYPE")) or "").upper()
            if divtype == "F":
                divider = normalize(row.get("DIVIDER"))
                if divider:
                    self._classify(divider, STATE_CABIN_FIX_RAIL_SHELF, path + [f"anglzone.DIVIDER={divider}"],
                                   "anglzone", "DIVIDER")

    def _cabin_branch_fix_panel_shelf(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_CABIN_FIX_PANEL_SHELF
        branch = BRANCHES[STATE_CABIN_FIX_PANEL_SHELF]
        rows = _fetch_branch(branch, name)
        for row in rows:
            if self._int_in(row.get("KONSTTYP"), (8,)):
                continue

            for col in ("UEBERST_R", "UEBERST_L", "UEBERST_V", "UEBERST_H", "SMINABLOCH"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"CABIN.{col}={val}"], "CABIN", col)

            cpinfo = normalize(row.get("CPINFO"))
            if cpinfo:
                self._generic_branch(cpinfo, STATE_IDENT, path + [f"CABIN.CPINFO={cpinfo}"])

            nut = normalize(row.get("NUT_ERB"))
            if nut:
                self._nut_erb_branch(nut, path + [f"CABIN.NUT_ERB={nut}"])

            kms = normalize(row.get("KMS"))
            if kms:
                self._resolve_then(kms, path + [f"CABIN.KMS={kms}"], self._kms_branch)

            self._cabin_cpconnprim_branch(name, path)

    def _cabin_branch_fix_rail_shelf(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_CABIN_FIX_RAIL_SHELF
        branch = BRANCHES[STATE_CABIN_FIX_RAIL_SHELF]
        rows = _fetch_branch(branch, name)
        for row in rows:
            if not self._int_in(row.get("KONSTTYP"), (8,)):
                continue

            cpinfo = normalize(row.get("CPINFO"))
            if cpinfo:
                self._generic_branch(cpinfo, STATE_IDENT, path + [f"CABIN.CPINFO={cpinfo}"])

            self._cabin_cpconnprim_branch_rail(name, path)
            self._traverse_branch_fix_rail_shelf(name, path)

    def _traverse_branch_fix_rail_shelf(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_TRAVERSE_FIX_RAIL_SHELF
        branch = BRANCHES[STATE_TRAVERSE_FIX_RAIL_SHELF]
        rows = _fetch_branch(branch, name)
        for row in rows:
            kms_vorne = normalize(row.get("KMS_VORNE"))
            if kms_vorne:
                self._resolve_then(kms_vorne, path + [f"TRAVERSE.KMS_VORNE={kms_vorne}"], self._kms_branch)
                for col in ("UEBERST_RV", "UEBERST_LV", "SCONDFRON", "STIEF_VORN"):
                    val = normalize(row.get(col))
                    if val:
                        self._classify(val, STATE_TERMINAL, path + [f"TRAVERSE.{col}={val}"], "TRAVERSE", col)

            kms_hinten = normalize(row.get("KMS_HINTEN"))
            if kms_hinten:
                self._resolve_then(kms_hinten, path + [f"TRAVERSE.KMS_HINTEN={kms_hinten}"], self._kms_branch)
                for col in ("UEBERST_RH", "UEBERST_LH", "SCONDBACK", "STIEF_HINT"):
                    val = normalize(row.get(col))
                    if val:
                        self._classify(val, STATE_TERMINAL, path + [f"TRAVERSE.{col}={val}"], "TRAVERSE", col)

    def _anglzone_branch_adjustable_shelf(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_ANGLZONE_ADJUSTABLE_SHELF, STATE_IDENT, STATE_CABIN_ADJUSTABLE_SHELF
        branch = BRANCHES[STATE_ANGLZONE_ADJUSTABLE_SHELF]
        rows = _fetch_branch(branch, name)
        for row in rows:
            maninfodi = normalize(row.get("MANINFODI"))
            if maninfodi:
                self._generic_branch(maninfodi, STATE_IDENT, path + [f"anglzone.MANINFODI={maninfodi}"])

            lindiv1 = normalize(row.get("LINDIV1"))
            if lindiv1:
                self._classify(lindiv1, STATE_TERMINAL, path + [f"anglzone.LINDIV1={lindiv1}"], "anglzone", "LINDIV1")

            divtype = (normalize(row.get("DIVTYPE")) or "").upper()
            if divtype == "A":
                divider = normalize(row.get("DIVIDER"))
                if divider:
                    self._classify(divider, STATE_CABIN_ADJUSTABLE_SHELF, path + [f"anglzone.DIVIDER={divider}"],
                                   "anglzone", "DIVIDER")

    def _anglzone_branch_partition(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_ANGLZONE_PARTITION, STATE_IDENT, STATE_CABIN
        branch = BRANCHES[STATE_ANGLZONE_PARTITION]
        rows = _fetch_branch(branch, name)
        for row in rows:
            maninfodi = normalize(row.get("MANINFODI"))
            if maninfodi:
                self._generic_branch(maninfodi, STATE_IDENT, path + [f"anglzone.MANINFODI={maninfodi}"])

            divtype = (normalize(row.get("DIVTYPE")) or "").upper()
            if divtype == "P":
                divider = normalize(row.get("DIVIDER"))
                if divider:
                    self._classify(divider, STATE_CABIN, path + [f"anglzone.DIVIDER={divider}"],
                                   "anglzone", "DIVIDER")

            hordeftype = row.get("HORDEFTYPE")
            if self._int_in(hordeftype, (2,)):
                cols = ("LINDIV1", "LINDIV2")
            elif (normalize(hordeftype) or "").upper() == "A":
                cols = ("LINDIV1", "SDIVANGLE")
            else:
                cols = ("LINDIV1",)
            for col in cols:
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"anglzone.{col}={val}"], "anglzone", col)

    def _anglzone_branch_side_partition(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_ANGLZONE_SIDE_PARTITION, STATE_IDENT, STATE_CSIDE
        branch = BRANCHES[STATE_ANGLZONE_SIDE_PARTITION]
        rows = _fetch_branch(branch, name)
        for row in rows:
            maninfodi = normalize(row.get("MANINFODI"))
            if maninfodi:
                self._generic_branch(maninfodi, STATE_IDENT, path + [f"anglzone.MANINFODI={maninfodi}"])

            divtype = (normalize(row.get("DIVTYPE")) or "").upper()
            if divtype in ("S", "D"):
                divider = normalize(row.get("DIVIDER"))
                if divider:
                    self._classify(divider, STATE_CSIDE, path + [f"anglzone.DIVIDER={divider}"],
                                   "anglzone", "DIVIDER")

            hordeftype = row.get("HORDEFTYPE")
            if self._int_in(hordeftype, (2,)):
                cols = ("LINDIV1", "LINDIV2")
            elif (normalize(hordeftype) or "").upper() == "A":
                cols = ("LINDIV1", "SDIVANGLE")
            else:
                cols = ("LINDIV1",)
            for col in cols:
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"anglzone.{col}={val}"], "anglzone", col)

    def _cabin_branch_adjustable_shelf(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        from core.branches import STATE_CABIN_ADJUSTABLE_SHELF
        branch = BRANCHES[STATE_CABIN_ADJUSTABLE_SHELF]
        rows = _fetch_branch(branch, name)
        for row in rows:
            if self._int_in(row.get("KONSTTYP"), (8,)):
                continue

            for col in ("UEBERST_R", "UEBERST_L", "UEBERST_V", "UEBERST_H", "SX_WINKEL", "SY_WINKEL"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_TERMINAL, path + [f"CABIN.{col}={val}"], "CABIN", col)

            cpinfo = normalize(row.get("CPINFO"))
            if cpinfo:
                self._generic_branch(cpinfo, STATE_IDENT, path + [f"CABIN.CPINFO={cpinfo}"])

            nut = normalize(row.get("NUT_ERB"))
            if nut:
                self._nut_erb_branch(nut, path + [f"CABIN.NUT_ERB={nut}"])

            kms = normalize(row.get("KMS"))
            if kms:
                self._resolve_then(kms, path + [f"CABIN.KMS={kms}"], self._kms_branch)

            self._cabin_cpconnprim_branch(name, path)

    def _doorsing_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_DOORSING]
        rows = _fetch_branch(branch, name)
        for row in rows:
            altlin = normalize(row.get("ALTLIN_BUFFER"))
            if altlin:
                self._classify(altlin, STATE_TERMINAL, path + [f"DOORSING.ALTLIN_BUFFER={altlin}"],
                               "DOORSING", "ALTLIN_BUFFER")
            for col in ("GRIFF_MITT", "GRIFF_L", "GRIFF_R"):
                val = normalize(row.get(col))
                if val:
                    self._classify(val, STATE_GRIFF, path + [f"DOORSING.{col}={val}"], "DOORSING", col)
            kms = normalize(row.get("KMS"))
            if kms:
                self._resolve_then(kms, path + [f"DOORSING.KMS={kms}"], self._kms_branch)

    def _griff_branch(self, name, path):
        if not name:
            return
        from core.traversal_base import _fetch_branch
        branch = BRANCHES[STATE_GRIFF]
        rows = _fetch_branch(branch, name)
        for row in rows:
            cid = normalize(row.get("CONNECTID"))
            if cid:
                self._classify(cid, STATE_CONNECTIONS, path + [f"GRIFF.CONNECTID={cid}"], "GRIFF", "CONNECTID")
            ph = normalize(row.get("PULLHEIGHT"))
            if ph:
                self._classify(ph, STATE_PULLHEIGHT, path + [f"GRIFF.PULLHEIGHT={ph}"], "GRIFF", "PULLHEIGHT")

    def _pullheight_branch(self, name, path):
        if not name:
            return
        rows = query(
            "SELECT PHTYPE, PHVALUE FROM dbo.[PULLHEIGHT] WHERE NAME = ?",
            (name,)
        )
        by_type = {}
        for row in rows:
            t = (normalize(row.get("PHTYPE")) or "").upper()
            if t:
                by_type[t] = row

        height_row = by_type.get("HEIGHT")
        if height_row:
            val = normalize(height_row.get("PHVALUE"))
            if val:
                self._classify(val, STATE_TERMINAL, path + [f"PULLHEIGHT.PHVALUE={val}"], "PULLHEIGHT", "PHVALUE")

        activate_row = by_type.get("ACTIVATE")
        if activate_row and normalize(activate_row.get("PHVALUE")) == "1":
            for t in ("DIST_BOT", "DIST_TOP", "SNAPRADIUS"):
                row = by_type.get(t)
                if row:
                    val = normalize(row.get("PHVALUE"))
                    if val:
                        self._classify(val, STATE_TERMINAL, path + [f"PULLHEIGHT.PHVALUE={val}"],
                                       "PULLHEIGHT", "PHVALUE")


class ArticleCategoryMixin:
    """articles → ARTICLECATEGORY → ARTICLECATEGORYATTRVALUE branches.
    Use together with AnglprimMixin (needs _resolve_then and _lng_branch)."""

    def _run_article_category(self, attr_name, lng_state):
        rows = query(
            "SELECT a.ARTICLECATEGORY_NAME FROM dbo.articles a "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(a.INORDER)), N'') IS NULL",
            (self.article,)
        )
        base = [f"articles({self.article})"]
        for row in rows:
            cat = normalize(row.get("ARTICLECATEGORY_NAME"))
            if cat:
                self._attr_value_branch(
                    cat, base + [f"articles.ARTICLECATEGORY_NAME={cat}"], attr_name, lng_state)
                continue
            for drow in query("SELECT ARTICLECATEGORY_NAME FROM dbo.ARTICLECATEGORY WHERE IS_DEFAULT = 1"):
                dcat = normalize(drow.get("ARTICLECATEGORY_NAME"))
                if dcat:
                    self._attr_value_branch(
                        dcat, base + [f"ARTICLECATEGORY.ARTICLECATEGORY_NAME={dcat}"], attr_name, lng_state)

    def _attr_values(self, category, name):
        rows = query(
            "SELECT [VALUE] FROM dbo.ARTICLECATEGORYATTRVALUE "
            "WHERE ARTICLECATEGORY_NAME = ? AND NAME = ?",
            (category, name)
        )
        return [v for v in (normalize(r.get("VALUE")) for r in rows) if v]

    def _attr_value_branch(self, category, path, attr_name, lng_state):
        for val in self._attr_values(category, "EinfuegeHoehe"):
            self._classify(val, STATE_TERMINAL, path + [f"ARTICLECATEGORYATTRVALUE.VALUE={val}"],
                           "ARTICLECATEGORYATTRVALUE", "VALUE")
        for val in self._attr_values(category, attr_name):
            self._resolve_then(
                val, path + [f"ARTICLECATEGORYATTRVALUE.VALUE={val}"],
                lambda v, p: self._lng_branch(v, p, lng_state),
            )