# Source : core/db.py
# Analogy: Phone line to SQL Server — every file uses this to talk to the database. Touch only when credentials or driver changes.
"""
SQL Server connection layer.
Reads credentials from environment variables OR from a .env file in the
project root (for local runs).

  MSSQL_SERVER   = host or host,port or host\\instance or IP,port
  MSSQL_DATABASE = database name
  MSSQL_USER     = SQL login username
  MSSQL_PASSWORD = SQL login password

Connection priority:
  1. pymssql  (bundled TDS, no ODBC driver needed — preferred)
  2. pyodbc   (needs a working ODBC driver; FreeTDS or msodbcsql)
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# Load config.json written by UI settings panel
_cfg_file = Path(__file__).parent.parent / "config.json"
if _cfg_file.exists():
    try:
        import json as _json
        _cfg = _json.loads(_cfg_file.read_text())
        for _k, _env in (("server",   "MSSQL_SERVER"),
                         ("database", "MSSQL_DATABASE"),
                         ("user",     "MSSQL_USER"),
                         ("password", "MSSQL_PASSWORD")):
            if _cfg.get(_k) and not os.environ.get(_env):
                os.environ[_env] = _cfg[_k]
    except Exception:
        pass

_conn = None
_driver = None  # "pymssql" or "pyodbc" — set on successful connect


def _get_env(key: str) -> str:
    val = os.environ.get(key, "").strip()
    if not val:
        raise RuntimeError(
            f"Environment variable {key!r} is not set.\n"
            "  Set MSSQL_SERVER, MSSQL_DATABASE, MSSQL_USER, MSSQL_PASSWORD\n"
            "  in a .env file (local) or as Replit Secrets."
        )
    return val


def _parse_server(server: str) -> tuple[str, int]:
    """
    Parse a server string into (host_or_instance, port).

    Supported formats:
      192.168.1.10            -> ('192.168.1.10', 1433)
      192.168.1.10,1433       -> ('192.168.1.10', 1433)
      HOST\\INSTANCE           -> ('HOST\\INSTANCE', 1433)  pymssql resolves via SQL Browser
      HOST\\INSTANCE,1450      -> ('HOST\\INSTANCE', 1450)
    """
    if "," in server:
        parts = server.rsplit(",", 1)
        return parts[0].strip(), int(parts[1].strip())
    return server.strip(), 1433


def _make_pymssql():
    import pymssql  # type: ignore

    server_str = _get_env("MSSQL_SERVER")
    database = _get_env("MSSQL_DATABASE")
    user = _get_env("MSSQL_USER")
    password = _get_env("MSSQL_PASSWORD")

    host, port = _parse_server(server_str)

    return pymssql.connect(
        server=host,
        port=port,
        database=database,
        user=user,
        password=password,
        tds_version="7.4",
        charset="UTF-8",
        login_timeout=10,
    )


def _make_pyodbc():
    import pyodbc  # type: ignore

    server_str = _get_env("MSSQL_SERVER")
    database = _get_env("MSSQL_DATABASE")
    user = _get_env("MSSQL_USER")
    password = _get_env("MSSQL_PASSWORD")

    # Try common ODBC driver names in order
    drivers_to_try = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "SQL Server",
        "FreeTDS",
    ]
    available = [
        d for d in pyodbc.drivers() if any(x in d for x in ["SQL Server", "FreeTDS"])
    ]
    candidates = available if available else drivers_to_try

    last_err = None
    for driver in candidates:
        try:
            cs = (
                f"DRIVER={{{driver}}};"
                f"SERVER={server_str};"
                f"DATABASE={database};"
                f"UID={user};"
                f"PWD={password};"
                f"TDS_Version=7.4;"
                f"Encrypt=no;"
            )
            return pyodbc.connect(cs, timeout=10)
        except Exception as e:
            last_err = e
    raise last_err or RuntimeError("No suitable ODBC driver found")


def get_connection():
    global _conn, _driver
    if _conn is not None:
        try:
            cur = _conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return _conn
        except Exception:
            _conn = None
            _driver = None

    errors = []
    for factory in (_make_pymssql, _make_pyodbc):
        try:
            _conn = factory()
            _driver = factory.__name__.replace('_make_', '')
            print(f"  [db] Connected via {_driver}")
            return _conn
        except Exception as e:
            errors.append(f"  [{factory.__name__.replace('_make_', '')}] {e}")

    raise RuntimeError(
        "Cannot connect to SQL Server.\n"
        + "\n".join(errors)
        + "\n\nSee README_IMOS.md → Connection Troubleshooting."
    )


def query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    global _driver
    conn = get_connection()
    cur = conn.cursor()
    if _driver == "pymssql":
        sql = sql.replace("?", "%s")
    try:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        cur.close()


def scalar(sql: str, params: tuple = ()) -> Any:
    rows = query(sql, params)
    if not rows:
        return None
    return next(iter(rows[0].values()))


def discover_sql_servers(timeout: float = 2.0) -> list[str]:
    """
    Broadcast a SQL Server Browser discovery request (UDP port 1434) on
    the local network and parse responses into 'HOST\\INSTANCE' or
    'HOST' strings. Same mechanism SSMS uses for its server dropdown.
    """
    import socket

    found: dict[str, str] = {}
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    try:
        sock.sendto(b"\x02", ("255.255.255.255", 1434))
        end_time = __import__("time").time() + timeout
        while True:
            remaining = end_time - __import__("time").time()
            if remaining <= 0:
                break
            sock.settimeout(remaining)
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                break
            except OSError:
                break
            host = addr[0]
            text = data.decode(errors="ignore")
            for entry in text.split(";;"):
                server_name = None
                instance_name = None
                parts = entry.split(";")
                for i in range(0, len(parts) - 1, 2):
                    key = parts[i]
                    val = parts[i + 1] if i + 1 < len(parts) else ""
                    if key == "ServerName":
                        server_name = val
                    elif key == "InstanceName":
                        instance_name = val
                if server_name:
                    label = f"{server_name}\\{instance_name}" if instance_name and instance_name != "MSSQLSERVER" else server_name
                    found[label] = host
    finally:
        sock.close()
    return sorted(found.keys())


def list_databases(server: str, user: str, password: str) -> list[str]:
    """
    Connect to the given server's master database (without selecting a
    target database) and return all non-system database names.
    """
    host, port = _parse_server(server)
    names: list[str] = []
    last_err = None

    try:
        import pymssql  # type: ignore
        conn = pymssql.connect(
            server=host, port=port, database="master",
            user=user, password=password,
            tds_version="7.4", charset="UTF-8", login_timeout=10,
        )
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sys.databases "
            "WHERE database_id > 4 ORDER BY name"
        )
        names = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return names
    except Exception as e:
        last_err = e

    try:
        import pyodbc  # type: ignore
        available = [d for d in pyodbc.drivers() if any(x in d for x in ["SQL Server", "FreeTDS"])]
        candidates = available or ["ODBC Driver 18 for SQL Server", "ODBC Driver 17 for SQL Server", "SQL Server", "FreeTDS"]
        for driver in candidates:
            try:
                cs = (
                    f"DRIVER={{{driver}}};SERVER={server};DATABASE=master;"
                    f"UID={user};PWD={password};TDS_Version=7.4;Encrypt=no;"
                )
                conn = pyodbc.connect(cs, timeout=10)
                cur = conn.cursor()
                cur.execute("SELECT name FROM sys.databases WHERE database_id > 4 ORDER BY name")
                names = [row[0] for row in cur.fetchall()]
                cur.close()
                conn.close()
                return names
            except Exception as e:
                last_err = e
    except Exception as e:
        last_err = e

    raise RuntimeError(f"Could not list databases: {last_err}")


def normalize(v: Any) -> str | None:
    """Return None for NULL / empty / whitespace-only values."""
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None