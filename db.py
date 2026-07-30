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

# Load .env file if present (local dev convenience)
try:
    from dotenv import load_dotenv

    _env_file = Path(__file__).parent / ".env"
    if _env_file.exists():
        load_dotenv(_env_file)
        print(f"  [db] Loaded .env from {_env_file}")
except ImportError:
    pass

_conn = None


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
    global _conn
    if _conn is not None:
        try:
            cur = _conn.cursor()
            cur.execute("SELECT 1")
            cur.close()
            return _conn
        except Exception:
            _conn = None

    errors = []
    for factory in (_make_pymssql, _make_pyodbc):
        try:
            _conn = factory()
            print(f"  [db] Connected via {factory.__name__.replace('_make_', '')}")
            return _conn
        except Exception as e:
            errors.append(f"  [{factory.__name__.replace('_make_', '')}] {e}")

    raise RuntimeError(
        "Cannot connect to SQL Server.\n"
        + "\n".join(errors)
        + "\n\nSee README_IMOS.md → Connection Troubleshooting."
    )


def query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    conn = get_connection()
    cur = conn.cursor()
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


def normalize(v: Any) -> str | None:
    """Return None for NULL / empty / whitespace-only values."""
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None