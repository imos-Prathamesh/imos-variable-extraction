# Source : flows/traversal_anglzone_article_zone.py
# Analogy: Flow entry point — anglzone.NAME -> DIVDIR='A' -> DIVIDER; resolves $/#
# (DESC_TYPE 11/30 only, flow-local) then re-feeds any raw value as a new
# articles.NAME across every registered articles.NAME flow.
"""anglzone_article_zone flow: articles.NAME -> anglzone.NAME -> DIVDIR='A' -> DIVIDER
   -> resolves $variable / #descriptor (DESC_TYPE 11 or 30 only; flow-specific,
      does NOT touch core._fetch_descriptor used by every other flow)
   -> any raw (non-$, non-#) value is treated as a new articles.NAME and re-run
      through every flow currently registered in core.flow_registry, merging
      results back into this same article's result."""
from __future__ import annotations

from core.db import query, normalize
from core.parser import parse
from core.traversal_base import BaseTraversal, ExtractionResult, _fetch_imos


def _fetch_descriptor_zone(name: str) -> list[str]:
    """Flow-specific descriptor resolution, used only by this flow.
    DESC_TYPE=11 -> all DESCRIPTORVALUES rows.
    DESC_TYPE=30 -> only rows WHERE COMMENT='DEFAULT'.
    Any other DESC_TYPE (or no DESCRIPTOR row) -> stop, no rows.
    Does NOT replace or alter core.traversal_base._fetch_descriptor, which
    every other flow continues to use unchanged."""
    desc_rows = query(
        "SELECT DESC_TYPE FROM dbo.[DESCRIPTOR] "
        "WHERE NAME = ? AND NULLIF(LTRIM(RTRIM(INORDER)), N'') IS NULL",
        (name,)
    )
    if not desc_rows:
        return []
    try:
        desc_type = int(desc_rows[0].get("DESC_TYPE"))
    except (TypeError, ValueError):
        return []

    if desc_type == 11:
        rows = query(
            "SELECT dv.LINDIV FROM dbo.[DESCRIPTORVALUES] dv "
            "WHERE dv.NAME = ? ORDER BY dv.NODENUM, dv.CONDITIONID",
            (name,)
        )
    elif desc_type == 30:
        rows = query(
            "SELECT dv.LINDIV FROM dbo.[DESCRIPTORVALUES] dv "
            "WHERE dv.NAME = ? AND dv.COMMENT = 'DEFAULT' "
            "ORDER BY dv.NODENUM, dv.CONDITIONID",
            (name,)
        )
    else:
        return []

    out = []
    for r in rows:
        v = normalize(r["LINDIV"])
        if v:
            out.append(v)
    return out


class TraversalAnglzoneArticleZone(BaseTraversal):

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT az.NAME, az.DIVDIR, az.DIVIDER "
            "FROM dbo.articles a "
            "JOIN dbo.anglzone az "
            "  ON az.NAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(a.INORDER)), N'') IS NULL "
            "  AND NULLIF(LTRIM(RTRIM(az.INORDER)), N'') IS NULL",
            (self.article,)
        )
        for row in rows:
            path = [f"anglzone({self.article})"]
            divdir = (normalize(row.get("DIVDIR")) or "").upper()
            if divdir != "A":
                continue
            divider = normalize(row.get("DIVIDER"))
            if divider:
                self._resolve_zone(divider, path + [f"anglzone.DIVIDER={divider}"],
                                    "anglzone", "DIVIDER")
        return self.result

    def _resolve_zone(self, value, path, source_table, source_column):
        """Flow-local $/# resolution (mirrors core._classify but uses
        _fetch_descriptor_zone instead of core._fetch_descriptor), ending
        with re-entry of any raw value as a new article."""
        if len(path) > self.max_depth:
            return

        pv = parse(value)
        if pv is None:
            return

        for varname in pv.variables:
            state_key = ("ZONE_IMOS", varname)
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
                        self._resolve_zone(wert, rec_path, "IMOS", "WERT")
            self._active.discard(state_key)

        for descname in pv.descriptors:
            state_key = ("ZONE_DESCRIPTOR", descname)
            if state_key in self._active:
                self.result.cycles.append(f"CYCLE: {' → '.join(path)} → #DESCRIPTOR({descname})")
                continue
            self._active.add(state_key)
            new_path = path + [f"#DESCRIPTOR({descname})"]
            lindiv_values = _fetch_descriptor_zone(descname)
            for lindiv in lindiv_values:
                rec_path = new_path + [f"LINDIV={lindiv}"]
                self._resolve_zone(lindiv, rec_path, "DESCRIPTORVALUES", "LINDIV")
            self._active.discard(state_key)

        if pv.is_raw:
            self._reenter_as_article(value, path)


def extract_anglzone_article_zone(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglzoneArticleZone(article, max_depth).run()


FLOW_NAME = "anglzone_article_zone"
extract = extract_anglzone_article_zone


def extract_all_anglzone_article_zone(max_depth: int = 40) -> list[ExtractionResult]:
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
            results.append(extract_anglzone_article_zone(name, max_depth))
    return results


extract_all = extract_all_anglzone_article_zone