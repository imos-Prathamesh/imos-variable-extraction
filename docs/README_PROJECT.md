# IMOS Anglconi Variable Extractor — Project Guide

---

## 1. How This Project Works (Plain Language)

Think of this project like a treasure hunt through a database.

Every IMOS article (a furniture/cabinet product) has a network of connected tables — like a tree with many branches. Hidden inside these tables are variables (values starting with $) and descriptors (values starting with #) that control how the product behaves.

This project:
1. Starts at an article name
2. Follows every branch and sub-branch through the database
3. Collects every variable and descriptor it finds
4. Returns the full list with where it was found

The core files and what each one does:

| File | Plain Purpose |
|------|--------------|
| core/branches.py | A menu of tables — lists every database table to check, which columns to read, and where to go next |
| core/traversal_base.py | The engine — the shared recursive core (IMOS lookup, descriptor lookup, cycle detection) every flow builds on |
| core/parser.py | The detector — scans any text value and spots $variables and #descriptors inside it |
| core/db.py | The connection — handles talking to SQL Server, nothing else |
| core/flow_registry.py | The staff directory — auto-discovers every flow module in flows/ so nothing needs manual wiring |
| flows/traversal_mixins.py | Plug-in attachments — ConnectionTreeMixin (full connection tree walk) or ImosMixin (IMOS-only loop) |
| flows/traversal_xxx.py | One file per workflow — the actual entry point + logic for that flow |
| main.py | The command panel — CLI entry point, or launches the web UI when run with no arguments |
| ui/main_window.py | The web dashboard — Settings / Run / Results, built with NiceGUI |

---

## 2. The Flow Registry (auto-discovery — read this first)

Adding a new workflow does not require editing main.py or ui/main_window.py. core/flow_registry.py scans every module inside flows/ at startup and picks up any module that defines:

    FLOW_NAME = "your_flow_name"
    extract = your_extract_function   (signature: (article, max_depth=40) -> ExtractionResult)

Optionally also:

    extract_all = your_extract_all_function   (signature: (max_depth=40) -> list[ExtractionResult])

That's it. The flow immediately becomes available via:
- CLI: python main.py --article "X" --flow your_flow_name
- CLI: python main.py --article "X" (runs as part of "all flows")
- CLI: python main.py --all (if extract_all is defined)
- UI: appears in the Workflow dropdown (click "Refresh Flow List" if UI already running)

A module with no FLOW_NAME is silently skipped — this is how flows/traversal_myflow.py stays a safe copy-paste template that is never accidentally run.

See docs/How to Add a New Flow.txt for full step-by-step instructions and examples.

---

## 3. How to Add or Remove Columns for Any Table

Every table in the system is described in core/branches.py.

Each table entry looks like this:

    STATE_CONNECTIONS: Branch(
        match_table  = "CONNECTIONS"       the database table name
        match_column = "NAME"              the column used to find matching rows
        filter_column = "INORDER"          a column that must be blank/NULL to qualify
        value_columns = [                  THE COLUMNS YOU WANT TO READ
            "CONNDIRECT",
            "LINDIV",
            "ROTATION",
            ...
        ]
        next_state = STATE_CONNECTIONS     where results go after being read
    )

To ADD a column: Find the right table in core/branches.py, add the column name to value_columns.

To REMOVE a column: Find the right table in core/branches.py, delete the column name from value_columns.

Special cases in flows/traversal_mixins.py: Some columns are handled individually because they need special routing (like SECTNAME going to contelem, or GROOVE going to nut_erb). These are in _extrupar_branch, _profil_branch, and _process_connections_row. Search for the column name in flows/traversal_mixins.py to find and edit those.

Rule of thumb:
- Normal column that just has a $value -> add to core/branches.py only
- Column that routes to a different table -> also needs a line in flows/traversal_mixins.py

---

## 4. How to Change or Add a Branch (sub-table within an existing flow's tree)

### Part A — Register the table in core/branches.py

Add a new Branch entry:

    STATE_MY_NEW_TABLE: Branch(
        label         = "MY_NEW_TABLE",
        match_table   = "MY_NEW_TABLE",       exact DB table name
        match_column  = "NAME",               column to match on
        filter_column = "INORDER",            blank/NULL filter column
        value_columns = ["COL1", "COL2"],     columns to extract variables from
        next_state    = STATE_CONNECTIONS,    where values go next
        order_columns = ["ID"],               optional ORDER BY
    )

Also add the state constant at the top of core/branches.py:

    STATE_MY_NEW_TABLE = "MY_NEW_TABLE"

### Part B — Connect it in flows/traversal_mixins.py

Find the point in the flow where you want this new table to be checked, and add one line:

    self._generic_branch(name, STATE_MY_NEW_TABLE, path)

That's it for most cases. The engine handles the rest automatically.

If the new table needs special column routing (like different columns going to different places), create a dedicated method like _my_new_table_branch following the same pattern as _extrupar_branch.

---

## 4a. New Candidate Table vs New Flow (read this before adding anything)

Sometimes one value (like CONISITU) can match many possible tables —
that is NOT a new flow, just a new candidate branch inside the existing
file. A new flow file is only needed when the starting chain itself
changes (different 2nd or 3rd table). See docs/How_to_Add_Flows_and_Branches_with_AI.txt
for the full decision guide, file naming convention, and what to give
an AI assistant for each case.

## 5. How to Add a Brand New Workflow (completely separate flow)

See docs/How to Add a New Flow.txt for the full step-by-step guide and worked examples. Short version:

1. Copy flows/traversal_myflow.py to flows/traversal_<yourflow>.py
2. Point its SQL query at the right table/entry column
3. Add FLOW_NAME = "<yourflow>" and extract = extract_<yourflow> at the bottom
4. Test: python main.py --article "X" --flow <yourflow>

No other file needs editing. This scales to any number of workflows — each new flow is one new file.

---

## 6. Do You Need New Files?

| Situation | What to Do |
|-----------|-----------|
| New columns in existing tables | Edit core/branches.py only |
| New sub-table in an existing flow | Edit core/branches.py + one line in flows/traversal_mixins.py |
| Completely new flow/workflow | New flows/traversal_XXX.py file with FLOW_NAME + extract() — no other file touched |
| New database connection setting | Edit core/db.py only |
| New output format (Excel, JSON) | Edit main.py only |

Short answer: For most changes, you only touch core/branches.py. You need new files only when adding a completely separate workflow — and even then, nothing else needs editing.

---

## 7. How to Expand This for Future AI-Assisted Development

When you want to give a new workflow to Claude (or any AI) to implement, provide:

1. The flow diagram (like the Visio file you shared) — this is the most important thing

2. A plain-language description like this:

    Start from TABLE_A.COLUMN_X
    If value has $, look up in IMOS
    If value has #, look up in DESCRIPTOR
    If raw value, match with TABLE_B.NAME where INORDER is blank
    From TABLE_B, check these columns: COL1, COL2, COL3
    COL1 goes to TABLE_C.NAME
    COL2 is just a variable, extract it
    COL3 goes back to start

3. A sample SQL result showing what real data looks like in the new tables

With those 3 things, any new workflow can be added cleanly without confusion — and it will register itself automatically via the flow registry described in section 2.

---

## 8. Project File Map (Quick Reference)

    imos variable extraction/
    │
    ├── main.py                     CLI entry point + launches UI with no args
    ├── config.json                 DB credentials, written by UI Settings tab
    ├── .env                        Alternative DB credentials source, never share
    │
    ├── core/
    │   ├── branches.py             EDIT to add/remove tables and columns
    │   ├── traversal_base.py       Shared recursive engine — rarely touched
    │   ├── parser.py               $ / # token parser — rarely touched
    │   ├── db.py                   DB connection layer — edit only for connection changes
    │   └── flow_registry.py        Auto-discovers flows — do not need to edit
    │
    ├── flows/
    │   ├── traversal_mixins.py     EDIT to change shared flow routing logic
    │   ├── traversal_anglconi.py   Flow: anglconi
    │   ├── traversal_anglclie.py   Flow: anglclie
    │   ├── traversal_anglgrtx.py   Flow: anglgrtx
    │   ├── traversal_myflow.py     Template only — copy this for new flows
    │   └── traversal_<yourflow>.py Add new flows here, one file each
    │
    ├── ui/
    │   └── main_window.py          NiceGUI dashboard (Settings / Run / Results)
    │
    ├── docs/
    │   ├── How to Run.txt
    │   ├── How to Add a New Flow.txt
    │   ├── README_IMOS.MD
    │   └── README_PROJECT.md       this file
    │
    └── output/                     Default location for CSV exports

---

## 9. Quick Command Reference

    python main.py
    python main.py --test-connection
    python main.py --list-articles 30
    python main.py --article "X" --flow doesnotexist
    python main.py --article "ARTICLE_NAME" --flow anglconi
    python main.py --article "ARTICLE_NAME"
    python main.py --article "ARTICLE_NAME" --flow anglconi --occurrences
    python main.py --article "ARTICLE_NAME" --flow anglconi --csv output/results.csv
    python main.py --all --csv output/all_results.csv

---

## 10. Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Unknown flow: X | Flow module missing FLOW_NAME or has an import error | Check for "[flow_registry] skipped ..." warning at startup; fix the reported error |
| New flow doesn't show in UI dropdown | UI was already running when flow file was added | Click "Refresh Flow List" on the Run tab |
| Variable missing from results | Column not in value_columns | Add to core/branches.py |
| Whole table branch not followed | Branch not called in flows/traversal_mixins.py | Add _generic_branch(name, STATE_XXX, path) |
| Sub-variables of a resolved name missing | Raw value going to CONNECTIONS instead of sub-branches | Use _resolve_then_branch or _direct_sub_branches |
| INORDER filter blocking rows | That table stores rows with INORDER set | Remove filter for that specific query |
| Variable shows [NOT IN IMOS] | Name not in IMOS table or ORDERID is set | Check DB: SELECT * FROM IMOS WHERE NAME='xxx' |
| A real article returns 0 results for a flow | That flow's source table has no matching row (or INORDER isn't blank) for this article | Confirm with a direct SQL check on the source table — this is expected, not a bug |
| Incorrect syntax near '?' | pymssql was used with ? placeholders (pyodbc syntax) | Already handled in core/db.py — placeholders are auto-converted per active driver |