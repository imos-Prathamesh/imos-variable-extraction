# Source : ui/main_window.py
# Analogy: The dashboard — Settings / Run / Results / Family Structure.
# Flow list comes from core/flow_registry.py (no hardcoding here).
#
# NOTE: NiceGUI 3.x requires all UI to be built inside an @ui.page() handler.
from __future__ import annotations

import csv
import io
import json
import os
import re
import socket
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

CONFIG_FILE = ROOT / "config.json"
RUN_STATE_FILE = ROOT / "run_state.json"

APP_VERSION = "v1.1"
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

# (key, label, width %, sortable, filterable)
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

_PILLS = [
    ("#e0e7ff", "#3730a3"), ("#dcfce7", "#166534"), ("#fef3c7", "#92400e"),
    ("#fce7f3", "#9d174d"), ("#cffafe", "#155e75"), ("#ede9fe", "#5b21b6"),
    ("#ffedd5", "#9a3412"), ("#e2e8f0", "#334155"),
]

def _pill_style(text) -> str:
    s = str(text or "")
    if not s or s == "—":
        return "background:#e2e8f0;color:#475569"
    bg, fg = _PILLS[sum(ord(c) for c in s) % len(_PILLS)]
    return f"background:{bg};color:{fg}"

def _load_cfg() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {"server": "", "database": "", "user": "", "password": ""}

def _load_run_state() -> dict:
    default = {
        "mode": "single", "article": "", "articles": [],
        "wf_mode": "single", "workflow": ALL_FLOWS_LABEL, "workflows": [],
    }
    if RUN_STATE_FILE.exists():
        try:
            saved = json.loads(RUN_STATE_FILE.read_text())
            default.update(saved)
        except Exception:
            pass
    return default

def _save_run_state(state: dict) -> None:
    try:
        RUN_STATE_FILE.write_text(json.dumps(state, indent=2))
    except Exception:
        pass

def _clear_run_state() -> None:
    try:
        if RUN_STATE_FILE.exists():
            RUN_STATE_FILE.unlink()
    except Exception:
        pass

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

def _try_conn() -> bool:
    try:
        from core.db import get_connection
        get_connection()
        return True
    except Exception:
        return False

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
    rows = []
    for i, o in enumerate(occurrences):
        var_type = typ_map.get(o.variable_name, "—")
        rows.append({
            "num":           i + 1,
            "article":       o.article,
            "var_type":      var_type,
            "variable_name": o.variable_name,
            "value":         o.value,
            "origin":        _parse_origin(o.path, o.variable_name),
            "source_table":  o.source_table,
            "source_column": o.source_column,
            "resolved_via":  o.resolved_via,
            "path":          o.path_str(),
            "var_type_sty":  _pill_style(var_type),
            "table_sty":     _pill_style(o.source_table),
            "via_sty":       _pill_style(o.resolved_via),
        })
    return rows

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
        --imos-surface-2:    #f7f7fd;
        --imos-border:       #e4e6f1;
        --imos-border-soft:  #f0f0f8;
        --imos-text:         #1e1b3a;
        --imos-text-2:       #3d3f57;
        --imos-muted:        #6b7086;
        --imos-faint:        #a0a3bd;
        --imos-input-bg:     #f7f7fc;
        --imos-hover:        #eef0ff;
        --imos-row-alt:      #fafaff;
        --imos-badge-bg:     #eef0ff;
        --imos-badge-border: #cfd3fb;
        --imos-link:         #4f46e5;
        --imos-guide:        #d3d6ee;
        --imos-hdr-a:        #ffffff;
        --imos-hdr-b:        #f7f7ff;
        --imos-th-a:         #f7f7fd;
        --imos-th-b:         #f0f0fa;
        --imos-shadow:       rgba(79,70,229,0.08);
    }
    .body--dark {
        --imos-primary-dark: #c7d2fe;
        --imos-success:      #34d399;
        --imos-bg:           #12121c;
        --imos-surface:      #1b1b2b;
        --imos-surface-2:    #222236;
        --imos-border:       #2f3047;
        --imos-border-soft:  #26273b;
        --imos-text:         #ecebff;
        --imos-text-2:       #c7c8e0;
        --imos-muted:        #9a9cb8;
        --imos-faint:        #6f7192;
        --imos-input-bg:     #232338;
        --imos-hover:        #2a2b4a;
        --imos-row-alt:      #1f1f31;
        --imos-badge-bg:     #262848;
        --imos-badge-border: #3b3e72;
        --imos-link:         #a5b4fc;
        --imos-guide:        #3a3b58;
        --imos-hdr-a:        #1b1b2b;
        --imos-hdr-b:        #202036;
        --imos-th-a:         #222236;
        --imos-th-b:         #1f1f33;
        --imos-shadow:       rgba(0,0,0,0.35);
    }
    body { background:var(--imos-bg) !important; color:var(--imos-text); }

    @keyframes imosFade { from { opacity:0; transform:translateY(8px); } to { opacity:1; transform:translateY(0); } }
    @keyframes treeIn   { from { opacity:0; transform:translateX(-8px); } to { opacity:1; transform:none; } }
    @keyframes imosShimmer { from { background-position:200% 0; } to { background-position:-200% 0; } }
    .q-tab-panel { animation:imosFade .35s ease; }
    .tree-anim   { animation:treeIn .22s ease; }

    .imos-header {
        background:linear-gradient(90deg, var(--imos-hdr-a), var(--imos-hdr-b)) !important;
        border-bottom:1px solid var(--imos-border) !important;
        box-shadow:0 2px 10px var(--imos-shadow) !important;
        padding:0 !important;
        color:var(--imos-text) !important;
    }
    .imos-header::after {
        content:"";
        position:absolute; left:0; right:0; bottom:-1px; height:3px;
        background:linear-gradient(90deg, #4f46e5, #f59e0b, #059669);
    }
    .imos-footer {
        background:var(--imos-surface) !important;
        border-top:1px solid var(--imos-border) !important;
        color:var(--imos-muted) !important;
        padding:6px 24px !important;
    }
    .q-tabs { background:var(--imos-surface) !important; border-bottom:2px solid var(--imos-border) !important; }
    .q-tab { color:var(--imos-muted) !important; font-weight:600 !important; font-size:13px !important; letter-spacing:0.04em !important; }
    .q-tab--active { color:var(--imos-primary) !important; }
    .q-tab__indicator { background:linear-gradient(90deg, var(--imos-primary), var(--imos-accent)) !important; height:3px !important; }
    .q-tab-panels { background:var(--imos-bg) !important; }
    .imos-card {
        background:var(--imos-surface) !important;
        border-radius:14px !important;
        border:1px solid var(--imos-border) !important;
        box-shadow:0 4px 16px var(--imos-shadow) !important;
    }
    .q-field__control { background:var(--imos-input-bg) !important; border-radius:9px !important; }
    .q-field__native, .q-field__input { color:var(--imos-text) !important; font-size:14px !important; }
    .q-field--outlined .q-field__control:before { border-color:var(--imos-border) !important; }
    .q-field--outlined .q-field__control:hover:before { border-color:var(--imos-primary) !important; }
    .q-field--outlined.q-field--focused .q-field__control:before { border-color:var(--imos-primary) !important; border-width:2px !important; }
    .q-field__label { color:var(--imos-muted) !important; font-size:13px !important; }
    .q-field__append .q-icon { color:var(--imos-faint) !important; }
    .q-checkbox__inner { color:var(--imos-primary) !important; }
    .q-checkbox__label { color:var(--imos-text-2) !important; font-size:13px !important; font-weight:500 !important; }
    .btn-primary .q-btn__content .block, .btn-orange .q-btn__content .block, .btn-danger .q-btn__content .block {
        color:#000000 !important;
        font-weight:800 !important;
    }
    .imos-scroll {
        max-height:62vh; overflow:auto;
        border:1px solid var(--imos-border); border-radius:12px;
        background:var(--imos-surface);
    }
    .imos-table { background:var(--imos-surface) !important; color:var(--imos-text) !important; border:none !important; border-radius:0 !important; box-shadow:none !important; }
    .imos-table .q-table { table-layout:fixed !important; width:100% !important; }
    .imos-table .q-table tbody tr td {
        color:var(--imos-text) !important; font-size:13px !important; padding:8px 12px !important;
        overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
        border-bottom:1px solid var(--imos-border-soft) !important;
    }
    .imos-table .q-table tbody tr:nth-child(even) td { background:var(--imos-row-alt); }
    .imos-table .q-table tbody tr:hover td { background:var(--imos-hover) !important; }
    .imos-table .q-table__bottom { color:var(--imos-text-2) !important; border-top:1px solid var(--imos-border) !important; }
    .imos-table .q-table__bottom .q-field__native,
    .imos-table .q-table__bottom .q-field__control { color:var(--imos-text-2) !important; }
    .imos-pill {
        display:inline-block; padding:2px 10px; border-radius:12px;
        font-size:11px; font-weight:700; line-height:1.5;
        max-width:100%; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;
    }
    .copy-cell .copy-ico { opacity:0; transition:opacity .15s; margin-left:6px; color:var(--imos-faint); }
    .copy-cell:hover .copy-ico { opacity:1; }
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
    .btn-run { padding:8px 40px !important; font-size:16px !important; letter-spacing:0.1em !important; }
    .btn-blue {
        background:#2563eb !important;
        color:#000000 !important;
        border-radius:9px !important;
        font-weight:800 !important;
        border:1px solid #1e3a8a !important;
        box-shadow:0 2px 8px rgba(37,99,235,0.4) !important;
    }
    .btn-blue .q-btn__content { color:#000000 !important; font-weight:800 !important; }
    .filter-input .q-field__control { background:var(--imos-surface) !important; border-radius:7px !important; }
    .filter-input .q-field__native { font-size:12px !important; color:var(--imos-text-2) !important; }
    .env-badge {
        background:#fff3cf; color:#8a5a00;
        font-size:10px; font-weight:700; letter-spacing:0.08em;
        padding:3px 10px; border-radius:20px; border:1px solid #f7d374;
    }
    .imos-header-badge {
        font-size:12px; font-weight:700; color:var(--imos-primary-dark);
        background:var(--imos-badge-bg); padding:5px 14px; border-radius:20px;
        border:1px solid var(--imos-badge-border);
    }
    .imos-count-badge {
        font-size:13px; font-weight:700; color:var(--imos-primary-dark);
        background:var(--imos-badge-bg); padding:4px 12px; border-radius:20px;
        border:1px solid var(--imos-badge-border);
    }
    .imos-chip { background:var(--imos-badge-bg) !important; color:var(--imos-primary-dark) !important; border:1px solid var(--imos-badge-border) !important; font-weight:600 !important; }
    .imos-stat {
        display:flex; align-items:center; gap:12px; padding:12px 18px;
        background:var(--imos-surface); border:1px solid var(--imos-border);
        border-radius:12px; flex:1; min-width:180px;
        box-shadow:0 2px 10px var(--imos-shadow);
    }
    .imos-stat-title { font-size:11px; font-weight:700; letter-spacing:0.08em; text-transform:uppercase; color:var(--imos-muted); }
    .imos-stat-value { font-size:22px; font-weight:800; color:var(--imos-text); line-height:1.1; }
    .imos-sec { font-size:10px; font-weight:700; letter-spacing:0.12em; color:var(--imos-primary); }
    .imos-status {
        background:var(--imos-surface-2); border:1px solid var(--imos-border);
        border-radius:10px; padding:8px 14px; gap:10px;
    }
    .imos-skel {
        height:30px; width:100%; border-radius:8px;
        background:linear-gradient(90deg, var(--imos-surface-2) 25%, var(--imos-border) 50%, var(--imos-surface-2) 75%);
        background-size:200% 100%; animation:imosShimmer 1.3s infinite linear;
    }
    .wf-select .q-chip { font-weight:700 !important; }
    .wf-select .q-chip:nth-child(3n+1) { background:#e0e7ff !important; color:#3730a3 !important; }
    .wf-select .q-chip:nth-child(3n+2) { background:#dcfce7 !important; color:#166534 !important; }
    .wf-select .q-chip:nth-child(3n+3) { background:#fef3c7 !important; color:#92400e !important; }
"""

ui.add_css(_CSS, shared=True)


def _stat_card(icon: str, title: str, accent: str):
    with ui.element("div").classes("imos-stat").style(f"border-left:4px solid {accent}"):
        ui.label(icon).style("font-size:24px")
        with ui.column().style("gap:0"):
            ui.label(title).classes("imos-stat-title")
            value = ui.label("0").classes("imos-stat-value")
    return value


def _skeleton_rows(n: int) -> None:
    for _ in range(n):
        ui.element("div").classes("imos-skel")


def _download_bytes(data: bytes, filename: str, media: str) -> None:
    dl = ui.download
    if hasattr(dl, "content"):
        dl.content(data, filename, media)
    else:
        dl(data, filename)


@ui.page("/")
def index_page() -> None:
    ui.query("body").style("font-family:'Segoe UI',sans-serif")
    dark = ui.dark_mode(False)

    _all_rows: list[dict] = []
    _last_run: dict = {}
    _visible: dict = {"rows": []}
    _run_meta: dict = {"flows": 0}
    _filters: dict = {
        "article": "", "var_type": "", "variable_name": "",
        "value": "", "source_table": "", "source_column": "",
        "resolved_via": "", "search": "", "unique": False,
    }
    _results_filters: dict = {}
    _results_sort: dict = {"col": None, "desc": False}
    _family_state: dict = {
        "full_tree": [], "expanded": set(), "filters": {},
        "matches": [], "match_idx": -1, "selected": None, "anim_parent": None,
    }

    # ── header ───────────────────────────────────────────────────────────
    with ui.header().classes("imos-header"):
        with ui.row().classes("items-center justify-between w-full q-px-xl").style("height:62px"):
            with ui.row().classes("items-center").style("gap:14px"):
                ui.label("💠").style("font-size:26px")
                with ui.column().style("gap:1px"):
                    ui.label("imos iX Variable Extractor").style(
                        "font-size:18px; font-weight:700; color:var(--imos-text); letter-spacing:0.01em")
                    ui.label("Developer — Prathamesh Patil").style(
                        "font-size:11px; color:var(--imos-muted); letter-spacing:0.04em")
            with ui.row().classes("items-center").style("gap:12px"):
                _hdr_cfg = _load_cfg()
                lbl_hdr_conn = ui.label(f"🖥 {_hdr_cfg.get('server','—')}  ›  {_hdr_cfg.get('database','—')}").classes(
                    "imos-header-badge")
                ui.html('<span class="env-badge">⚗ TEST ENVIRONMENT</span>')

                def toggle_theme() -> None:
                    dark.toggle()
                    btn_theme.props(f"icon={'light_mode' if dark.value else 'dark_mode'}")

                btn_theme = ui.button(icon="dark_mode", on_click=toggle_theme).props(
                    "flat round dense").style("color:var(--imos-primary)").tooltip("Toggle dark / light theme")

    # ── footer ───────────────────────────────────────────────────────────
    with ui.footer().classes("imos-footer"):
        with ui.row().classes("items-center justify-between w-full"):
            ui.label(f"imos iX Variable Extractor  {APP_VERSION}").style(
                "font-size:11px; color:var(--imos-muted); letter-spacing:0.04em")
            with ui.row().classes("items-center").style("gap:8px"):
                dot_db = ui.element("div").style(
                    "width:9px; height:9px; border-radius:50%; background:#9ca3af")
                lbl_db = ui.label("DB unchecked").style("font-size:11px; color:var(--imos-muted)")

    def _set_db_status(ok) -> None:
        if ok is True:
            dot_db.style("background:#22c55e; box-shadow:0 0 6px #22c55e")
            lbl_db.set_text("DB connected")
        elif ok is False:
            dot_db.style("background:#ef4444; box-shadow:0 0 6px #ef4444")
            lbl_db.set_text("DB not connected")
        else:
            dot_db.style("background:#9ca3af; box-shadow:none")
            lbl_db.set_text("DB unchecked")

    async def _check_db() -> None:
        from nicegui import run as nicegui_run
        ok = await nicegui_run.io_bound(_try_conn)
        _set_db_status(ok)

    ui.timer(0.5, _check_db, once=True)

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
                        "font-size:15px; font-weight:700; color:var(--imos-text)")

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

                lbl_conn = ui.label("").style("font-size:12px; color:var(--imos-muted); min-height:18px")

                _servers_scanned = {"done": False}
                _dbs_loaded_for = {"key": None}

                def on_discover_servers():
                    if _servers_scanned["done"]:
                        return
                    _servers_scanned["done"] = True
                    lbl_conn.style("color:var(--imos-muted)").set_text("Scanning network (this can take a few seconds)…")
                    try:
                        from core.db import discover_sql_servers
                        found = discover_sql_servers()
                        if found:
                            sel_server.set_options(found)
                            lbl_conn.style("color:var(--imos-success)").set_text(f"✓ Found {len(found)} server(s)")
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
                    lbl_conn.style("color:var(--imos-muted)").set_text("Loading database list…")
                    try:
                        from core.db import list_databases
                        names = list_databases(sel_server.value, inp_user.value, inp_pass.value)
                        sel_db.set_options(names)
                        _dbs_loaded_for["key"] = key
                        lbl_conn.style("color:var(--imos-success)").set_text(f"✓ {len(names)} database(s) found")
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
                    lbl_conn.style("color:var(--imos-success)").set_text("✓ Credentials saved")
                    lbl_hdr_conn.set_text(f"🖥 {new_cfg.get('server','—')}  ›  {new_cfg.get('database','—')}")
                    ui.notify("Credentials saved", type="positive", position="top-right")
                    _set_db_status(None)

                def on_test():
                    _reset_db_conn()
                    lbl_conn.style("color:var(--imos-muted)").set_text("Connecting…")
                    try:
                        from core.db import get_connection
                        get_connection()
                        lbl_conn.style("color:var(--imos-success)").set_text("✓ Connected successfully")
                        _set_db_status(True)
                        ui.notify("Connected successfully", type="positive", position="top-right")
                    except Exception as e:
                        lbl_conn.style("color:#e11d48").set_text(f"✗ {e}")
                        _set_db_status(False)
                        ui.notify("Connection failed", type="negative", position="top-right")

                with ui.row().classes("q-mt-md").style("gap:8px"):
                    ui.button("Save", on_click=on_save).classes("btn-primary").props(
                        "unelevated color=orange-8 text-color=black")
                    ui.button("Test Connection", on_click=on_test).classes("btn-primary").props(
                        "unelevated color=orange-8 text-color=black")

        # ── Run ──────────────────────────────────────────────────────────
        with ui.tab_panel(t_run):
            with ui.element("div").classes("imos-card q-pa-lg").style("max-width:920px"):
                with ui.row().classes("items-center q-mb-md").style("gap:10px"):
                    ui.element("div").style(
                        "width:4px; height:20px; background:linear-gradient(180deg,#4f46e5,#f59e0b); border-radius:2px")
                    ui.label("Extract Variables").style(
                        "font-size:15px; font-weight:700; color:var(--imos-text)")

                with ui.row().classes("w-full").style("gap:28px; flex-wrap:wrap; align-items:flex-start"):
                    with ui.column().style("flex:1; min-width:300px; gap:4px"):
                        ui.label("ARTICLES").classes("imos-sec")
                        sel_article  = ui.select([], label="Article", with_input=True).classes("w-full")
                        sel_articles_multi = ui.select([], label="Articles", multiple=True,
                                                       with_input=True).classes("w-full").props("use-chips")
                        sel_articles_multi.set_visibility(False)
                        with ui.row().style("gap:12px"):
                            chk_multi = ui.checkbox("Multiple Articles")
                            chk_all   = ui.checkbox("All Articles")

                    with ui.column().style("flex:1; min-width:300px; gap:4px"):
                        ui.label("WORKFLOWS").classes("imos-sec")
                        sel_workflow = ui.select(_workflow_options(), label="Workflow",
                                                 value=ALL_FLOWS_LABEL).classes("w-full")
                        sel_workflow_multi = ui.select(_workflow_options(), label="Workflows", multiple=True,
                                                       with_input=True).classes("w-full wf-select").props("use-chips")
                        sel_workflow_multi.set_visibility(False)
                        chk_multi_wf = ui.checkbox("Multiple Workflows")

                lbl_run = ui.label("").style("font-size:12px; color:var(--imos-muted); min-height:18px; margin-top:8px")

                _articles_loaded = {"done": False}
                _run_persist_state = _load_run_state()

                def _load_articles():
                    if _articles_loaded["done"]:
                        return
                    _articles_loaded["done"] = True
                    lbl_run.style("color:var(--imos-muted)").set_text("Loading articles…")
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
                        lbl_run.style("color:var(--imos-success)").set_text(f"✓ {len(names)} articles loaded")
                        _restore_run_selection()
                    except Exception as e:
                        _articles_loaded["done"] = False
                        lbl_run.style("color:#e11d48").set_text(f"✗ {e}")

                ui.timer(0.1, _load_articles, once=True)

                def _restore_run_selection() -> None:
                    st = _run_persist_state
                    try:
                        if st.get("mode") == "all":
                            chk_all.set_value(True)
                        elif st.get("mode") == "multi":
                            chk_multi.set_value(True)
                            if st.get("articles"):
                                sel_articles_multi.set_value(st["articles"])
                        elif st.get("article") and st["article"] in (sel_article.options or []):
                            sel_article.set_value(st["article"])

                        if st.get("wf_mode") == "multi":
                            chk_multi_wf.set_value(True)
                            if st.get("workflows"):
                                sel_workflow_multi.set_value(st["workflows"])
                        elif st.get("workflow"):
                            sel_workflow.set_value(st["workflow"])
                        _refresh_article_visibility()
                        _refresh_workflow_visibility()
                    except Exception:
                        pass

                def _persist_current_selection() -> None:
                    state = {
                        "mode": "all" if chk_all.value else ("multi" if chk_multi.value else "single"),
                        "article": sel_article.value or "",
                        "articles": sel_articles_multi.value or [],
                        "wf_mode": "multi" if chk_multi_wf.value else "single",
                        "workflow": sel_workflow.value or ALL_FLOWS_LABEL,
                        "workflows": sel_workflow_multi.value or [],
                    }
                    _save_run_state(state)

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

                # live status strip
                with ui.row().classes("imos-status items-center w-full no-wrap q-mt-md"):
                    spin_run = ui.spinner(size="sm", color="orange")
                    spin_run.set_visibility(False)
                    lbl_status = ui.label("Ready — select articles and workflows, then press RUN").style(
                        "font-size:13px; font-weight:600; color:var(--imos-text-2)")
                    ui.space()
                    lbl_status_detail = ui.label("").style(
                        "font-size:12px; color:var(--imos-muted); font-family:monospace")

                def _set_status(text: str, detail: str = "", spin: bool = False) -> None:
                    lbl_status.set_text(text)
                    lbl_status_detail.set_text(detail)
                    spin_run.set_visibility(spin)

                def _flow_label(workflows: list) -> str:
                    if ALL_FLOWS_LABEL in workflows:
                        return "All Flows"
                    return ", ".join(workflows)

                def _art_label(art, all_arts, arts) -> str:
                    if all_arts:
                        return "All articles"
                    if arts:
                        return ", ".join(arts) if len(arts) <= 3 else f"{len(arts)} articles"
                    return art or "—"

                async def _execute_run(workflows, art, all_arts, arts, switch_tab: bool):
                    nonlocal _all_rows, _last_run
                    from nicegui import run as nicegui_run
                    from core.flow_registry import flow_names

                    flow_lbl = _flow_label(workflows)
                    art_lbl  = _art_label(art, all_arts, arts)

                    lbl_run.style("color:var(--imos-link)").set_text("Running extraction…")
                    _set_status("Running…", f"Flows: {flow_lbl}  ·  Articles: {art_lbl}", spin=True)
                    btn_run.props(add="loading")
                    btn_run.disable()
                    _set_loading(True)
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
                        lbl_run.style("color:var(--imos-success)").set_text(f"✓ {len(_all_rows)} occurrences found")
                        _last_run = {"workflows": workflows, "art": art, "all_arts": all_arts, "arts": arts}
                        _run_meta["flows"] = (len(flow_names()) if ALL_FLOWS_LABEL in workflows
                                              else len(set(workflows)))
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
                        _set_status(f"Completed — {len(_all_rows)} occurrences",
                                    f"Flows: {flow_lbl}  ·  Articles: {art_lbl}")
                        _set_db_status(True)
                        ui.notify(f"{len(_all_rows)} occurrences found", type="positive", position="top-right")
                        if switch_tab:
                            tabs.set_value(t_results)
                    except Exception as e:
                        lbl_run.style("color:#e11d48").set_text(f"✗ {e}")
                        _set_status("Failed", str(e)[:120])
                        ui.notify(f"Extraction failed: {e}", type="negative", position="top-right")
                    finally:
                        anim_task.cancel()
                        prog_run.set_visibility(False)
                        spin_run.set_visibility(False)
                        btn_run.props(remove="loading")
                        btn_run.enable()
                        _set_loading(False)

                def on_reset():
                    chk_all.set_value(False)
                    chk_multi.set_value(False)
                    chk_multi_wf.set_value(False)
                    sel_article.set_value(None)
                    sel_articles_multi.set_value([])
                    sel_workflow.set_value(ALL_FLOWS_LABEL)
                    sel_workflow_multi.set_value([])
                    _refresh_article_visibility()
                    _refresh_workflow_visibility()
                    _clear_run_state()
                    lbl_run.style("color:var(--imos-muted)").set_text("")
                    _set_status("Ready — select articles and workflows, then press RUN")
                    ui.notify("Reset complete", type="info", position="top-right")

                async def on_run():
                    art  = None
                    arts = None
                    if chk_all.value:
                        pass
                    elif chk_multi.value:
                        arts = sel_articles_multi.value or []
                        if not arts:
                            lbl_run.style("color:#b45309").set_text("⚠ Select at least one article")
                            ui.notify("Select at least one article", type="warning", position="top-right")
                            return
                    else:
                        art = sel_article.value
                        if not art:
                            lbl_run.style("color:#b45309").set_text("⚠ Select an article or check All Articles")
                            ui.notify("Select an article or check All Articles", type="warning", position="top-right")
                            return

                    if chk_multi_wf.value:
                        workflows = sel_workflow_multi.value or []
                        if not workflows:
                            lbl_run.style("color:#b45309").set_text("⚠ Select at least one workflow")
                            ui.notify("Select at least one workflow", type="warning", position="top-right")
                            return
                    else:
                        workflows = [sel_workflow.value]

                    _persist_current_selection()
                    await _execute_run(workflows, art, chk_all.value, arts, switch_tab=True)

                async def on_rerun():
                    if not _last_run:
                        return
                    await _execute_run(_last_run["workflows"], _last_run["art"],
                                        _last_run["all_arts"], _last_run["arts"], switch_tab=False)

                with ui.row().classes("q-mt-md items-center").style("gap:12px"):
                    btn_run = ui.button("RUN", icon="play_arrow", on_click=on_run).classes(
                        "btn-orange btn-run").props("unelevated size=lg color=orange-8 text-color=black")
                    ui.button("RESET", icon="restart_alt", on_click=on_reset).classes(
                        "btn-danger btn-run").props("unelevated size=lg color=orange-8 text-color=black")

        # ── Results ──────────────────────────────────────────────────────
        with ui.tab_panel(t_results):

            # summary cards
            with ui.row().classes("w-full").style("gap:14px; flex-wrap:wrap; margin-bottom:12px"):
                card_occ   = _stat_card("📊", "Occurrences",      "#4f46e5")
                card_uniq  = _stat_card("🔣", "Unique Variables", "#059669")
                card_flows = _stat_card("🔀", "Flows Used",       "#f59e0b")
                card_arts  = _stat_card("📄", "Articles",         "#e11d48")

            # toolbar
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
                ui.button("CSV", icon="download", on_click=lambda: _export_rows("csv")).classes(
                    "btn-blue").props("unelevated dense")
                ui.button("Excel", icon="download", on_click=lambda: _export_rows("xlsx")).classes(
                    "btn-blue").props("unelevated dense")
                lbl_flow_indicator = ui.label("Flow: —").classes("imos-header-badge")

            # text filter row
            with ui.element("div").classes("imos-card q-pa-sm q-mb-sm"):
                with ui.row().classes("items-center").style("gap:6px; flex-wrap:wrap"):
                    ui.label("FILTER").style(
                        "font-size:10px; font-weight:700; color:var(--imos-primary); "
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

            _filter_widgets = {
                "article": f_article, "var_type": f_vartype, "variable_name": f_varname,
                "value": f_value, "source_table": f_table, "source_column": f_col,
                "resolved_via": f_via, "search": inp_search,
            }

            # active filter chips
            chips_row = ui.row().classes("w-full items-center").style("gap:6px; margin-bottom:8px")
            chips_row.set_visibility(False)

            # skeleton while loading
            skel_results = ui.column().classes("w-full").style("gap:8px")
            with skel_results:
                _skeleton_rows(9)
            skel_results.set_visibility(False)

            # sticky-header scrollable table
            with ui.element("div").classes("imos-scroll w-full") as tbl_wrap:
                results_header = ui.row().classes("w-full no-wrap").style(
                    "gap:0; position:sticky; top:0; z-index:5; box-sizing:border-box; "
                    "background:linear-gradient(180deg,var(--imos-th-a),var(--imos-th-b)); "
                    "border-bottom:2px solid var(--imos-border)")

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
                ).classes("imos-table w-full").props("dense flat hide-header")

                tbl.add_slot("body", """
                    <q-tr :props="props">
                        <q-td v-for="col in props.cols" :key="col.name" :props="props">
                            <template v-if="col.name === 'expand'">
                                <q-btn flat dense round size="sm"
                                       :icon="props.expand ? 'expand_less' : 'expand_more'"
                                       @click="props.expand = !props.expand" />
                            </template>
                            <template v-else-if="col.name === 'variable_name'">
                                <span class="copy-cell"
                                      style="cursor:pointer; font-family:monospace; font-weight:600; color:var(--imos-link); font-size:13px"
                                      title="Click to copy"
                                      @click="() => { navigator.clipboard.writeText(col.value);
                                          $q.notify({ message: '$ ' + col.value + ' copied', timeout: 1200,
                                                      color: 'indigo-8', position: 'top-right', icon: 'content_copy' }); }">
                                    <span style="opacity:0.4; margin-right:2px">$</span>{{ col.value }}<q-icon name="content_copy" class="copy-ico" size="14px" />
                                </span>
                            </template>
                            <template v-else-if="col.name === 'value'">
                                <span class="copy-cell"
                                      style="cursor:pointer; color:var(--imos-success); font-family:monospace; font-size:13px"
                                      title="Click to copy"
                                      @click="() => { navigator.clipboard.writeText(col.value);
                                          $q.notify({ message: 'Copied', timeout: 800, color: 'teal-8',
                                                      position: 'top-right', icon: 'content_copy' }); }">
                                    {{ col.value }}<q-icon name="content_copy" class="copy-ico" size="14px" />
                                </span>
                            </template>
                            <template v-else-if="col.name === 'var_type'">
                                <span v-if="col.value" class="imos-pill" :style="props.row.var_type_sty">{{ col.value }}</span>
                            </template>
                            <template v-else-if="col.name === 'source_table'">
                                <span v-if="col.value" class="imos-pill" :style="props.row.table_sty">{{ col.value }}</span>
                            </template>
                            <template v-else-if="col.name === 'resolved_via'">
                                <span v-if="col.value" class="imos-pill" :style="props.row.via_sty">{{ col.value }}</span>
                            </template>
                            <template v-else>
                                {{ col.value }}
                            </template>
                        </q-td>
                    </q-tr>
                    <q-tr v-if="props.expand" :props="props">
                        <q-td colspan="100%" style="background:var(--imos-surface-2); padding:10px 16px; white-space:normal">
                            <div style="font-size:10px; font-weight:700; color:var(--imos-primary); letter-spacing:0.08em; margin-bottom:4px">
                                RESOLUTION PATH
                            </div>
                            <div style="font-family:monospace; font-size:12px; color:var(--imos-text-2); white-space:pre-wrap; word-break:break-word">
                                {{ props.row.path }}
                            </div>
                        </q-td>
                    </q-tr>
                """)

            ui.label("💠 Click any Variable or Value cell to copy to clipboard").style(
                "font-size:11px; color:var(--imos-faint); margin-top:6px")

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

            family_skel = ui.column().classes("w-full").style("gap:8px")
            with family_skel:
                _skeleton_rows(9)
            family_skel.set_visibility(False)

            family_container = ui.column().classes("imos-card w-full").style("gap:0; overflow:auto")

    # ── loading helper ─────────────────────────────────────────────────────

    def _set_loading(flag: bool) -> None:
        skel_results.set_visibility(flag)
        tbl_wrap.set_visibility(not flag)
        family_skel.set_visibility(flag)
        family_container.set_visibility(not flag)

    # ── export ─────────────────────────────────────────────────────────────

    def _export_rows(kind: str) -> None:
        rows = _visible["rows"]
        if not rows:
            ui.notify("Nothing to export", type="warning", position="top-right")
            return
        headers = ["Article", "Var. Type", "Variable", "Value", "Origin",
                   "Table", "Column", "Via", "Path"]
        keys = ["article", "var_type", "variable_name", "value", "origin",
                "source_table", "source_column", "resolved_via", "path"]
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if kind == "csv":
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(headers)
            for r in rows:
                w.writerow(["" if r.get(k) is None else r.get(k) for k in keys])
            _download_bytes(("\ufeff" + buf.getvalue()).encode("utf-8"),
                            f"imos_variables_{stamp}.csv", "text/csv")
            ui.notify(f"Exported {len(rows)} rows to CSV", type="positive", position="top-right")
            return
        try:
            from openpyxl import Workbook
        except ImportError:
            ui.notify("Excel export needs openpyxl — run: pip install openpyxl",
                      type="negative", position="top-right")
            return
        wb = Workbook()
        ws = wb.active
        ws.title = "Variables"
        ws.append(headers)
        for r in rows:
            ws.append([str("" if r.get(k) is None else r.get(k)) for k in keys])
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.data_type = "s"
        bio = io.BytesIO()
        wb.save(bio)
        _download_bytes(bio.getvalue(), f"imos_variables_{stamp}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        ui.notify(f"Exported {len(rows)} rows to Excel", type="positive", position="top-right")

    # ── results filter / sort logic ────────────────────────────────────────

    def _set_filter(key: str, val) -> None:
        if isinstance(val, str):
            cleaned = val.strip().lower()
            if key == "search" and cleaned.startswith(("$", "#")):
                cleaned = cleaned[1:]
            _filters[key] = cleaned
        else:
            _filters[key] = bool(val)
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

        _visible["rows"] = rows
        tbl.rows = rows
        tbl.update()
        lbl_count.set_text(f"{len(rows)} / {len(_all_rows)} variables")
        card_occ.set_text(f"{len(rows):,}")
        card_uniq.set_text(f"{len({r['variable_name'] for r in rows}):,}")
        card_arts.set_text(f"{len({r['article'] for r in rows}):,}")
        card_flows.set_text(str(_run_meta["flows"]))
        _render_chips()

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

    def _col_label(key: str) -> str:
        return next((c[1] for c in _RES_COLS if c[0] == key), key)

    def _make_remove(kind: str, key):
        def _h(e) -> None:
            if e.value:
                return
            if kind == "text":
                _filter_widgets[key].set_value("")
            elif kind == "unique":
                chk_unique.set_value(False)
            else:
                _results_filters.pop(key, None)
                _render_results_header()
                _apply_filters()
        return _h

    def _render_chips() -> None:
        chips_row.clear()
        items: list[tuple] = []
        labels = {"article": "Article", "var_type": "Var Type", "variable_name": "Variable",
                  "value": "Value", "source_table": "Table", "source_column": "Column",
                  "resolved_via": "Via", "search": "Search"}
        for k, lab in labels.items():
            v = _filters.get(k)
            if v:
                items.append((f"{lab}: {v}", "text", k))
        if _filters["unique"]:
            items.append(("Unique only", "unique", None))
        for c in sorted(_active_filter_cols()):
            items.append((f"{_col_label(c)}: {len(_results_filters[c])} selected", "col", c))
        chips_row.set_visibility(bool(items))
        with chips_row:
            if items:
                ui.label("ACTIVE").style(
                    "font-size:10px; font-weight:700; color:var(--imos-primary); letter-spacing:0.1em")
            for text, kind, key in items:
                ui.chip(text, icon="filter_alt", removable=True,
                        on_value_change=_make_remove(kind, key)).props("dense").classes("imos-chip")

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
                        "font-size:12px; font-weight:700; color:var(--imos-text-2); "
                        "text-transform:uppercase; letter-spacing:0.05em; white-space:nowrap")
                    if sortable:
                        if _results_sort["col"] == key:
                            s_icon = "arrow_downward" if _results_sort["desc"] else "arrow_upward"
                            s_color = "indigo-5"
                        else:
                            s_icon = "unfold_more"
                            s_color = "grey-6"
                        ui.button(icon=s_icon, on_click=lambda k=key: _toggle_results_sort(k)).props(
                            f"flat dense round size=xs color={s_color}")
                    if filterable:
                        f_color = "red-6" if key in active else "grey-6"
                        ui.button(icon="filter_alt", on_click=lambda k=key: _open_results_filter_menu(k)).props(
                            f"flat dense round size=xs color={f_color}")

    def _open_results_filter_menu(col_key: str) -> None:
        values = _results_distinct_values(col_key, skip=col_key)
        current = _results_filters.get(col_key)
        checked = set(current) if current is not None else set(values)
        checks: dict[str, object] = {}
        col_label = _col_label(col_key)

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

    # ── family tree logic ──────────────────────────────────────────────────

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
                ft = (filter_text or "").strip().lower()
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
                f"flex:{flex}; gap:4px; font-size:11px; font-weight:700; color:var(--imos-text-2); "
                f"text-transform:uppercase; letter-spacing:0.04em"):
            ui.label(title)
            if col_key:
                icon_color = "red-6" if is_active else "grey-6"
                ui.button(icon="filter_alt", on_click=lambda c=col_key: _open_filter_menu(c)).props(
                    f"flat dense round size=sm color={icon_color}")

    def _render_header_row() -> None:
        with ui.row().classes("items-center w-full").style(
                "padding:8px 10px; gap:0; background:var(--imos-surface-2); border-bottom:2px solid var(--imos-border)"):
            _col_header("Name", "name", flex="2")
            _col_header("Type", "node_type")
            _col_header("Default Value", "value")
            _col_header("Category", "category")
            _col_header("Comment", "comment")

    def _toggle_node(nid: str) -> None:
        if nid in _family_state["expanded"]:
            _family_state["expanded"].discard(nid)
            _family_state["anim_parent"] = None
        else:
            _family_state["expanded"].add(nid)
            _family_state["anim_parent"] = nid
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

    def _render_nodes(nodes: list, depth: int, animate: bool = False) -> None:
        for n in nodes:
            nid = n["id"]
            is_family = n["node_type"] == "Family"
            has_children = bool(n.get("children"))
            expanded = nid in _family_state["expanded"] or bool(_family_state["filters"])
            selected = (nid == _family_state["selected"])

            bg = "var(--imos-surface-2)" if is_family else "transparent"
            if selected:
                bg = "var(--imos-hover)"
            guide = ""
            if depth:
                guide = (
                    "; background-image:repeating-linear-gradient(to right, transparent 0, transparent 9px, "
                    "var(--imos-guide) 9px, var(--imos-guide) 10px, transparent 10px, transparent 20px)"
                    f"; background-size:{depth * 20}px 100%; background-position:10px 0; background-repeat:no-repeat"
                )
            row_style = (f"padding:6px 10px; border-bottom:1px solid var(--imos-border-soft); "
                         f"cursor:pointer; background-color:{bg}{guide}")

            row = ui.row().classes("items-center w-full" + (" tree-anim" if animate else "")).style(row_style)
            with row:
                with ui.row().classes("items-center").style(f"flex:2; gap:4px; padding-left:{depth*20}px"):
                    if has_children:
                        icon = "expand_more" if expanded else "chevron_right"
                        ui.button(icon=icon, on_click=lambda nid=nid: _toggle_node(nid)).props(
                            "flat dense round size=sm")
                    else:
                        ui.element("div").style("width:28px")
                    ui.label(_icon_for(n["node_type"]))
                    ui.label(n["label"]).style(
                        "font-family:monospace; font-size:13px; color:var(--imos-text)"
                        + (";font-weight:700" if is_family else ""))
                with ui.element("div").style("flex:1"):
                    ui.label(n["node_type"]).classes("imos-pill").style(_pill_style(n["node_type"]))
                ui.label(n["value"]).style(
                    "flex:1; font-size:12px; color:var(--imos-success); font-family:monospace")
                ui.label(n["category"]).style("flex:1; font-size:12px; color:var(--imos-text-2)")
                ui.label(n["comment"]).style("flex:1; font-size:12px; color:var(--imos-muted)")
            if has_children and expanded:
                _render_nodes(n["children"], depth + 1,
                              animate or (nid == _family_state["anim_parent"]))

    def _render_family_tree() -> None:
        family_container.clear()
        visible = _prune(_family_state["full_tree"])
        with family_container:
            _render_header_row()
            if not visible:
                ui.label("No data — run an extraction first, then click Refresh").style(
                    "padding:12px; color:var(--imos-muted); font-size:13px")
            else:
                _render_nodes(visible, 0)
        _family_state["anim_parent"] = None

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
        lbl_search_status.style("color:var(--imos-success)").set_text(f"{idx + 1} / {len(matches)} found")
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