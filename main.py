#!/usr/bin/env python3
# Source : main.py (project root)
# Analogy: Control panel — the only file you run from terminal. Wires all flows together and handles all commands.
"""
IMOS Variable Extractor — CLI entry point

Flows available
───────────────
  anglconi  →  articles → anglconi.CONISITU → IMOS / DESCRIPTOR / CONNECTIONS (full tree)
  anglclie  →  articles → anglclie.TAGVALUE → IMOS loop only
  anglgrtx  →  articles → anglgrtx.TEXT     → IMOS loop only

Usage
─────
  # Parser self-test (no DB needed — run this first)
  python main.py --test-parser

  # Test DB connection + check all tables
  python main.py --test-connection

  # List available article names
  python main.py --list-articles 20

  # Extract one article — runs ALL flows, shows which flow found what
  python main.py --article "MY_ARTICLE"

  # Extract one article — specific flow only
  python main.py --article "MY_ARTICLE" --flow anglconi
  python main.py --article "MY_ARTICLE" --flow anglclie
  python main.py --article "MY_ARTICLE" --flow anglgrtx

  # Show full occurrence path detail
  python main.py --article "MY_ARTICLE" --occurrences

  # Save results to CSV
  python main.py --article "MY_ARTICLE" --csv output/results.csv

  # Extract ALL articles — save to CSV
  python main.py --all --csv output/all_results.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
import traceback
from pathlib import Path

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    GREEN  = Fore.GREEN
    RED    = Fore.RED
    YELLOW = Fore.YELLOW
    CYAN   = Fore.CYAN
    BOLD   = Style.BRIGHT
    RESET  = Style.RESET_ALL
except ImportError:
    GREEN = RED = YELLOW = CYAN = BOLD = RESET = ""

try:
    from tabulate import tabulate
    HAS_TABULATE = True
except ImportError:
    HAS_TABULATE = False


# ── helpers ───────────────────────────────────────────────────────────────────

def _header(msg: str) -> None:
    print(f"\n{BOLD}{CYAN}{'═'*70}{RESET}")
    print(f"{BOLD}{CYAN}  {msg}{RESET}")
    print(f"{BOLD}{CYAN}{'═'*70}{RESET}")


def _ok(msg: str) -> None:
    print(f"{GREEN}✓ {msg}{RESET}")


def _err(msg: str) -> None:
    print(f"{RED}✗ {msg}{RESET}", file=sys.stderr)


def _warn(msg: str) -> None:
    print(f"{YELLOW}⚠ {msg}{RESET}")


def _tbl(rows: list[list], headers: list[str]) -> None:
    if not rows:
        print("  (no results)")
        return
    if HAS_TABULATE:
        print(tabulate(rows, headers=headers, tablefmt="simple"))
    else:
        print("\t".join(headers))
        for r in rows:
            print("\t".join(str(x) for x in r))


# ── subcommands ───────────────────────────────────────────────────────────────

def cmd_test_connection() -> None:
    _header("Test SQL Server Connection")
    try:
        from core.db import get_connection, query, normalize
        conn = get_connection()
        _ok("Connected to SQL Server")

        tables = query(
            "SELECT TABLE_SCHEMA, TABLE_NAME "
            "FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_TYPE = 'BASE TABLE' "
            "  AND TABLE_NAME IN ("
            "  'articles','anglconi','IMOS','CONNECTIONS','CONNSELTREE',"
            "  'CONNDESC','CONNEXTRA','CONNGROUPS','WORKGROUP','PROFIL',"
            "  'RENDER','contelem','nut_erb','extrupar','extrucon',"
            "  'DESCRIPTOR','DESCRIPTORVALUES','ident'"
            ") ORDER BY TABLE_NAME"
        )
        _ok(f"Found {len(tables)} expected tables:")
        for t in tables:
            print(f"    {t['TABLE_SCHEMA']}.{t['TABLE_NAME']}")

        expected = {
            'articles','anglconi','IMOS','CONNECTIONS','CONNSELTREE',
            'CONNDESC','CONNEXTRA','CONNGROUPS','WORKGROUP','PROFIL',
            'RENDER','contelem','nut_erb','extrupar','extrucon',
            'DESCRIPTOR','DESCRIPTORVALUES','ident'
        }
        found = {t['TABLE_NAME'] for t in tables}
        missing = expected - found
        if missing:
            _warn(f"Missing tables: {', '.join(sorted(missing))}")
        else:
            _ok("All 18 expected tables present")

        # Row counts
        print()
        for tname in sorted(expected & found):
            try:
                n = query(f"SELECT COUNT(*) AS n FROM dbo.[{tname}]")[0]["n"]
                print(f"    {tname:30s} {n:>8,} rows")
            except Exception as e:
                _warn(f"    {tname}: {e}")

    except Exception as e:
        _err(f"Connection failed: {e}")
        traceback.print_exc()
        sys.exit(1)


def cmd_list_articles(n: int) -> None:
    _header(f"First {n} Articles")
    from core.db import query
    rows = query(
        f"SELECT TOP ({n}) NAME FROM dbo.articles ORDER BY NAME"
    )
    for i, r in enumerate(rows, 1):
        print(f"  {i:4d}. {r['NAME']}")
    print(f"\n  (showing {len(rows)} of up to {n})")


def cmd_test_parser() -> None:
    _header("Parser Self-Test")
    from core.parser import parse

    cases = [
        ("$DOOR_EDGE", ["DOOR_EDGE"], []),
        ("$MAT_1", ["MAT_1"], []),
        ("900mm+$Handle_Position_WD_X:1", ["Handle_Position_WD_X"], []),
        ("715mm+$Handle_Position_X:1", ["Handle_Position_X"], []),
        ("#CAM_for_Dowel", [], ["CAM_for_Dowel"]),
        ("HMEB22X081103", [], []),
        ("", None, None),
        (None, None, None),
        ("$DOOR_SURF_EXTERIOR", ["DOOR_SURF_EXTERIOR"], []),
        ("$PRF_1", ["PRF_1"], []),
    ]

    passed = 0
    for raw, exp_vars, exp_descs in cases:
        pv = parse(raw)
        if exp_vars is None:
            ok = pv is None
        else:
            ok = (
                pv is not None
                and pv.variables == exp_vars
                and pv.descriptors == exp_descs
            )
        sym = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
        print(f"  [{sym}]  {repr(raw):45s}  vars={pv.variables if pv else None}  descs={pv.descriptors if pv else None}")
        if ok:
            passed += 1

    print(f"\n  {passed}/{len(cases)} passed")
    if passed < len(cases):
        sys.exit(1)


def cmd_extract(article: str, show_occurrences: bool, csv_path: str | None, _result=None, flow_label: str = "") -> None:
    _header(f"Extract: {article}" + (f"  [flow: {flow_label}]" if flow_label else "  [flow: all]"))

    if _result is not None:
        result = _result
    else:
        from flows.traversal_anglconi import extract_article
        result = extract_article(article)

    print(f"\n{BOLD}Unique Variables ({len(result.unique_vars)}){RESET}")
    rows = sorted(result.unique_vars.items())
    _tbl([[k, v] for k, v in rows], ["Variable", "Value"])

    if show_occurrences or csv_path:
        print(f"\n{BOLD}Occurrences ({len(result.occurrences)}){RESET}")
        occ_rows = [
            [
                o.variable_name,
                o.value,
                o.source_table,
                o.source_column,
                o.resolved_via,
                o.path_str(),
            ]
            for o in result.occurrences
        ]
        headers = ["Variable", "Value", "Table", "Column", "Via", "Path"]
        if show_occurrences:
            _tbl(occ_rows, headers)

        if csv_path:
            p = Path(csv_path)
            with p.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["Article"] + headers)
                for orow, data in zip(result.occurrences, occ_rows):
                    w.writerow([article] + data)
            _ok(f"Saved {len(occ_rows)} rows → {p.resolve()}")

    if result.cycles:
        print(f"\n{YELLOW}{BOLD}Cycles detected ({len(result.cycles)}):{RESET}")
        for c in result.cycles:
            print(f"  {YELLOW}{c}{RESET}")


def cmd_extract_all(csv_path: str | None) -> None:
    _header("Extract All Articles")
    from flows.traversal_anglconi import extract_all_articles

    results = extract_all_articles()
    total_occ = sum(len(r.occurrences) for r in results)
    total_vars = sum(len(r.unique_vars) for r in results)
    print(f"\n  Articles processed : {len(results)}")
    print(f"  Total occurrences  : {total_occ}")
    print(f"  Total unique vars  : {total_vars}")

    if csv_path:
        p = Path(csv_path)
        with p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Article", "Variable", "Value", "Table", "Column", "Via", "Path"])
            for r in results:
                for o in r.occurrences:
                    w.writerow([
                        r.article, o.variable_name, o.value,
                        o.source_table, o.source_column,
                        o.resolved_via, o.path_str(),
                    ])
        _ok(f"Saved → {p.resolve()}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description="IMOS Anglconi Extractor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--test-connection", action="store_true",
                    help="Verify DB connection and table presence")
    ap.add_argument("--test-parser", action="store_true",
                    help="Run parser self-tests (no DB needed)")
    ap.add_argument("--list-articles", type=int, metavar="N",
                    help="List first N article names from the DB")
    ap.add_argument("--article", metavar="NAME",
                    help="Extract a single article by NAME")
    ap.add_argument("--flow", metavar="FLOW", default=None,
                    help="Flow to use: anglconi, anglclie, anglgrtx. Omit to run all flows.")
    ap.add_argument("--all", action="store_true",
                    help="Extract all articles")
    ap.add_argument("--occurrences", action="store_true",
                    help="Print full occurrence table (with --article)")
    ap.add_argument("--csv", metavar="FILE",
                    help="Save results to CSV file")
    ap.add_argument("--max-depth", type=int, default=40,
                    help="Maximum traversal depth per path (default 40)")

    args = ap.parse_args()

    if args.test_parser:
        cmd_test_parser()
        return

    if args.test_connection:
        cmd_test_connection()
        return

    if args.list_articles:
        cmd_list_articles(args.list_articles)
        return

    if args.article:
        if args.flow is None:
            from flows.traversal_anglconi import extract_article
            from flows.traversal_anglclie import extract_anglclie
            from flows.traversal_anglgrtx import extract_anglgrtx
            from core.traversal_base import ExtractionResult

            flows_to_run = [
                ("anglconi", extract_article),
                ("anglclie", extract_anglclie),
                ("anglgrtx", extract_anglgrtx),
            ]
            combined = ExtractionResult(article=args.article)
            for flow_name, flow_fn in flows_to_run:
                print(f"\n{BOLD}  ▶ Running flow: {flow_name}{RESET}")
                flow_result = flow_fn(args.article)
                if flow_result.unique_vars:
                    for var, val in sorted(flow_result.unique_vars.items()):
                        print(f"    {CYAN}{flow_name}{RESET}  →  {var} = {val}")
                else:
                    print(f"    (no variables found in {flow_name})")
                combined.occurrences.extend(flow_result.occurrences)
                combined.unique_vars.update(flow_result.unique_vars)
                combined.cycles.extend(flow_result.cycles)
            cmd_extract(args.article, args.occurrences, args.csv,
                        _result=combined, flow_label="")
        elif args.flow == "anglclie":
            from flows.traversal_anglclie import extract_anglclie
            result = extract_anglclie(args.article)
            cmd_extract(args.article, args.occurrences, args.csv,
                        _result=result, flow_label="anglclie")
        elif args.flow == "anglgrtx":
            from flows.traversal_anglgrtx import extract_anglgrtx
            result = extract_anglgrtx(args.article)
            cmd_extract(args.article, args.occurrences, args.csv,
                        _result=result, flow_label="anglgrtx")
        elif args.flow == "anglconi":
            cmd_extract(args.article, args.occurrences, args.csv,
                        flow_label="anglconi")
        else:
            _err(f"Unknown flow: {args.flow}")
        return

    if args.all:
        cmd_extract_all(args.csv)
        return

    ap.print_help()


if __name__ == "__main__":
    main()