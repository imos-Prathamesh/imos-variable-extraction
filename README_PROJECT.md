# IMOS Anglconi Variable Extractor — Project Guide

---

## 1. How This Project Works (Plain Language)

Think of this project like a **treasure hunt through a database**.

Every IMOS article (a furniture/cabinet product) has a network of connected tables — like a tree with many branches. Hidden inside these tables are **variables** (values starting with `$`) and **descriptors** (values starting with `#`) that control how the product behaves.

This project:
1. Starts at an article name
2. Follows every branch and sub-branch through the database
3. Collects every variable and descriptor it finds
4. Returns the full list with where it was found

**The 5 files and what each one does:**

| File | Plain Purpose |
|------|--------------|
| `branches.py` | A **menu of tables** — lists every database table to check, which columns to read, and where to go next |
| `traversal.py` | The **engine** — actually walks through the branches, follows the chains, and collects results |
| `parser.py` | The **detector** — scans any text value and spots `$variables` and `#descriptors` inside it |
| `db.py` | The **connection** — handles talking to SQL Server, nothing else |
| `main.py` | The **command panel** — lets you run everything from the terminal |

---

## 2. How to Add or Remove Columns for Any Table

Every table in the system is described in **`branches.py`**.

Each table entry looks like this:

```
STATE_CONNECTIONS: Branch(
    match_table  = "CONNECTIONS"       ← the database table name
    match_column = "NAME"              ← the column used to find matching rows
    filter_column = "INORDER"          ← a column that must be blank/NULL to qualify
    value_columns = [                  ← THE COLUMNS YOU WANT TO READ
        "CONNDIRECT",
        "LINDIV",
        "ROTATION",
        ...
    ]
    next_state = STATE_CONNECTIONS     ← where results go after being read
)
```

**To ADD a column:** Find the right table in `branches.py`, add the column name to `value_columns`.

**To REMOVE a column:** Find the right table in `branches.py`, delete the column name from `value_columns`.

**Special cases in `traversal.py`:** Some columns are handled individually because they need special routing (like SECTNAME going to contelem, or GROOVE going to nut_erb). These are in `_extrupar_branch`, `_profil_branch`, and `_process_connections_row`. Search for the column name in `traversal.py` to find and edit those.

**Rule of thumb:**
- Normal column that just has a `$value` → add to `branches.py` only
- Column that routes to a different table → also needs a line in `traversal.py`

---

## 3. How to Change or Add a Branch/Flow

The flow is built from two parts:

### Part A — Register the table in `branches.py`

Add a new `Branch` entry:

```python
STATE_MY_NEW_TABLE: Branch(
    label         = "MY_NEW_TABLE",
    match_table   = "MY_NEW_TABLE",       # exact DB table name
    match_column  = "NAME",               # column to match on
    filter_column = "INORDER",            # blank/NULL filter column
    value_columns = ["COL1", "COL2"],     # columns to extract variables from
    next_state    = STATE_CONNECTIONS,    # where values go next
    order_columns = ["ID"],               # optional ORDER BY
)
```

Also add the state constant at the top of `branches.py`:
```python
STATE_MY_NEW_TABLE = "MY_NEW_TABLE"
```

### Part B — Connect it in `traversal.py`

Find the point in the flow where you want this new table to be checked, and add one line:

```python
self._generic_branch(name, STATE_MY_NEW_TABLE, path)
```

That's it for most cases. The engine handles the rest automatically.

**If the new table needs special column routing** (like different columns going to different places), create a dedicated method like `_my_new_table_branch` following the same pattern as `_extrupar_branch`.

---

## 4. How to Handle 50 Different Workflows

Each workflow is just a **different starting point and a different set of branches**.

The best approach for 50 workflows:

- Keep `branches.py`, `db.py`, `parser.py` as **shared** files — they work for all workflows
- Create a **separate traversal file per workflow** if the flow is very different (e.g. `traversal_anglconi.py`, `traversal_profiles.py`)
- Or add a **workflow name parameter** to the existing traversal to switch branch sets

For now, if your 50 workflows all follow the same general pattern (start → connections → branches → IMOS loop), you only need to add new Branch entries in `branches.py` and new call lines in `traversal.py`.

---

## 5. Do You Need New Files?

| Situation | What to Do |
|-----------|-----------|
| New columns in existing tables | Edit `branches.py` only |
| New table in same flow | Edit `branches.py` + one line in `traversal.py` |
| Completely new flow/workflow | New `traversal_XXX.py` file + new command in `main.py` |
| New database connection | Edit `db.py` only |
| New output format (Excel, JSON) | Edit `main.py` only |

**Short answer: For most changes, you only touch `branches.py`. You need new files only when adding a completely separate workflow.**

---

## 6. How to Expand This for Future AI-Assisted Development

When you want to give a new workflow to Claude (or any AI) to implement, provide:

**1. The flow diagram** (like the Visio file you shared) — this is the most important thing

**2. A plain-language description like this:**
```
Start from TABLE_A.COLUMN_X
If value has $, look up in IMOS
If value has #, look up in DESCRIPTOR
If raw value, match with TABLE_B.NAME where INORDER is blank
From TABLE_B, check these columns: COL1, COL2, COL3
COL1 goes to TABLE_C.NAME
COL2 is just a variable, extract it
COL3 goes back to start
```

**3. A sample SQL result** showing what real data looks like in the new tables

With those 3 things, any new workflow can be added cleanly without confusion.

---

## 7. Project File Map (Quick Reference)

```
imos_extractor/
│
├── branches.py       ← EDIT THIS to add/remove tables and columns
├── traversal.py      ← EDIT THIS to change flow routing logic
├── parser.py         ← Do not touch unless $ or # rules change
├── db.py             ← Do not touch unless DB connection changes
├── main.py           ← EDIT THIS to add new commands or output formats
├── run.py            ← Just runs main.py, no changes needed
└── .env              ← Your DB credentials, never share this file
```

---

## 8. Quick Command Reference

```bash
# Check DB connection
python main.py --test-connection

# List available articles
python main.py --list-articles 30

# Extract one article
python main.py --article "ARTICLE_NAME"

# Extract with full path detail
python main.py --article "ARTICLE_NAME" --occurrences

# Save to CSV
python main.py --article "ARTICLE_NAME" --csv output.csv

# Extract all articles
python main.py --all --csv all_results.csv
```

---

## 9. Troubleshooting

| Problem | Likely Cause | Fix |
|---------|-------------|-----|
| Variable missing from results | Column not in `value_columns` | Add to `branches.py` |
| Whole table branch not followed | Branch not called in `traversal.py` | Add `_generic_branch(name, STATE_XXX, path)` |
| Sub-variables of a resolved name missing | Raw value going to CONNECTIONS instead of sub-branches | Use `_resolve_then_branch` or `_direct_sub_branches` |
| INORDER filter blocking rows | That table stores rows with INORDER set | Remove filter for that specific query |
| Variable shows [NOT IN IMOS] | Name not in IMOS table or ORDERID is set | Check DB: `SELECT * FROM IMOS WHERE NAME='xxx'` |
