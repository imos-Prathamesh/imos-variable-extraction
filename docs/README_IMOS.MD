# IMOS Anglconi Extractor

Extracts all $variables from an IMOS article by following the complete Anglconi/Visio flow against a live SQL Server database.

---

## Launching

### Web UI (recommended)

    python main.py

No arguments launches the NiceGUI dashboard — Settings tab for DB credentials, Run tab to pick article/workflow, Results tab for filtering and copy-to-clipboard.

### CLI (for scripting / automation / testing individual flows)

    python main.py --test-parser
    python main.py --test-connection
    python main.py --list-articles 30
    python main.py --article "YOUR_ARTICLE_NAME"
    python main.py --article "YOUR_ARTICLE_NAME" --flow anglconi
    python main.py --article "YOUR_ARTICLE_NAME" --occurrences
    python main.py --article "YOUR_ARTICLE_NAME" --csv out.csv
    python main.py --all --csv all_results.csv

---

## Connection Setup

### Option A — Run Locally (Recommended for private-network SQL Servers)

Your SQL Server (e.g. HCS-C-244\IMOSSQL2022) is on a private LAN. Run the extractor on any machine that can reach it.

Step 1 — Install Python 3.11+
https://www.python.org/downloads/

Step 2 — Install dependencies

    pip install pymssql pyodbc tabulate colorama python-dotenv nicegui

Step 3 — Create a .env file in the project root:

    MSSQL_SERVER=HCS-C-244\IMOSSQL2022
    MSSQL_DATABASE=Fresh_DB
    MSSQL_USER=IMOSADMIN
    MSSQL_PASSWORD=your_password_here

Alternatively, use the Settings tab in the web UI — it writes the same values to config.json.

If the named instance does not connect, find the exact TCP port:
- Open SQL Server Configuration Manager on the DB host
- SQL Server Network Configuration -> Protocols for your instance
- TCP/IP -> IP Addresses tab -> IPAll -> TCP Dynamic Ports (e.g. 52716)
- Then use: MSSQL_SERVER=HCS-C-244,52716

Step 4 — Run

    python main.py --test-connection
    python main.py --list-articles 20
    python main.py --article "ARTICLE_NAME"

### Option B — Tunnel via ngrok

On the machine that can reach SQL Server:

    ngrok tcp 1433
    (or, for a named instance port)
    ngrok tcp 52716

Update MSSQL_SERVER to the forwarded host,port (e.g. 0.tcp.ngrok.io,12345), then run as normal.

### Option C — SQL Server port already exposed on a reachable IP

    MSSQL_SERVER = 203.0.113.50,1433

---

## Connection Troubleshooting

| Symptom | Fix |
|---|---|
| Name or service not known | Hostname not reachable — use IP or ngrok |
| Connection refused on port 1433 | Named instance uses a different port — check SQL Server Config Manager |
| Login failed for user | Wrong MSSQL_USER / MSSQL_PASSWORD |
| Cannot open database | Wrong MSSQL_DATABASE, or user has no access |
| TLS/SSL error | Encrypt=no already set in code (pyodbc path) |
| Incorrect syntax near '?' | Already fixed in core/db.py — placeholders auto-adapt to pymssql (%s) vs pyodbc (?) |

---

## Output Explanation

Unique Variables (per article) — one row per variable name; last resolved value wins.

Occurrences (--occurrences) — every resolution path in traversal order: variable name, value, source table, source column, resolution method (DIRECT / IMOS / DESCRIPTOR), and full path from the entry table.

CSV — all occurrences with article name (and, for --all, flow name) prefix — ready for Excel/Power BI.

---

## Flows Implemented

Flows are auto-discovered from flows/ — run python main.py --article "X" --flow doesnotexist to see the current live list. As of this writing:

### anglconi

    articles.NAME
      -> anglconi (INORDER blank/NULL)
          -> CONISITU
              |- $var -> IMOS.NAME -> IMOS.WERT -> classify again
              |- #desc -> DESCRIPTOR -> DESCRIPTORVALUES.LINDIV -> classify again
              `- raw -> CONNECTIONS.NAME
                        |- CONNSELTREE -> CHILDID -> classify
                        |- CONNDESC -> ARTICLE_ID, ORDER_ID, SPRICE, SCFACTOR, SWEIGHT
                        |- CONNEXTRA -> CONNVALUE
                        |- CONNGROUPS -> CONNGROUP -> WORKGROUP
                        |     |- PRF -> PROFIL -> PRFDESCR/RENDER_PRZ/contelem
                        |     `- CONTOUR -> contelem
                        |- GROOVE -> nut_erb (LIN_TEIL, SFUGE_Y, SLANGUEBV...)
                        |- LINDIV / LINDIV2 / ROTATION / POSPART0VAR / SNAPRADI / VARIANT
                        |- extrupar -> SECTNAME/CONT/GROOVE/GAP/RENDER/INFOFOLDER
                        `- extrucon -> CONNAME
                                        |- raw -> CONNECTIONS.NAME  <- explicit return
                                        `- $ -> IMOS -> classify again

### anglclie

    articles.NAME -> anglclie.TAGVALUE -> IMOS loop only (no connection tree)

### anglgrtx

    articles.NAME -> anglgrtx.TEXT -> IMOS loop only (no connection tree)

All extracted values containing $ or # are recursively resolved. Cycle detection prevents infinite loops — cycles are reported separately.

Note: a flow returning 0 results for a real article is normal if that flow's source table has no qualifying row for that article — it does not indicate a bug. See docs/README_PROJECT.md section 10 for how to verify.

---

## Adding More Flows

See docs/How to Add a New Flow.txt. Short version: copy flows/traversal_myflow.py, point it at your table, add FLOW_NAME + extract at the bottom. No other file needs to be touched — it appears automatically in CLI and UI.

If a single value can match several possible tables (not a new starting
point), that's a new candidate branch inside an existing flow file, not
a new flow. See docs/How_to_Add_Flows_and_Branches_with_AI.txt.