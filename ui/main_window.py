# Source : ui/main_window.py
# Analogy: The dashboard — Settings / Run / Results. Flow list is no longer
# hardcoded; it comes from core/flow_registry.py, so new flows (with
# FLOW_NAME + extract()) appear here automatically without editing this file.
#
# NOTE: NiceGUI 3.x requires all UI to be built inside an @ui.page() handler
# (module-level UI building is no longer reliably attached to the page).
from __future__ import annotations

import json
import os
import re
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

CONFIG_FILE = ROOT / "config.json"

ALL_FLOWS_LABEL = "— All Flows —"

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

# (key, label, width %, sortable, filterable) — shared by custom header and table columns
_RES_COLS: list[tuple] = [
    ("expand",        "",          4,  False, False),
    ("num",           "#",         5,  False, False),
    ("article",       "Article",   13, True,  True),
    ("var_type",      "Var. Type", 10, True,  True),
    ("variable_name", "Variable",  18, True,  True),
    ("value",         "Value",     13, True,  True),
    ("origin",        "Origin",    15, True,  True),
    ("source_table",  "Table",     7,  True,  True),
    ("source_column", "Column",    8,  True,  True),
    ("resolved_via",  "Via",       7,  True,  True),
]

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

def _workflow_options() -> list[str]:
    from core.flow_registry import flow_names
    names = flow_names()
    if not names:
        return [ALL_FLOWS_LABEL]
    return names + [ALL_FLOWS_LABEL]

def _run_flow(workflows: list[str], article: str | None, all_arts: bool,
               articles: list[str] | None = None) -> list:
    from core.flow_registry import get_registry
    registry = get_registry()
    selected = list(registry.keys()) if ALL_FLOWS_LABEL in workflows else workflows
    out = []
    for wf in selected:
        info = registry.get(wf)
        if info is None:
            continue
        print(f"\n  ▶ Running flow: {wf}")
        if all_arts:
            if info.extract_all is None:
                continue
            for r in info.extract_all():
                out.extend(r.occurrences)
        elif articles:
            for art in articles:
                out.extend(info.extract(art).occurrences)
        else:
            res = info.extract(article)
            for o in res.occurrences:
                print(f"    {wf}  →  {o.variable_name} = {o.value}")
            out.extend(res.occurrences)
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

def _parse_origin(path: list, var_name: str) -> str:
    marker = f"$IMOS({var_name})"
    try:
        idx = path.index(marker)
    except ValueError:
        return "—"
    if idx == 0:
        return "—"
    col_seg = path[idx - 1]
    if "=" not in col_seg:
        return "—"
    left, _, _ = col_seg.partition("=")
    if "." in left:
        return left
    column = left
    table = None
    for seg in reversed(path[:idx - 1]):
        if seg.startswith("$IMOS("):
            table = "IMOS"
            break
        if seg.startswith("#DESCRIPTOR("):
            table = "DESCRIPTORVALUES"
            break
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\(', seg)
        if m:
            table = m.group(1)
            break
    return f"{table or '?'}.{column}"


def _build_rows(occurrences: list, typ_map: dict) -> list[dict]:
    return [
        {
            "num":           i + 1,
            "article":       o.article,
            "var_type":      typ_map.get(o.variable_name, "—"),
            "variable_name": o.variable_name,
            "value":         o.value,
            "origin":        _parse_origin(o.path, o.variable_name),
            "source_table":  o.source_table,
            "source_column": o.source_column,
            "resolved_via":  o.resolved_via,
            "path":          o.path_str(),
        }
        for i, o in enumerate(occurrences)
    ]

_apply_env(_load_cfg())

from nicegui import ui  # noqa: E402


_CSS = """
    :root {
        --imos-primary:      #4f46e5;
        --imos-primary-dark: #3730a3;
        --imos-accent:       #f59e0b;
        --imos-success:      #059669;
        --imos-danger:       #e11d48;
        --imos-bg:           #f4f5fb;
        --imos-surface:      #ffffff;
        --imos-border:       #e4e6f1;
        --imos-text:         #1e1b3a;
        --imos-muted:        #6b7086;
    }
    body { background:var(--imos-bg) !important; }
    .q-tabs { background:var(--imos-surface) !important; border-bottom:2px solid var(--imos-border) !important; }
    .q-tab { color:var(--imos-muted) !important; font-weight:600 !important; font-size:13px !important; letter-spacing:0.04em !important; }
    .q-tab--active { color:var(--imos-primary) !important; }
    .q-tab__indicator { background:linear-gradient(90deg, var(--imos-primary), var(--imos-accent)) !important; height:3px !important; }
    .q-tab-panels { background:var(--imos-bg) !important; }
    .imos-card {
        background:var(--imos-surface) !important;
        border-radius:14px !important;
        border:1px solid var(--imos-border) !important;
        box-shadow:0 4px 16px rgba(79,70,229,0.06) !important;
    }
    .q-field__control { background:#f7f7fc !important; border-radius:9px !important; }
    .q-field__native, .q-field__input { color:var(--imos-text) !important; font-size:14px !important; }
    .q-field--outlined .q-field__control:before { border-color:#d6d8ea !important; }
    .q-field--outlined .q-field__control:hover:before { border-color:var(--imos-primary) !important; }
    .q-field--outlined.q-field--focused .q-field__control:before { border-color:var(--imos-primary) !important; border-width:2px !important; }
    .q-field__label { color:var(--imos-muted) !important; font-size:13px !important; }
    .q-field__append .q-icon { color:#a0a3bd !important; }
    .q-checkbox__inner { color:var(--imos-primary) !important; }
    .q-checkbox__label { color:#3d3f57 !important; font-size:13px !important; font-weight:500 !important; }
    .btn-primary .q-btn__content .block, .btn-orange .q-btn__content .block, .btn-danger .q-btn__content .block {
        color:#000000 !important;
        font-weight:800 !important;
    }
    .imos-table { background:var(--imos-surface) !important; border-radius:12px !important; border:1px solid var(--imos-border) !important; overflow:hidden !important; }
    .imos-table .q-table { table-layout:fixed !important; width:100% !important; }
    .imos-table .q-table tbody tr td {
        color:var(--imos-text) !important; font-size:13px !important; padding:8px 12px !important;
        overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
    }
    .imos-table .q-table tbody tr { border-bottom:1px solid #f0f0f8 !important; }
    .imos-table .q-table tbody tr:hover td { background:#eef0ff !important; }
    .btn-primary, .btn-orange, .btn-secondary, .btn-danger {
        background:#f97316 !important;
        color:#000000 !important;
        border-radius:9px !important;
        font-weight:800 !important;
        border:1px solid #c2410c !important;
        box-shadow:0 2px 8px rgba(249,115,22,0.4) !important;
    }
    .btn-primary .q-btn__content, .btn-orange .q-btn__content,
    .btn-secondary .q-btn__content, .btn-danger .q-btn__content {
        color:#000000 !important;
        font-weight:800 !important;
    }
    .btn-blue {
        background:#2563eb !important;
        color:#000000 !important;
        border-radius:9px !important;
        font-weight:800 !important;
        border:1px solid #1e3a8a !important;
        box-shadow:0 2px 8px rgba(37,99,235,0.4) !important;
    }
    .btn-blue .q-btn__content {
        color:#000000 !important;
        font-weight:800 !important;
    }
    .filter-input .q-field__control { background:var(--imos-surface) !important; border-radius:7px !important; }
    .filter-input .q-field__native { font-size:12px !important; color:#3d3f57 !important; }
    .env-badge {
        background:#fff3cf; color:#8a5a00;
        font-size:10px; font-weight:700;
        letter-spacing:0.08em;
        padding:3px 10px; border-radius:20px;
        border:1px solid #f7d374;
    }
    .imos-header-badge {
        font-size:12px; font-weight:700; color:var(--imos-primary-dark);
        background:#eef0ff; padding:5px 14px; border-radius:20px;
        border:1px solid #cfd3fb;
    }
    .imos-count-badge {
        font-size:13px; font-weight:700; color:var(--imos-primary-dark);
        background:#eef0ff; padding:4px 12px; border-radius:20px;
        border:1px solid #cfd3fb;
    }
"""

ui.add_css(_CSS, shared=True)


@ui.page("/")
def index_page() -> None:
    ui.query("body").style("font-family:'Segoe UI',sans-serif")

    _all_rows: list[dict] = []
    _last_run: dict = {}
    _filters: dict = {
        "article": "", "var_type": "", "variable_name": "",
        "value": "", "source_table": "", "source_column": "",
        "resolved_via": "", "search": "", "unique": False,
    }
    _results_filters: dict = {}
    _results_sort: dict = {"col": None, "desc": False}
    _family_state: dict = {
        "full_tree": [], "expanded": set(), "filters": {},
        "matches": [], "match_idx": -1, "selected": None,
    }

    # ── header ───────────────────────────────────────────────────────────
    with ui.header().style(
        "background:linear-gradient(90deg, #ffffff, #f7f7ff); border-bottom:1px solid #e4e6f1; "
        "box-shadow:0 2px 10px rgba(79,70,229,0.08); padding:0"
    ):
        with ui.row().classes("items-center justify-between w-full q-px-xl").style("height:62px"):
            with ui.row().classes("items-center").style("gap:14px"):
                ui.label("💠").style("font-size:26px")
                with ui.column().style("gap:1px"):
                    ui.label("imos iX Variable Extractor").style(
                        "font-size:18px; font-weight:700; color:#1e1b3a; letter-spacing:0.01em")
                    ui.label("Developer — Prathamesh Patil").style(
                        "font-size:11px; color:#6b7086; letter-spacing:0.04em")
            with ui.row().classes("items-center").style("gap:12px"):
                _hdr_cfg = _load_cfg()
                lbl_hdr_conn = ui.label(f"🖥 {_hdr_cfg.get('server','—')}  ›  {_hdr_cfg.get('database','—')}").classes(
                    "imos-header-badge")
                ui.html('<span class="env-badge">⚗ TEST ENVIRONMENT</span>')
                ui.label("$").style(
                    "font-size:20px; font-weight:900; color:#4f46e5; font-family:monospace; opacity:0.5")

    # ── tabs ─────────────────────────────────────────────────────────────
    with ui.tabs().classes("w-full") as tabs:
        t_settings = ui.tab("⚙  Settings")
        t_run      = ui.tab("▶  Run")
        t_results  = ui.tab("📋  Results")
        t_family   = ui.tab("🌳  Family Structure")

    with ui.tab_panels(tabs, value=t_settings).classes("w-full q-pa-xl"):

        # ── Settings ─────────────────────────────────────────────────────
        with ui.tab_panel(t_settings):
            with ui.element("div").classes("imos-card q-pa-lg").style("max-width:460px"):
                with ui.row().classes("items-center q-mb-md").style("gap:10px"):
                    ui.element("div").style(
                        "width:4px; height:20px; background:linear-gradient(180deg,#4f46e5,#f59e0b); border-radius:2px")
                    ui.label("Database Credentials").style(
                        "font-size:15px; font-weight:700; color:#1e1b3a")

                cfg = _load_cfg()
                sel_server = ui.select([cfg.get("server", "")] if cfg.get("server") else [],
                                       label="Server (HOST\\INSTANCE or IP,port)",
                                       value=cfg.get("server", ""), with_input=True,
                                       new_value_mode="add-unique").classes("w-full")

                sel_db = ui.select([cfg.get("database", "")] if cfg.get("database") else [],
                                   label="Database",
                                   value=cfg.get("database", ""), with_input=True,
                                   new_value_mode="add-unique").classes("w-full q-mt-sm")
                inp_user = ui.input("User", value=cfg.get("user", "")).classes("w-full")
                inp_pass = ui.input("Password", value=cfg.get("password", ""),
                                    password=True, password_toggle_button=True).classes("w-full")

                lbl_conn = ui.label("").style("font-size:12px; color:#6b7086; min-height:18px")

                _servers_scanned = {"done": False}
                _dbs_loaded_for = {"key": None}

                def on_discover_servers():
                    if _servers_scanned["done"]:
                        return
                    _servers_scanned["done"] = True
                    lbl_conn.style("color:#6b7086").set_text("Scanning network (this can take a few seconds)…")
                    try:
                        from core.db import discover_sql_servers
                        found = discover_sql_servers()
                        if found:
                            sel_server.set_options(found)
                            lbl_conn.style("color:#059669").set_text(f"✓ Found {len(found)} server(s)")
                        else:
                            lbl_conn.style("color:#b45309").set_text(
                                "⚠ No servers responded (they may block discovery broadcasts — type the server manually)")
                    except Exception as e:
                        lbl_conn.style("color:#e11d48").set_text(f"✗ {e}")

                sel_server.on("popup-show", lambda: on_discover_servers())

                def on_load_dbs():
                    if not sel_server.value or not inp_user.value:
                        lbl_conn.style("color:#b45309").set_text(
                            "⚠ Enter Server and User first, then click Database again")
                        return
                    key = (sel_server.value, inp_user.value, inp_pass.value)
                    if _dbs_loaded_for["key"] == key:
                        return
                    lbl_conn.style("color:#6b7086").set_text("Loading database list…")
                    try:
                        from core.db import list_databases
                        names = list_databases(sel_server.value, inp_user.value, inp_pass.value)
                        sel_db.set_options(names)
                        _dbs_loaded_for["key"] = key
                        lbl_conn.style("color:#059669").set_text(f"✓ {len(names)} database(s) found")
                    except Exception as e:
                        lbl_conn.style("color:#e11d48").set_text(f"✗ {e}")

                sel_db.on("popup-show", lambda: on_load_dbs())

                def on_save():
                    new_cfg = {
                        "server": sel_server.value, "database": sel_db.value,
                        "user": inp_user.value, "password": inp_pass.value,
                    }
                    CONFIG_FILE.write_text(json.dumps(new_cfg, indent=2))
                    _apply_env(new_cfg)
                    _reset_db_conn()
                    lbl_conn.style("color:#059669").set_text("✓ Credentials saved")
                    lbl_hdr_conn.set_text(f"🖥 {new_cfg.get('server','—')}  ›  {new_cfg.get('database','—')}")

                def on_test():
                    _reset_db_conn()
                    lbl_conn.style("color:#6b7086").set_text("Connecting…")
                    try:
                        from core.db import get_connection
                        get_connection()
                        lbl_conn.style("color:#059669").set_text("✓ Connected successfully")
                    except Exception as e:
                        lbl_conn.style("color:#e11d48").set_text(f"✗ {e}")

                with ui.row().classes("q-mt-md").style("gap:8px"):
                    ui.button("Save", on_click=on_save).classes("btn-primary").props(
                        "unelevated color=orange-8 text-color=black")
                    ui.button("Test Connection", on_click=on_test).classes("btn-primary").props(
                        "unelevated color=orange-8 text-color=black")

        # ── Run ──────────────────────────────────────────────────────────
        with ui.tab_panel(t_run):
            with ui.element("div").classes("imos-card q-pa-lg").style("max-width:460px"):
                with ui.row().classes("items-center q-mb-md").style("gap:10px"):
                    ui.element("div").style(
                        "width:4px; height:20px; background:linear-gradient(180deg,#4f46e5,#f59e0b); border-radius:2px")
                    ui.label("Extract Variables").style(
                        "font-size:15px; font-weight:700; color:#1e1b3a")

                sel_article  = ui.select([], label="Article", with_input=True).classes("w-full")
                sel_articles_multi = ui.select([], label="Articles", multiple=True,
                                               with_input=True).classes("w-full").props("use-chips")
                sel_articles_multi.set_visibility(False)
                chk_multi = ui.checkbox("Multiple Articles").classes("q-mt-xs")
                chk_all   = ui.checkbox("All Articles").classes("q-mt-xs")
                sel_workflow = ui.select(_workflow_options(), label="Workflow",
                                         value=ALL_FLOWS_LABEL).classes("w-full q-mt-sm")
                sel_workflow_multi = ui.select(_workflow_options(), label="Workflows", multiple=True,
                                               with_input=True).classes("w-full q-mt-sm").props("use-chips")
                sel_workflow_multi.set_visibility(False)
                chk_multi_wf = ui.checkbox("Multiple Workflows").classes("q-mt-xs")
                lbl_run      = ui.label("").style("font-size:12px; color:#6b7086; min-height:18px")

                _articles_loaded = {"done": False}

                def _load_articles():
                    if _articles_loaded["done"]:
                        return
                    _articles_loaded["done"] = True
                    lbl_run.style("color:#6b7086").set_text("Loading articles…")
                    try:
                        from core.db import query
                        rows = query(
                            "SELECT DISTINCT NAME FROM dbo.articles "
                            "WHERE NULLIF(LTRIM(RTRIM(INORDER)), N'') IS NULL ORDER BY NAME"
                        )
                        names = [r["NAME"] for r in rows if r.get("NAME")]
                        sel_article.options = names
                        sel_article.update()
                        sel_articles_multi.options = names
                        sel_articles_multi.update()
                        lbl_run.style("color:#059669").set_text(f"✓ {len(names)} articles loaded")
                    except Exception as e:
                        _articles_loaded["done"] = False
                        lbl_run.style("color:#e11d48").set_text(f"✗ {e}")

                ui.timer(0.1, _load_articles, once=True)

                def _refresh_article_visibility():
                    if chk_all.value:
                        sel_article.set_visibility(False)
                        sel_articles_multi.set_visibility(False)
                    elif chk_multi.value:
                        sel_article.set_visibility(False)
                        sel_articles_multi.set_visibility(True)
                    else:
                        sel_article.set_visibility(True)
                        sel_articles_multi.set_visibility(False)
                    sel_article.update()
                    sel_articles_multi.update()

                def on_toggle_multi(e):
                    if e.args:
                        chk_all.value = False
                    _refresh_article_visibility()

                def on_toggle_all(e):
                    if e.args:
                        chk_multi.value = False
                    _refresh_article_visibility()

                chk_multi.on("update:modelValue", on_toggle_multi)
                chk_all.on("update:modelValue", on_toggle_all)

                def _refresh_workflow_visibility():
                    if chk_multi_wf.value:
                        sel_workflow.set_visibility(False)
                        sel_workflow_multi.set_visibility(True)
                    else:
                        sel_workflow.set_visibility(True)
                        sel_workflow_multi.set_visibility(False)
                    sel_workflow.update()
                    sel_workflow_multi.update()

                chk_multi_wf.on("update:modelValue", lambda e: _refresh_workflow_visibility())

                def on_refresh_flows():
                    from core.flow_registry import reset_registry
                    reset_registry()
                    opts = _workflow_options()
                    sel_workflow.options = opts
                    sel_workflow.update()
                    sel_workflow_multi.options = opts
                    sel_workflow_multi.update()

                sel_workflow.on("popup-show", lambda: on_refresh_flows())
                sel_workflow_multi.on("popup-show", lambda: on_refresh_flows())

                prog_run = ui.linear_progress(value=0, show_value=False).classes("q-mt-sm")
                prog_run.style(
                    "border-radius:6px; height:8px; "
                    "--q-primary:#f59e0b; background:#fde7c2")
                prog_run.set_visibility(False)

                async def _execute_run(workflows, art, all_arts, arts, switch_tab: bool):
                    nonlocal _all_rows, _last_run
                    from nicegui import run as nicegui_run

                    lbl_run.style("color:#4f46e5").set_text("Running extraction…")
                    prog_run.set_visibility(True)
                    prog_run.set_value(0)
                    anim_task = ui.timer(0.15, lambda: prog_run.set_value(
                        0.08 if prog_run.value >= 0.9 else prog_run.value + 0.08))
                    try:
                        occ       = await nicegui_run.io_bound(
                            _run_flow, workflows, art, all_arts, arts)
                        var_names = list({o.variable_name for o in occ})
                        typ_map   = await nicegui_run.io_bound(_fetch_typ_map, var_names)
                        _all_rows = _build_rows(occ, typ_map)
                        prog_run.set_value(1.0)
                        lbl_run.style("color:#059669").set_text(f"✓ {len(_all_rows)} occurrences found")
                        _last_run = {"workflows": workflows, "art": art, "all_arts": all_arts, "arts": arts}
                        btn_rerun.set_visibility(True)
                        if ALL_FLOWS_LABEL in workflows:
                            flow_text = "Flow: All Flows"
                        elif len(workflows) == 1:
                            flow_text = f"Flow: {workflows[0]}"
                        else:
                            flow_text = f"Flows: {', '.join(workflows)}"
                        lbl_flow_indicator.set_text(flow_text)
                        _results_filters.clear()
                        _render_results_header()
                        _apply_filters()
                        await _rebuild_family_tree()
                        if switch_tab:
                            tabs.set_value(t_results)
                    except Exception as e:
                        lbl_run.style("color:#e11d48").set_text(f"✗ {e}")
                    finally:
                        anim_task.cancel()
                        prog_run.set_visibility(False)

                async def on_run():
                    art  = None
                    arts = None
                    if chk_all.value:
                        pass
                    elif chk_multi.value:
                        arts = sel_articles_multi.value or []
                        if not arts:
                            lbl_run.style("color:#b45309").set_text("⚠ Select at least one article")
                            return
                    else:
                        art = sel_article.value
                        if not art:
                            lbl_run.style("color:#b45309").set_text("⚠ Select an article or check All Articles")
                            return

                    if chk_multi_wf.value:
                        workflows = sel_workflow_multi.value or []
                        if not workflows:
                            lbl_run.style("color:#b45309").set_text("⚠ Select at least one workflow")
                            return
                    else:
                        workflows = [sel_workflow.value]

                    await _execute_run(workflows, art, chk_all.value, arts, switch_tab=True)

                async def on_rerun():
                    if not _last_run:
                        return
                    await _execute_run(_last_run["workflows"], _last_run["art"],
                                        _last_run["all_arts"], _last_run["arts"], switch_tab=False)

                with ui.row().classes("q-mt-md").style("gap:8px"):
                    ui.button("RUN", on_click=on_run).classes("btn-orange").props(
                        "unelevated color=orange-8 text-color=black")

        # ── Results ──────────────────────────────────────────────────────
        with ui.tab_panel(t_results):

            with ui.row().classes("items-center w-full q-mb-sm").style("gap:16px; flex-wrap:wrap"):
                lbl_count = ui.label("No results").classes("imos-count-badge")
                btn_rerun = ui.button("⟳ Rerun", on_click=lambda: on_rerun()).classes(
                    "btn-orange").props("unelevated dense color=orange-8 text-color=black")
                btn_rerun.set_visibility(False)
                chk_unique = ui.checkbox("Unique Variables Only",
                                         on_change=lambda e: _set_filter("unique", e.value))
                inp_search = ui.input(placeholder="🔍  Search variable name…",
                                      on_change=lambda e: _set_filter("search", e.value)
                                      ).props("dense outlined clearable").style("width:260px").classes("filter-input")
                ui.space()
                lbl_flow_indicator = ui.label("Flow: —").classes("imos-header-badge")

            with ui.element("div").classes("imos-card q-pa-sm q-mb-sm"):
                with ui.row().classes("items-center").style("gap:6px; flex-wrap:wrap"):
                    ui.label("FILTER").style(
                        "font-size:10px; font-weight:700; color:#4f46e5; "
                        "letter-spacing:0.1em; min-width:44px")
                    f_article = ui.input(placeholder="Article",  on_change=lambda e: _set_filter("article",       e.value)).props("dense outlined clearable").style("width:120px").classes("filter-input")
                    f_vartype = ui.input(placeholder="Var Type", on_change=lambda e: _set_filter("var_type",      e.value)).props("dense outlined clearable").style("width:120px").classes("filter-input")
                    f_varname = ui.input(placeholder="Variable", on_change=lambda e: _set_filter("variable_name", e.value)).props("dense outlined clearable").style("width:120px").classes("filter-input")
                    f_value   = ui.input(placeholder="Value",    on_change=lambda e: _set_filter("value",         e.value)).props("dense outlined clearable").style("width:120px").classes("filter-input")
                    f_table   = ui.input(placeholder="Table",    on_change=lambda e: _set_filter("source_table",  e.value)).props("dense outlined clearable").style("width:100px").classes("filter-input")
                    f_col     = ui.input(placeholder="Column",   on_change=lambda e: _set_filter("source_column", e.value)).props("dense outlined clearable").style("width:100px").classes("filter-input")
                    f_via     = ui.input(placeholder="Via",      on_change=lambda e: _set_filter("resolved_via",  e.value)).props("dense outlined clearable").style("width:80px").classes("filter-input")
                    ui.button("Clear", on_click=lambda: _clear_filters()).classes("btn-danger").props(
                        "unelevated dense color=orange-8 text-color=black")

            # custom header row (native NiceGUI buttons → reliable click handling)
            results_header = ui.row().classes("w-full no-wrap").style(
                "gap:0; background:linear-gradient(180deg,#f7f7fd,#f0f0fa); "
                "border:1px solid #e4e6f1; border-bottom:2px solid #e4e6f1; "
                "border-radius:12px 12px 0 0; box-sizing:border-box")

            tbl = ui.table(
                columns=[
                    {"name": key, "label": label, "field": key,
                     "align": "right" if key == "num" else ("center" if key == "expand" else "left"),
                     "style": f"width:{width}%"
                              + ("; color:#a0a3bd; font-family:monospace; font-weight:700" if key == "num" else "")}
                    for key, label, width, _s, _f in _RES_COLS
                ],
                rows=[],
                row_key="num",
                pagination={"rowsPerPage": 100},
            ).classes("imos-table w-full").props("dense flat hide-header").style(
                "border-top:none !important; border-radius:0 0 12px 12px !important")

            tbl.add_slot("body", """
                <q-tr :props="props">
                    <q-td v-for="col in props.cols" :key="col.name" :props="props">
                        <template v-if="col.name === 'expand'">
                            <q-btn flat dense round size="sm"
                                   :icon="props.expand ? 'expand_less' : 'expand_more'"
                                   @click="props.expand = !props.expand" />
                        </template>
                        <template v-else-if="col.name === 'variable_name'">
                            <span style="cursor:pointer; font-family:monospace; font-weight:600; color:#4f46e5; font-size:13px"
                                  title="Click to copy"
                                  @click="() => { navigator.clipboard.writeText(props.value);
                                      $q.notify({ message: '$ ' + props.value + ' copied', timeout: 1200,
                                                  color: 'indigo-8', position: 'top-right', icon: 'content_copy' }); }">
                                <span style="opacity:0.4; margin-right:2px">$</span>{{ col.value }}
                            </span>
                        </template>
                        <template v-else-if="col.name === 'value'">
                            <span style="cursor:pointer; color:#059669; font-family:monospace; font-size:13px"
                                  title="Click to copy"
                                  @click="() => { navigator.clipboard.writeText(props.value);
                                      $q.notify({ message: 'Copied', timeout: 800, color: 'teal-8',
                                                  position: 'top-right', icon: 'content_copy' }); }">
                                {{ col.value }}
                            </span>
                        </template>
                        <template v-else>
                            {{ col.value }}
                        </template>
                    </q-td>
                </q-tr>
                <q-tr v-if="props.expand" :props="props">
                    <q-td colspan="100%" style="background:#f7f7fd; padding:10px 16px">
                        <div style="font-size:10px; font-weight:700; color:#4f46e5; letter-spacing:0.08em; margin-bottom:4px">
                            RESOLUTION PATH
                        </div>
                        <div style="font-family:monospace; font-size:12px; color:#3d3f57; white-space:pre-wrap; word-break:break-word">
                            {{ props.row.path }}
                        </div>
                    </q-td>
                </q-tr>
            """)

            ui.label("💠 Click any Variable or Value cell to copy to clipboard").style(
                "font-size:11px; color:#a0a3bd; margin-top:6px")

        # ── Family Structure ────────────────────────────────────────────
        with ui.tab_panel(t_family):
            with ui.row().classes("items-center justify-between w-full q-mb-sm").style("gap:10px; flex-wrap:wrap"):
                with ui.row().classes("items-center").style("gap:10px"):
                    lbl_family_count = ui.label("No data — click Refresh").classes("imos-count-badge")
                    inp_family_search = ui.input(
                        placeholder="🔍  Find/Go to…",
                        on_change=lambda e: _do_search(e.value)
                    ).props("dense outlined clearable").style("width:420px").classes("filter-input")
                    ui.button(icon="arrow_upward", on_click=lambda: _go_to_match(-1)).props(
                        "flat dense round size=sm")
                    ui.button(icon="arrow_downward", on_click=lambda: _go_to_match(1)).props(
                        "flat dense round size=sm")
                    lbl_search_status = ui.label("").style("font-size:12px; font-weight:700; min-width:140px")
                with ui.row().classes("items-center").style("gap:8px"):
                    ui.button(icon="unfold_more", on_click=lambda: _expand_all_family()).props(
                        "flat dense round").tooltip("Expand All")
                    ui.button(icon="unfold_less", on_click=lambda: _collapse_all_family()).props(
                        "flat dense round").tooltip("Collapse All")
                    ui.button("Clear All Filters", on_click=lambda: _clear_all_family_filters()).classes(
                        "btn-blue").props("unelevated dense")
                    ui.button("⟳ Refresh", on_click=lambda: on_family_refresh()).classes(
                        "btn-blue").props("unelevated dense")

            family_container = ui.column().classes("imos-card w-full").style("gap:0; overflow:auto")

    # ── results filter / sort logic (closures over this page's state) ──────

    def _set_filter(key: str, val) -> None:
        _filters[key] = (val or "").strip().lower() if isinstance(val, str) else bool(val)
        _apply_filters()

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

        for col, allowed in _results_filters.items():
            rows = [r for r in rows if str(r.get(col, "")) in allowed]

        sort_col = _results_sort["col"]
        if sort_col:
            rows = sorted(rows, key=lambda r: str(r.get(sort_col, "")).lower(),
                          reverse=_results_sort["desc"])

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
        _results_filters.clear()
        _results_sort["col"] = None
        _results_sort["desc"] = False
        _render_results_header()
        _apply_filters()

    def _results_distinct_values(col: str, skip: str | None = None) -> list:
        pool = list(_all_rows)
        for c, allowed in _results_filters.items():
            if c == skip:
                continue
            pool = [r for r in pool if str(r.get(c, "")) in allowed]
        return sorted({str(r.get(col, "")) for r in pool})

    def _active_filter_cols() -> set:
        active = set()
        for c, allowed in _results_filters.items():
            if set(allowed) != set(_results_distinct_values(c, skip=c)):
                active.add(c)
        return active

    def _toggle_results_sort(col_key: str) -> None:
        if _results_sort["col"] != col_key:
            _results_sort["col"] = col_key
            _results_sort["desc"] = False
        elif not _results_sort["desc"]:
            _results_sort["desc"] = True
        else:
            _results_sort["col"] = None
            _results_sort["desc"] = False
        _render_results_header()
        _apply_filters()

    def _render_results_header() -> None:
        results_header.clear()
        active = _active_filter_cols()
        with results_header:
            for key, label, width, sortable, filterable in _RES_COLS:
                justify = "flex-end" if key == "num" else "flex-start"
                with ui.row().classes("items-center no-wrap").style(
                        f"width:{width}%; padding:8px 12px; gap:2px; box-sizing:border-box; "
                        f"justify-content:{justify}; overflow:hidden"):
                    ui.label(label).style(
                        "font-size:12px; font-weight:700; color:#3d3f57; "
                        "text-transform:uppercase; letter-spacing:0.05em; white-space:nowrap")
                    if sortable:
                        if _results_sort["col"] == key:
                            s_icon = "arrow_downward" if _results_sort["desc"] else "arrow_upward"
                            s_color = "indigo-8"
                        else:
                            s_icon = "unfold_more"
                            s_color = "grey-6"
                        ui.button(icon=s_icon, on_click=lambda k=key: _toggle_results_sort(k)).props(
                            f"flat dense round size=xs color={s_color}")
                    if filterable:
                        f_color = "red-6" if key in active else "grey-7"
                        ui.button(icon="filter_alt", on_click=lambda k=key: _open_results_filter_menu(k)).props(
                            f"flat dense round size=xs color={f_color}")

    def _open_results_filter_menu(col_key: str) -> None:
        values = _results_distinct_values(col_key, skip=col_key)
        current = _results_filters.get(col_key)
        checked = set(current) if current is not None else set(values)
        checks: dict[str, object] = {}
        col_label = next((c[1] for c in _RES_COLS if c[0] == col_key), col_key)

        def toggle(v: str, val: bool):
            if val:
                checked.add(v)
            else:
                checked.discard(v)

        with ui.dialog() as dlg, ui.card().style("min-width:280px"):
            dlg.props("persistent")
            ui.label(f"Filter: {col_label}").style("font-weight:700; font-size:13px")
            box_search = ui.input(placeholder="Search values…").props("dense outlined clearable").classes("w-full q-mt-xs")
            list_area = ui.column().style("max-height:260px; overflow:auto; gap:2px")

            def render_list(filter_text: str = ""):
                list_area.clear()
                checks.clear()
                ft = (filter_text or "").strip().lower()
                with list_area:
                    for v in values:
                        shown = v if v else "(blank)"
                        if ft and ft not in shown.lower():
                            continue
                        checks[v] = ui.checkbox(shown, value=(v in checked),
                                                 on_change=lambda e, v=v: toggle(v, e.value))

            box_search.on("update:model-value", lambda e: render_list(box_search.value or ""))
            render_list()

            def select_all():
                checked.update(values)
                render_list(box_search.value or "")

            def select_none():
                checked.clear()
                render_list(box_search.value or "")

            def apply_and_close():
                _results_filters[col_key] = set(checked)
                dlg.close()
                _render_results_header()
                _apply_filters()

            def cancel():
                dlg.close()

            with ui.row().classes("q-mt-sm").style("gap:8px"):
                ui.button("Select All", on_click=select_all).props("flat dense")
                ui.button("Clear (Hide All)", on_click=select_none).props("flat dense")
                ui.button("Cancel", on_click=cancel).props("flat dense")
                ui.button("Apply", on_click=apply_and_close).classes("btn-orange").props(
                    "unelevated dense color=orange-8 text-color=black")
        dlg.open()

    # ── family tree logic (closures over this page's state) ────────────────

    def _flatten_all(nodes: list) -> list:
        out = []
        for n in nodes:
            out.append(n)
            out.extend(_flatten_all(n.get("children", [])))
        return out

    def _col_field(col: str) -> str:
        return "label" if col == "name" else col

    def _node_matches_filters(n: dict, skip_col: str | None = None) -> bool:
        for col, allowed in _family_state["filters"].items():
            if col == skip_col:
                continue
            if str(n.get(_col_field(col), "")) not in allowed:
                return False
        return True

    def _prune(nodes: list) -> list:
        out = []
        for n in nodes:
            kids = _prune(n.get("children", []))
            if _node_matches_filters(n) or kids:
                nn = dict(n)
                nn["children"] = kids
                out.append(nn)
        return out

    def _distinct_values(col: str) -> list:
        field = _col_field(col)
        pool = [n for n in _flatten_all(_family_state["full_tree"]) if _node_matches_filters(n, skip_col=col)]
        vals = {str(n.get(field, "")) for n in pool if str(n.get(field, "")).strip()}
        return sorted(vals)

    def _clear_all_family_filters() -> None:
        _family_state["filters"] = {}
        _render_family_tree()

    def _open_filter_menu(col_key: str) -> None:
        values = _distinct_values(col_key)
        current = _family_state["filters"].get(col_key)
        checked = set(current) if current is not None else set(values)
        checks: dict[str, object] = {}

        def toggle(v: str, val: bool):
            if val:
                checked.add(v)
            else:
                checked.discard(v)

        with ui.dialog() as dlg, ui.card().style("min-width:260px"):
            dlg.props("persistent")
            ui.label(f"Filter: {col_key}").style("font-weight:700; font-size:13px")
            box_search = ui.input(placeholder="Search values…").props("dense outlined clearable").classes("w-full q-mt-xs")
            list_area = ui.column().style("max-height:220px; overflow:auto; gap:2px")

            def render_list(filter_text: str = ""):
                list_area.clear()
                checks.clear()
                ft = filter_text.strip().lower()
                with list_area:
                    for v in values:
                        if ft and ft not in v.lower():
                            continue
                        checks[v] = ui.checkbox(v, value=(v in checked),
                                                 on_change=lambda e, v=v: toggle(v, e.value))

            box_search.on("update:model-value", lambda e: render_list(box_search.value or ""))
            render_list()

            def select_all():
                checked.update(values)
                render_list(box_search.value or "")

            def select_none():
                checked.clear()
                render_list(box_search.value or "")

            def apply_and_close():
                _family_state["filters"][col_key] = set(checked)
                dlg.close()
                _render_family_tree()

            def cancel():
                dlg.close()

            with ui.row().classes("q-mt-sm").style("gap:8px"):
                ui.button("Select All", on_click=select_all).props("flat dense")
                ui.button("Clear (Hide All)", on_click=select_none).props("flat dense")
                ui.button("Cancel", on_click=cancel).props("flat dense")
                ui.button("Apply", on_click=apply_and_close).classes("btn-orange").props(
                    "unelevated dense color=orange-8 text-color=black")
        dlg.open()

    def _col_header(title: str, col_key: str | None, flex: str = "1") -> None:
        is_active = col_key in _family_state["filters"] if col_key else False
        with ui.row().classes("items-center").style(
                f"flex:{flex}; gap:4px; font-size:11px; font-weight:700; color:#3d3f57; "
                f"text-transform:uppercase; letter-spacing:0.04em"):
            ui.label(title)
            if col_key:
                icon_color = "red-6" if is_active else "grey-7"
                ui.button(icon="filter_alt", on_click=lambda c=col_key: _open_filter_menu(c)).props(
                    f"flat dense round size=sm color={icon_color}")

    def _render_header_row() -> None:
        with ui.row().classes("items-center w-full").style(
                "padding:8px 10px; gap:0; background:#f7f7fd; border-bottom:2px solid #e4e6f1"):
            _col_header("Name", "name", flex="2")
            _col_header("Type", "node_type")
            _col_header("Default Value", "value")
            _col_header("Category", "category")
            _col_header("Comment", "comment")

    def _toggle_node(nid: str) -> None:
        if nid in _family_state["expanded"]:
            _family_state["expanded"].discard(nid)
        else:
            _family_state["expanded"].add(nid)
        _render_family_tree()

    def _all_family_ids(nodes: list) -> list:
        out = []
        for n in nodes:
            if n.get("children"):
                out.append(n["id"])
                out.extend(_all_family_ids(n["children"]))
        return out

    def _expand_all_family() -> None:
        _family_state["expanded"] = set(_all_family_ids(_family_state["full_tree"]))
        _render_family_tree()

    def _collapse_all_family() -> None:
        _family_state["expanded"] = set()
        _render_family_tree()

    _TYPE_ICONS = {
        "Family": "📁", "Article": "📄", "back": "↩️", "base": "🧱",
        "Calculation_Principle": "📊", "Color_Principle": "🎨",
        "Connection_Situation": "🔗", "Connector": "🔌", "Crown_Moulding": "🏛️",
        "Design_Parameter": "👁️", "Door": "🚪", "Drawer": "🗄️",
        "Light_Valance": "💡", "Material": "🧩", "Number": "🔢",
        "Part_Definition": "⚙️", "Profile_Name": "▭", "Pull": "🖐️",
        "Shelf_Partition": "🗂️", "Side_Panel": "🧱",
        "Stretchable_Purchase_Part": "📏", "Surface": "🟦", "Text": "🔤",
        "Work_Surface": "🪵",
    }

    def _icon_for(node_type: str) -> str:
        return _TYPE_ICONS.get(node_type, "❔")

    def _render_nodes(nodes: list, depth: int) -> None:
        for n in nodes:
            nid = n["id"]
            is_family = n["node_type"] == "Family"
            has_children = bool(n.get("children"))
            expanded = nid in _family_state["expanded"] or bool(_family_state["filters"])
            selected = (nid == _family_state["selected"])
            row_style = "padding:6px 10px; border-bottom:1px solid #f0f0f8; cursor:pointer"
            if selected:
                row_style += "; background:#eef0ff"
            with ui.row().classes("items-center w-full").style(row_style):
                with ui.row().classes("items-center").style(f"flex:2; gap:4px; padding-left:{depth*20}px"):
                    if has_children:
                        icon = "expand_more" if expanded else "chevron_right"
                        ui.button(icon=icon, on_click=lambda nid=nid: _toggle_node(nid)).props(
                            "flat dense round size=sm")
                    else:
                        ui.element("div").style("width:28px")
                    ui.label(_icon_for(n["node_type"]))
                    ui.label(n["label"]).style(
                        "font-family:monospace; font-size:13px" + (";font-weight:700" if is_family else ""))
                ui.label(n["node_type"]).style("flex:1; font-size:12px; color:#3d3f57")
                ui.label(n["value"]).style("flex:1; font-size:12px; color:#059669; font-family:monospace")
                ui.label(n["category"]).style("flex:1; font-size:12px; color:#3d3f57")
                ui.label(n["comment"]).style("flex:1; font-size:12px; color:#6b7086")
            if has_children and expanded:
                _render_nodes(n["children"], depth + 1)

    def _render_family_tree() -> None:
        family_container.clear()
        visible = _prune(_family_state["full_tree"])
        with family_container:
            _render_header_row()
            if not visible:
                ui.label("No data — run an extraction first, then click Refresh").style(
                    "padding:12px; color:#6b7086; font-size:13px")
            else:
                _render_nodes(visible, 0)

    def _expand_path_to(nid: str) -> None:
        def find_path(nodes, target, trail):
            for n in nodes:
                t2 = trail + [n["id"]]
                if n["id"] == target:
                    return t2
                r = find_path(n.get("children", []), target, t2)
                if r:
                    return r
            return None
        path = find_path(_family_state["full_tree"], nid, [])
        if path:
            for pid in path[:-1]:
                _family_state["expanded"].add(pid)

    def _select_match(idx: int) -> None:
        matches = _family_state["matches"]
        _family_state["match_idx"] = idx
        nid = matches[idx]
        _family_state["selected"] = nid
        _expand_path_to(nid)
        lbl_search_status.style("color:#059669").set_text(f"{idx + 1} / {len(matches)} found")
        _render_family_tree()

    def _go_to_match(delta: int) -> None:
        matches = _family_state["matches"]
        if not matches:
            return
        idx = (_family_state["match_idx"] + delta) % len(matches)
        _select_match(idx)

    def _do_search(text: str) -> None:
        text = (text or "").strip().lower()
        _family_state["matches"] = []
        _family_state["match_idx"] = -1
        if not text:
            _family_state["selected"] = None
            lbl_search_status.set_text("")
            _render_family_tree()
            return
        for n in _flatten_all(_family_state["full_tree"]):
            if text in n["label"].lower():
                _family_state["matches"].append(n["id"])
        if not _family_state["matches"]:
            _family_state["selected"] = None
            lbl_search_status.style("color:#e11d48").set_text("No match found")
            _render_family_tree()
            return
        _select_match(0)

    async def _rebuild_family_tree() -> None:
        from nicegui import run as nicegui_run
        from core.family_tree import build_family_tree
        var_names = sorted({r["variable_name"] for r in _all_rows})
        tree = await nicegui_run.io_bound(build_family_tree, var_names)
        _family_state["full_tree"] = tree
        _family_state["expanded"] = set()
        _family_state["filters"] = {}
        _family_state["selected"] = None
        _family_state["matches"] = []
        _family_state["match_idx"] = -1
        var_count = sum(1 for n in _flatten_all(tree) if n.get("node_type") != "Family")
        lbl_family_count.set_text(f"{var_count} variables")
        _render_family_tree()

    async def on_family_refresh() -> None:
        if _last_run:
            await on_rerun()
        else:
            await _rebuild_family_tree()

    _render_results_header()


def launch() -> None:
    port = _find_free_port(8080)
    ui.run(title="imos iX Variable Extractor", port=port, reload=False, favicon="💠", show=True)


if __name__ in {"__main__", "__mp_main__"}:
    launch()