"""anglclie flow: articles.NAME → anglclie.TAGVALUE → IMOS loop"""
from __future__ import annotations
from dataclasses import dataclass, field
from db import query, normalize
from parser import parse
from traversal import ExtractionResult, OccurrenceRow, _fetch_imos, _fetch_descriptor
from branches import STATE_IMOS, STATE_DESCRIPTOR, STATE_CONNECTIONS


class TraversalAnglclie:
    def __init__(self, article: str, max_depth: int = 40):
        self.article = article
        self.max_depth = max_depth
        self.result = ExtractionResult(article=article)
        self._active: set[tuple[str, str]] = set()

    def run(self) -> ExtractionResult:
        rows = query(
            "SELECT ac.TAGVALUE "
            "FROM dbo.articles a "
            "JOIN dbo.anglclie ac "
            "  ON ac.NAME = a.NAME COLLATE Latin1_General_CI_AS "
            "WHERE a.NAME = ? "
            "  AND NULLIF(LTRIM(RTRIM(ac.INORDER)), N'') IS NULL",
            (self.article,)
        )
        for row in rows:
            tagvalue = normalize(row["TAGVALUE"])
            if tagvalue:
                path = [f"anglclie({self.article})", f"TAGVALUE={tagvalue}"]
                self._classify(tagvalue, path, "anglclie", "TAGVALUE")
        return self.result

    def _classify(self, value: str, path: list[str],
                  source_table: str, source_column: str) -> None:
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
                self._classify(wert, rec_path, "IMOS", "WERT")
            self._active.discard(state_key)

        for descname in pv.descriptors:
            state_key = (STATE_DESCRIPTOR, descname)
            if state_key in self._active:
                continue
            self._active.add(state_key)
            new_path = path + [f"#DESCRIPTOR({descname})"]
            for lindiv in _fetch_descriptor(descname):
                self._classify(lindiv, new_path + [f"LINDIV={lindiv}"],
                               "DESCRIPTORVALUES", "LINDIV")
            self._active.discard(state_key)

    def _record(self, varname, value, path, source_table,
                source_column, resolved_via) -> None:
        self.result.occurrences.append(OccurrenceRow(
            article=self.article, path=list(path),
            variable_name=varname, value=value,
            source_table=source_table, source_column=source_column,
            resolved_via=resolved_via,
        ))
        self.result.unique_vars[varname] = value


def extract_anglclie(article: str, max_depth: int = 40) -> ExtractionResult:
    return TraversalAnglclie(article, max_depth).run()