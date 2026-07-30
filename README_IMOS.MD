IMOS Anglconi Extractor
Extracts all $variables from an IMOS article by following the complete Anglconi/Visio flow against a live SQL Server database.

Quick Commands
# Parser self-test (no DB needed — run this first)
python -m imos_extractor.main --test-parser
# Test DB connection + check all 18 tables
python -m imos_extractor.main --test-connection
# List available article names (first 30)
python -m imos_extractor.main --list-articles 30
# Extract one article — show unique variables
python -m imos_extractor.main --article "YOUR_ARTICLE_NAME"
# Extract one article — show every occurrence path
python -m imos_extractor.main --article "YOUR_ARTICLE_NAME" --occurrences
# Extract one article — save to CSV
python -m imos_extractor.main --article "YOUR_ARTICLE_NAME" --csv out.csv
# Extract ALL articles — save to CSV
python -m imos_extractor.main --all --csv all_results.csv

Connection Setup
Option A — Run Locally (Recommended for private-network SQL Servers)
Your SQL Server (HCS-C-244\IMOSSQL2022) is on a private LAN. Run the extractor on any machine that can reach it:

Step 1 — Install Python 3.11+

https://www.python.org/downloads/

Step 2 — Install dependencies

pip install pymssql tabulate colorama python-dotenv

Step 3 — Create a .env file in the project root:

MSSQL_SERVER=HCS-C-244\IMOSSQL2022
MSSQL_DATABASE=Fresh_DB
MSSQL_USER=IMOSADMIN
MSSQL_PASSWORD=your_password_here

If the named instance does not connect, find the exact TCP port:

Open SQL Server Configuration Manager on HCS-C-244
SQL Server Network Configuration → Protocols for IMOSSQL2022
TCP/IP → IP Addresses tab → IPAll → TCP Dynamic Ports (e.g. 52716)
Then use: MSSQL_SERVER=HCS-C-244,52716
Step 4 — Run

python -m imos_extractor.main --test-connection
python -m imos_extractor.main --list-articles 20
python -m imos_extractor.main --article "ARTICLE_NAME"

Option B — Tunnel via ngrok (run from Replit, reach your LAN SQL Server)
On the machine that can reach SQL Server (Windows/Mac/Linux):

Download ngrok: https://ngrok.com/download
Start a TCP tunnel to your SQL Server port:
ngrok tcp 1433

Or if using a named instance port (e.g. 52716):
ngrok tcp 52716

ngrok will show something like:
Forwarding  tcp://0.tcp.ngrok.io:12345 -> localhost:1433

In Replit Secrets, update:

MSSQL_SERVER = 0.tcp.ngrok.io,12345

(use the host,port format — no instance name needed, just the forwarded port)

Then run from Replit:

python -m imos_extractor.main --test-connection

Option C — SQL Server port already exposed on a public/reachable IP
Update the MSSQL_SERVER secret to the public IP and port:

MSSQL_SERVER = 203.0.113.50,1433

Connection Troubleshooting
Symptom	Fix
Name or service not known	Hostname not reachable — use IP or ngrok
Connection refused on port 1433	Named instance uses a different port — check SQL Server Config Manager
Login failed for user	Wrong MSSQL_USER / MSSQL_PASSWORD
Cannot open database	Wrong MSSQL_DATABASE, or user has no access
TLS/SSL error	Add Encrypt=no to connection string (already set in code)
Output Explanation
Unique Variables (per article)
One row per variable name — last resolved value wins. Useful for "what is the current value of X for article Y?"

Occurrences (with --occurrences)
Every resolution path in traversal order. Includes: variable name, value, source table, source column, resolution method (DIRECT / IMOS / DESCRIPTOR), and the full path from anglconi.

CSV
All occurrences with article name prefix — ready for Excel/Power BI.

Flow Implemented
articles.NAME
  → anglconi (INORDER blank/NULL)
      → CONISITU
          ├─ $var → IMOS.NAME → IMOS.WERT → classify again
          ├─ #desc → DESCRIPTOR → DESCRIPTORVALUES.LINDIV → classify again
          └─ raw → CONNECTIONS.NAME
                    ├─ CONNSELTREE → CHILDID → classify
                    ├─ CONNDESC → ARTICLE_ID, ORDER_ID, SPRICE, SCFACTOR, SWEIGHT
                    ├─ CONNEXTRA → CONNVALUE
                    ├─ CONNGROUPS → CONNGROUP → WORKGROUP
                    │     ├─ PRF → PROFIL → PRFDESCR/RENDER_PRZ/contelem
                    │     └─ CONTOUR → contelem
                    ├─ GROOVE → nut_erb (LIN_TEIL, SFUGE_Y, SLANGUEBV…)
                    ├─ LINDIV / LINDIV2 / ROTATION / POSPART0VAR / SNAPRADI / VARIANT
                    ├─ extrupar → SECTNAME/CONT/GROOVE/GAP/RENDER/INFOFOLDER
                    └─ extrucon → CONNAME
                                    ├─ raw → CONNECTIONS.NAME  ← explicit return
                                    └─ $ → IMOS → classify again

All extracted values that contain $ or # are recursively resolved. Cycle detection prevents infinite loops — cycles are reported separately.