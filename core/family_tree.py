# Source : core/family_tree.py
# Analogy: Builds a Family/Variable tree from IMOS, scoped ONLY to variables
# already present in the last extraction results — not the whole IMOS table.
from __future__ import annotations

from core.db import query, normalize

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


def _fetch_imos_rows(names: list[str]) -> dict[str, dict]:
    if not names:
        return {}
    ph = ",".join(["?"] * len(names))
    rows = query(
        f"SELECT NAME, TYP, WERT, CATEGORY, OPTINFO, FAMILY FROM dbo.IMOS "
        f"WHERE NAME IN ({ph}) AND NULLIF(LTRIM(RTRIM(ORDERID)), N'') IS NULL",
        tuple(names),
    )
    out: dict[str, dict] = {}
    for r in rows:
        name = normalize(r.get("NAME"))
        if name:
            out[name] = r
    return out


def build_family_tree(variable_names: list[str]) -> list[dict]:
    """
    variable_names: distinct variable names already found in Results.
    Walks each one's FAMILY chain upward and returns a list of root
    node dicts: {id, label, node_type, value, category, comment, family, children}
    """
    nodes: dict[str, dict] = {}
    fetched: set[str] = set()
    pending = {n for n in variable_names if n}

    while pending:
        batch = [n for n in pending if n not in fetched]
        if not batch:
            break
        rows = _fetch_imos_rows(batch)
        for n in batch:
            fetched.add(n)
        for name, r in rows.items():
            typ = str(r.get("TYP") or "").strip()
            family = normalize(r.get("FAMILY")) or ""
            nodes[name] = {
                "id": name,
                "label": name,
                "node_type": TYP_LABELS.get(typ, typ or "—"),
                "value": normalize(r.get("WERT")) or "",
                "category": normalize(r.get("CATEGORY")) or "",
                "comment": normalize(r.get("OPTINFO")) or "",
                "family": family,
                "children": [],
            }
            if family and family not in nodes:
                pending.add(family)
        pending -= fetched

    for n in variable_names:
        if n and n not in nodes:
            nodes[n] = {
                "id": n, "label": n, "node_type": "—", "value": "[NOT IN IMOS]",
                "category": "", "comment": "", "family": "", "children": [],
            }

    roots: list[dict] = []
    for name, node in nodes.items():
        fam = node["family"]
        if fam and fam in nodes:
            nodes[fam]["children"].append(node)
        else:
            roots.append(node)

    def _sort(n: dict) -> None:
        n["children"].sort(key=lambda c: c["label"])
        for c in n["children"]:
            _sort(c)

    for r in roots:
        _sort(r)
    roots.sort(key=lambda r: r["label"])
    return roots