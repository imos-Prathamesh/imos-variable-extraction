# Source : ui/main_window.py
from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

CONFIG_FILE = ROOT / "config.json"

WORKFLOWS = ["anglconi", "anglclie", "anglgrtx", "— All Flows —"]

TYP_LABELS: dict[str, str] = {
    "30": "Family",         "25": "Article",               "12": "back",
    "37": "base",           "40": "Calculation_Principle", "29": "Color_Principle",
    "33": "Connection_Situation", "32": "Connector",       "39": "Crown_Moulding",
    "28": "Design_Parameter",    "13": "Door",             "31": "Drawer",
    "38": "Light_Valance",  "4":  "Material",              "100": "Number",
    "5":  "Part_Definition","2":  "Profile_Name",          "6":  "Pull",
    "7":  "Shelf_Partition","8":  "Side_Panel",            "35": "Stretchable_Purchase_Part",
    "3":  "Surface",        "120":"Text",                  "36": "Work_Surface",
}

def _load_cfg() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {"server": "", "database": "", "user": "", "password": ""}

def _apply_env(cfg: dict) -> None:
    os.environ["MSSQL_SERVER"]   = cfg.get("server",   "")
    os.environ["MSSQL_DATABASE"] = cfg.get("database", "")
    os.environ["MSSQL_USER"]     = cfg.get("user",     "")
    os.environ["MSSQL_PASSWORD"] = cfg.get("password", "")

def _reset_db_conn() -> None:
    try:
        import core.db as _db
        _db._conn = None
    except Exception:
        pass

def _find_free_port(start: int = 8080) -> int:
    for p in range(start, start + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", p))
                return p
            except OSError:
                continue
    return start

def _run_flow(workflow: str, article: str | None, all_arts: bool) -> list:
    flows = ["anglconi", "anglclie", "anglgrtx"] if workflow == "— All Flows —" else [workflow]
    out = []
    for wf in flows:
        if wf == "anglconi":
            if all_arts:
                from flows.traversal_anglconi import extract_all_articles
                for r in extract_all_articles():
                    out.extend(r.occurrences)
            else:
                from flows.traversal_anglconi import extract_article
                out.extend(extract_article(article).occurrences)
        elif wf == "anglclie":
            from flows.traversal_anglclie import extract_anglclie
            out.extend(extract_anglclie(article).occurrences)
        elif wf == "anglgrtx":
            from flows.traversal_anglgrtx import extract_anglgrtx
            out.extend(extract_anglgrtx(article).occurrences)
    return out

def _fetch_typ_map(var_names: list[str]) -> dict[str, str]:
    if not var_names:
        return {}
    try:
        from core.db import query
        ph = ",".join(["?"] * len(var_names))
        rows = query(
            f"SELECT NAME, TYP FROM dbo.IMOS "
            f"WHERE NAME IN ({ph}) "
            f"  AND NULLIF(LTRIM(RTRIM(ORDERID)), N'') IS NULL",
            tuple(var_names),
        )
        result: dict[str, str] = {}
        for r in rows:
            name = (r.get("NAME") or "").strip()
            typ  = str(r.get("TYP") or "").strip()
            if name and name not in result:
                result[name] = TYP_LABELS.get(typ, typ if typ else "—")
        return result
    except Exception:
        return {}

def _build_rows(occurrences: list, typ_map: dict) -> list[dict]:
    return [
        {
            "num":           i + 1,
            "article":       o.article,
            "var_type":      typ_map.get(o.variable_name, "—"),
            "variable_name": o.variable_name,
            "value":         o.value,
            "source_table":  o.source_table,
            "source_column": o.source_column,
            "resolved_via":  o.resolved_via,
        }
        for i, o in enumerate(occurrences)
    ]

# ── startup ────────────────────────────────────────────────────────────────────
_apply_env(_load_cfg())

from nicegui import ui  # noqa: E402

_all_rows: list[dict] = []
_filters: dict = {
    "article": "", "var_type": "", "variable_name": "",
    "value": "", "source_table": "", "source_column": "",
    "resolved_via": "", "search": "", "unique": False,
}

def _set_filter(key: str, val) -> None:
    _filters[key] = (val or "").strip().lower() if isinstance(val, str) else bool(val)
    _apply_filters()

# ── global styles ──────────────────────────────────────────────────────────────
ui.query("body").style("background:#f0f2f5; font-family:'Segoe UI',sans-serif")

ui.add_css("""
    /* ── tabs ── */
    .q-tabs { background:#ffffff !important; border-bottom:2px solid #e2e8f0 !important; }
    .q-tab { color:#64748b !important; font-weight:600 !important; font-size:13px !important; letter-spacing:0.04em !important; }
    .q-tab--active { color:#1e40af !important; }
    .q-tab__indicator { background:#1e40af !important; height:3px !important; }

    /* ── tab panels ── */
    .q-tab-panels { background:#f0f2f5 !important; }

    /* ── cards ── */
    .imos-card {
        background:#ffffff !important;
        border-radius:12px !important;
        border:1px solid #e2e8f0 !important;
        box-shadow:0 1px 6px rgba(0,0,0,0.06) !important;
    }

    /* ── inputs ── */
    .q-field__control { background:#f8fafc !important; border-radius:8px !important; }
    .q-field__native, .q-field__input { color:#1e293b !important; font-size:14px !important; }
    .q-field--outlined .q-field__control:before { border-color:#cbd5e1 !important; }
    .q-field--outlined .q-field__control:hover:before { border-color:#3b82f6 !important; }
    .q-field--outlined.q-field--focused .q-field__control:before { border-color:#1e40af !important; border-width:2px !important; }
    .q-field__label { color:#64748b !important; font-size:13px !important; }
    .q-field__append .q-icon { color:#94a3b8 !important; }

    /* ── checkbox ── */
    .q-checkbox__inner { color:#1e40af !important; }
    .q-checkbox__label { color:#374151 !important; font-size:13px !important; font-weight:500 !important; }

    /* ── table ── */
    .imos-table { background:#ffffff !important; border-radius:10px !important; border:1px solid #e2e8f0 !important; overflow:hidden !important; }
    .imos-table .q-table thead tr th {
        background:#f8fafc !important;
        color:#374151 !important;
        font-weight:700 !important;
        font-size:12px !important;
        letter-spacing:0.05em !important;
        text-transform:uppercase !important;
        border-bottom:2px solid #e2e8f0 !important;
        padding:10px 12px !important;
    }
    .imos-table .q-table tbody tr td { color:#1e293b !important; font-size:13px !important; padding:8px 12px !important; }
    .imos-table .q-table tbody tr { border-bottom:1px solid #f1f5f9 !important; }
    .imos-table .q-table tbody tr:hover td { background:#eff6ff !important; }

    /* ── buttons ── */
    .btn-primary { background:#1e40af !important; color:#ffffff !important; border-radius:8px !important; font-weight:600 !important; }
    .btn-secondary { background:#f1f5f9 !important; color:#374151 !important; border-radius:8px !important; font-weight:600 !important; border:1px solid #e2e8f0 !important; }
    .btn-danger { background:#fee2e2 !important; color:#dc2626 !important; border-radius:8px !important; font-weight:600 !important; }

    /* ── filter row inputs ── */
    .filter-input .q-field__control { background:#ffffff !important; border-radius:6px !important; }
    .filter-input .q-field__native { font-size:12px !important; color:#374151 !important; }

    /* ── badge ── */
    .env-badge {
        background:#fef3c7; color:#92400e;
        font-size:10px; font-weight:700;
        letter-spacing:0.08em;
        padding:3px 10px; border-radius:20px;
        border:1px solid #fcd34d;
    }
""")

# ── header ─────────────────────────────────────────────────────────────────────
with ui.header().style(
    "background:#ffffff; border-bottom:1px solid #e2e8f0; "
    "box-shadow:0 2px 8px rgba(0,0,0,0.06); padding:0"
):
    with ui.row().classes("items-center justify-between w-full q-px-xl").style("height:62px"):
        with ui.row().classes("items-center").style("gap:14px"):
            ui.label("💲").style("font-size:26px")
            with ui.column().style("gap:1px"):
                ui.label("imos iX Variable Extractor").style(
                    "font-size:18px; font-weight:700; color:#1e293b; letter-spacing:0.01em")
                ui.label("Developer — Prathamesh Patil").style(
                    "font-size:11px; color:#64748b; letter-spacing:0.04em")
        with ui.row().classes("items-center").style("gap:12px"):
            ui.html('<span class="env-badge">⚗ TEST ENVIRONMENT</span>')
            ui.label("$").style(
                "font-size:20px; font-weight:900; color:#1e40af; font-family:monospace; opacity:0.5")

# ── tabs ───────────────────────────────────────────────────────────────────────
with ui.tabs().classes("w-full") as tabs:
    t_settings = ui.tab("⚙  Settings")
    t_run      = ui.tab("▶  Run")
    t_results  = ui.tab("📋  Results")

with ui.tab_panels(tabs, value=t_settings).classes("w-full q-pa-xl"):

    # ── Settings ──────────────────────────────────────────────────────────────
    with ui.tab_panel(t_settings):
        with ui.element("div").classes("imos-card q-pa-lg").style("max-width:460px"):
            with ui.row().classes("items-center q-mb-md").style("gap:10px"):
                ui.element("div").style(
                    "width:4px; height:20px; background:#1e40af; border-radius:2px")
                ui.label("Database Credentials").style(
                    "font-size:15px; font-weight:700; color:#1e293b")

            cfg = _load_cfg()
            inp_server = ui.input("Server (HOST\\INSTANCE or IP,port)",
                                  value=cfg.get("server", "")).classes("w-full")
            inp_db     = ui.input("Database", value=cfg.get("database", "")).classes("w-full")
            inp_user   = ui.input("User",     value=cfg.get("user", "")).classes("w-full")
            inp_pass   = ui.input("Password", value=cfg.get("password", ""),
                                  password=True, password_toggle_button=True).classes("w-full")

            lbl_conn = ui.label("").style("font-size:12px; color:#64748b; min-height:18px")

            def on_save():
                new_cfg = {
                    "server": inp_server.value, "database": inp_db.value,
                    "user":   inp_user.value,   "password": inp_pass.value,
                }
                CONFIG_FILE.write_text(json.dumps(new_cfg, indent=2))
                _apply_env(new_cfg)
                _reset_db_conn()
                lbl_conn.style("color:#16a34a").set_text("✓ Credentials saved")

            def on_test():
                _reset_db_conn()
                lbl_conn.style("color:#64748b").set_text("Connecting…")
                try:
                    from core.db import get_connection
                    get_connection()
                    lbl_conn.style("color:#16a34a").set_text("✓ Connected successfully")
                except Exception as e:
                    lbl_conn.style("color:#dc2626").set_text(f"✗ {e}")

            with ui.row().classes("q-mt-md").style("gap:8px"):
                ui.button("Save", on_click=on_save).classes("btn-secondary").props("unelevated")
                ui.button("Test Connection", on_click=on_test).classes("btn-primary").props("unelevated")

    # ── Run ───────────────────────────────────────────────────────────────────
    with ui.tab_panel(t_run):
        with ui.element("div").classes("imos-card q-pa-lg").style("max-width:460px"):
            with ui.row().classes("items-center q-mb-md").style("gap:10px"):
                ui.element("div").style(
                    "width:4px; height:20px; background:#1e40af; border-radius:2px")
                ui.label("Extract Variables").style(
                    "font-size:15px; font-weight:700; color:#1e293b")

            sel_article  = ui.select([], label="Article", with_input=True).classes("w-full")
            chk_all      = ui.checkbox("All Articles").classes("q-mt-xs")
            sel_workflow = ui.select(WORKFLOWS, label="Workflow", value="anglconi").classes("w-full q-mt-sm")
            lbl_run      = ui.label("").style("font-size:12px; color:#64748b; min-height:18px")

            chk_all.on("update:modelValue", lambda e: sel_article.set_enabled(not e.args))

            def on_load():
                lbl_run.style("color:#64748b").set_text("Loading…")
                try:
                    from core.db import query
                    rows = query("SELECT DISTINCT NAME FROM dbo.articles ORDER BY NAME")
                    names = [r["NAME"] for r in rows if r.get("NAME")]
                    sel_article.options = names
                    sel_article.update()
                    lbl_run.style("color:#16a34a").set_text(f"✓ {len(names)} articles loaded")
                except Exception as e:
                    lbl_run.style("color:#dc2626").set_text(f"✗ {e}")

            def on_run():
                global _all_rows
                lbl_run.style("color:#2563eb").set_text("Running extraction…")
                try:
                    art = sel_article.value if not chk_all.value else None
                    if not chk_all.value and not art:
                        lbl_run.style("color:#d97706").set_text("⚠ Select an article or check All Articles")
                        return
                    occ       = _run_flow(sel_workflow.value, art, chk_all.value)
                    var_names = list({o.variable_name for o in occ})
                    typ_map   = _fetch_typ_map(var_names)
                    _all_rows = _build_rows(occ, typ_map)
                    lbl_run.style("color:#16a34a").set_text(f"✓ {len(_all_rows)} occurrences found")
                    _apply_filters()
                    tabs.set_value(t_results)
                except Exception as e:
                    lbl_run.style("color:#dc2626").set_text(f"✗ {e}")

            with ui.row().classes("q-mt-md").style("gap:8px"):
                ui.button("Load Articles", on_click=on_load).classes("btn-secondary").props("unelevated")
                ui.button("Run", on_click=on_run).classes("btn-primary").props("unelevated")

    # ── Results ───────────────────────────────────────────────────────────────
    with ui.tab_panel(t_results):

        # top bar
        with ui.row().classes("items-center w-full q-mb-sm").style("gap:16px; flex-wrap:wrap"):
            lbl_count = ui.label("No results").style(
                "font-size:13px; font-weight:700; color:#1e40af; "
                "background:#eff6ff; padding:4px 12px; border-radius:20px; "
                "border:1px solid #bfdbfe")
            chk_unique = ui.checkbox("Unique Variables Only",
                                     on_change=lambda e: _set_filter("unique", e.value))
            inp_search = ui.input(placeholder="🔍  Search variable name…",
                                  on_change=lambda e: _set_filter("search", e.value)
                                  ).props("dense outlined clearable").style("width:260px").classes("filter-input")

        # filter bar
        with ui.element("div").classes("imos-card q-pa-sm q-mb-sm"):
            with ui.row().classes("items-center").style("gap:6px; flex-wrap:wrap"):
                ui.label("FILTER").style(
                    "font-size:10px; font-weight:700; color:#1e40af; "
                    "letter-spacing:0.1em; min-width:44px")
                f_article = ui.input(placeholder="Article",  on_change=lambda e: _set_filter("article",       e.value)).props("dense outlined clearable").style("width:120px").classes("filter-input")
                f_vartype = ui.input(placeholder="Var Type", on_change=lambda e: _set_filter("var_type",      e.value)).props("dense outlined clearable").style("width:120px").classes("filter-input")
                f_varname = ui.input(placeholder="Variable", on_change=lambda e: _set_filter("variable_name", e.value)).props("dense outlined clearable").style("width:120px").classes("filter-input")
                f_value   = ui.input(placeholder="Value",    on_change=lambda e: _set_filter("value",         e.value)).props("dense outlined clearable").style("width:120px").classes("filter-input")
                f_table   = ui.input(placeholder="Table",    on_change=lambda e: _set_filter("source_table",  e.value)).props("dense outlined clearable").style("width:100px").classes("filter-input")
                f_col     = ui.input(placeholder="Column",   on_change=lambda e: _set_filter("source_column", e.value)).props("dense outlined clearable").style("width:100px").classes("filter-input")
                f_via     = ui.input(placeholder="Via",      on_change=lambda e: _set_filter("resolved_via",  e.value)).props("dense outlined clearable").style("width:80px").classes("filter-input")
                ui.button("Clear", on_click=lambda: _clear_filters()).classes("btn-danger").props("unelevated dense")

        # table
        tbl = ui.table(
            columns=[
                {"name": "num",           "label": "#",         "field": "num",           "align": "right",
                 "style": "width:50px; color:#94a3b8; font-family:monospace; font-weight:700"},
                {"name": "article",       "label": "Article",   "field": "article",       "align": "left", "sortable": True},
                {"name": "var_type",      "label": "Var. Type", "field": "var_type",      "align": "left", "sortable": True},
                {"name": "variable_name", "label": "Variable",  "field": "variable_name", "align": "left", "sortable": True},
                {"name": "value",         "label": "Value",     "field": "value",         "align": "left", "sortable": True},
                {"name": "source_table",  "label": "Table",     "field": "source_table",  "align": "left", "sortable": True},
                {"name": "source_column", "label": "Column",    "field": "source_column", "align": "left", "sortable": True},
                {"name": "resolved_via",  "label": "Via",       "field": "resolved_via",  "align": "left", "sortable": True},
            ],
            rows=[],
            row_key="num",
            pagination={"rowsPerPage": 100},
        ).classes("imos-table w-full").props("dense flat virtual-scroll")

        tbl.add_slot("body-cell-variable_name", """
            <q-td :props="props"
                  style="cursor:pointer; font-family:monospace; font-weight:600;
                         color:#1e40af; font-size:13px"
                  title="Click to copy"
                  @click="() => {
                      navigator.clipboard.writeText(props.value);
                      $q.notify({ message: '$ ' + props.value + ' copied',
                                  timeout: 1200, color: 'blue-8',
                                  position: 'top-right', icon: 'content_copy' });
                  }">
                <span style="opacity:0.4; margin-right:2px">$</span>{{ props.value }}
            </q-td>
        """)

        tbl.add_slot("body-cell-value", """
            <q-td :props="props"
                  style="cursor:pointer; color:#047857; font-family:monospace; font-size:13px"
                  title="Click to copy"
                  @click="() => {
                      navigator.clipboard.writeText(props.value);
                      $q.notify({ message: 'Copied',
                                  timeout: 800, color: 'teal-8',
                                  position: 'top-right', icon: 'content_copy' });
                  }">
                {{ props.value }}
            </q-td>
        """)

        ui.label("💲 Click any Variable or Value cell to copy to clipboard").style(
            "font-size:11px; color:#94a3b8; margin-top:6px")


# ── filter logic ───────────────────────────────────────────────────────────────

def _apply_filters() -> None:
    rows = list(_all_rows)

    if _filters["unique"]:
        seen: set[str] = set()
        unique: list[dict] = []
        for r in rows:
            if r["variable_name"] not in seen:
                seen.add(r["variable_name"])
                unique.append(r)
        rows = unique

    if _filters["search"]:
        rows = [r for r in rows if _filters["search"] in r["variable_name"].lower()]

    for field in ("article", "var_type", "variable_name", "value",
                  "source_table", "source_column", "resolved_via"):
        v = _filters[field]
        if v:
            rows = [r for r in rows if v in str(r.get(field, "")).lower()]

    for i, r in enumerate(rows):
        rows[i] = {**r, "num": i + 1}

    tbl.rows = rows
    tbl.update()
    lbl_count.set_text(f"{len(rows)} / {len(_all_rows)} variables")


def _clear_filters() -> None:
    for key in ("article", "var_type", "variable_name", "value",
                "source_table", "source_column", "resolved_via", "search"):
        _filters[key] = ""
    _filters["unique"] = False
    for w in (f_article, f_vartype, f_varname, f_value, f_table, f_col, f_via, inp_search):
        w.set_value("")
    chk_unique.set_value(False)
    _apply_filters()


port = _find_free_port(8080)
ui.run(title="imos iX Variable Extractor", port=port, reload=False, favicon="💲")