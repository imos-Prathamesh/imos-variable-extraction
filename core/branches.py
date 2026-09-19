# Source : core/branches.py
# Analogy: Menu of database tables — lists every table to check, which columns to read, and where to go next.
"""
Typed branch definitions.
Each Branch describes exactly one table in the flow:
  match_table    – the table to query
  match_column   – the column that must equal the incoming value
  filter_column  – the INORDER / ORDERID column filtered to blank/NULL
  value_columns  – the columns whose values are extracted and classified
  next_state     – where the extracted values go after classification
  label          – human-readable name for logging
"""
from __future__ import annotations

from dataclasses import dataclass, field


STATE_CONISITU        = "CONISITU"
STATE_CONNECTIONS     = "CONNECTIONS"
STATE_CONNSELTREE     = "CONNSELTREE"
STATE_CONNDESC        = "CONNDESC"
STATE_CONNEXTRA       = "CONNEXTRA"
STATE_CONNGROUPS      = "CONNGROUPS"
STATE_WORKGROUP_PRF   = "WORKGROUP_PRF"
STATE_WORKGROUP_CONT  = "WORKGROUP_CONTOUR"
STATE_PROFIL          = "PROFIL"
STATE_PROFIL_GEOM     = "PROFIL_GEOM"
STATE_RENDER          = "RENDER"
STATE_CONTELEM        = "CONTELEM"
STATE_NUT_ERB         = "NUT_ERB"
STATE_EXTRUPAR        = "EXTRUPAR"
STATE_EXTRUCON        = "EXTRUCON"
STATE_IDENT           = "IDENT"
STATE_DESCRIPTOR      = "DESCRIPTOR"
STATE_IMOS            = "IMOS"
STATE_MAT             = "MAT"
STATE_SURF            = "SURF"
STATE_TERMINAL        = "TERMINAL"


@dataclass
class Branch:
    label: str
    match_table: str
    match_column: str
    filter_column: str        # INORDER or ORDERID; blank/NULL filter applied
    value_columns: list[str]
    next_state: str           # state after classification
    order_columns: list[str] = field(default_factory=list)  # ORDER BY hint


# ─────────────────────────────────────────────────────────────────────────────
# Branch registry
# ─────────────────────────────────────────────────────────────────────────────

BRANCHES: dict[str, Branch] = {

    STATE_CONNECTIONS: Branch(
        label="CONNECTIONS",
        match_table="CONNECTIONS",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=[
            "CONNDIRECT", "LINDIV", "LINDIV2", "ROTATION",
            "GROOVE", "POSPART0VAR", "POSPART1VAR", "SNAPRADI", "VARIANT",
        ],
        next_state=STATE_CONNECTIONS,
        order_columns=["CONNUM"],
    ),

    STATE_CONNSELTREE: Branch(
        label="CONNSELTREE",
        match_table="CONNSELTREE",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=["CHILDID"],
        next_state=STATE_CONNECTIONS,
        order_columns=["COMPONENT", "PARENTNUM", "CHILDNUM", "POSNUM"],
    ),

    STATE_CONNDESC: Branch(
        label="CONNDESC",
        match_table="CONNDESC",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=["ARTICLE_ID", "ORDER_ID", "SPRICE", "SCFACTOR", "SWEIGHT"],
        next_state=STATE_CONNECTIONS,
        order_columns=["ORDER_ID"],
    ),

    STATE_CONNEXTRA: Branch(
        label="CONNEXTRA",
        match_table="CONNEXTRA",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=["CONNVALUE"],
        next_state=STATE_CONNECTIONS,
        order_columns=["ATTRIBUTE"],
    ),

    STATE_CONNGROUPS: Branch(
        label="CONNGROUPS",
        match_table="CONNGROUPS",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=["CONNGROUP"],
        next_state=STATE_WORKGROUP_PRF,
        order_columns=["LFDNR"],
    ),

    STATE_WORKGROUP_PRF: Branch(
        label="WORKGROUP(PRF)",
        match_table="WORKGROUP",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=["PRF"],
        next_state=STATE_PROFIL,
        order_columns=["MACHINING_SEQ"],
    ),

    STATE_WORKGROUP_CONT: Branch(
        label="WORKGROUP(CONTOUR)",
        match_table="WORKGROUP",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=["CONTOUR"],
        next_state=STATE_CONTELEM,
        order_columns=["MACHINING_SEQ"],
    ),

    STATE_PROFIL: Branch(
        label="PROFIL",
        match_table="PROFIL",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=[
            "SPRFTHK", "SPRFDE", "SCOST", "SCFACTOR",
            "SCPLUSV", "SCPLUSSTAER", "PRFDESCR", "RENDER_PRZ",
        ],
        next_state=STATE_CONTELEM,
        order_columns=["THK"],
    ),

    STATE_PROFIL_GEOM: Branch(
        label="PROFIL→PRFDESCR→contelem",
        match_table="contelem",
        match_column="CNAME",
        filter_column="INORDER",
        value_columns=[
            "STARTANGLE", "ENDANGLE", "SSTARTANGL", "SENDANGLE",
            "SENDPOINTX", "SENDPOINTY", "SPOINT2X", "SPOINT2Y",
            "SLENDIA", "SLENRAD", "SFILLETRAD", "SWIDTH",
        ],
        next_state=STATE_TERMINAL,
        order_columns=["ID"],
    ),

    STATE_RENDER: Branch(
        label="RENDER",
        match_table="RENDER",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=["CODE1", "CODE2", "CODE3", "SCOST", "SCFACTOR"],
        next_state=STATE_TERMINAL,
        order_columns=[],
    ),

    STATE_CONTELEM: Branch(
        label="contelem",
        match_table="contelem",
        match_column="CNAME",
        filter_column="INORDER",
        value_columns=[
            "STARTANGLE", "ENDANGLE", "SSTARTANGL", "SENDANGLE",
            "SENDPOINTX", "SENDPOINTY", "SPOINT2X", "SPOINT2Y",
            "SLENDIA", "SLENRAD", "SFILLETRAD", "SWIDTH",
        ],
        next_state=STATE_TERMINAL,
        order_columns=["ID"],
    ),

    STATE_NUT_ERB: Branch(
        label="nut_erb",
        match_table="nut_erb",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=[
            "LIN_TEIL",
            "SFUGE_X", "SFUGE_Y", "SLANGUEBV", "SLANGUEBH",
            "SWGTYPE", "SMACHCLASS",
            "SGAP_X_LEFT", "SGAP_X_RIGHT",
            "MERGE_GROOVES_RADIUS",
            "PRFNAMEBO", "PRFNAMESE",
        ],
        next_state=STATE_TERMINAL,
        order_columns=[],
    ),

    STATE_MAT: Branch(
        label="MAT",
        match_table="MAT",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=[
            "RENDER_PRZ", "STHK", "STHK_ORD", "SCFACTOR",
            "SCOST", "SDWEIGHT", "OVERSIZEX", "OVERSIZEY",
        ],
        next_state=STATE_CONNECTIONS,
        order_columns=[],
    ),

    STATE_SURF: Branch(
        label="SURF",
        match_table="SURF",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=[
            "RENDER_PRZ", "OVERSIZEX", "OVERSIZEY", "SCFACTOR",
            "SCOST", "STHK", "STHK_ORD", "VPART_MAT",
        ],
        next_state=STATE_CONNECTIONS,
        order_columns=[],
    ),

    STATE_EXTRUPAR: Branch(
        label="extrupar",
        match_table="extrupar",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=[
            "SECTNAME", "CONT", "GROOVE", "GAP",
            "ORDERID", "ARTIKELNR", "RENDER", "INFOFOLDER",
            "SCFACTOR", "SLWEIGHT", "SAUFMASS",
            "SCOST", "SSIZEX", "SSIZEY", "SREFX", "SREFY", "SWALLSTREN",
            "TEXT", "TEXT2", "MAT", "SURF", "MATOR", "SURFOR",
        ],
        next_state=STATE_EXTRUCON,
        order_columns=["CHILDNUM"],
    ),

    STATE_EXTRUCON: Branch(
        label="extrucon",
        match_table="extrucon",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=[
            "CONNAME", "LINTEIL",
            "SDISTANCE", "SDISTANCEZ", "SROT", "SSNAPRAD",
        ],
        next_state=STATE_CONNECTIONS,   # CONNAME returns to CONNECTIONS
        order_columns=["CHILDNUM"],
    ),

    STATE_IDENT: Branch(
        label="ident",
        match_table="ident",
        match_column="NAME",
        filter_column="INORDER",
        value_columns=[
            "COMMENT", "NCNUMBER", "INFO1", "INFO2", "INFO3", "INFO4", "INFO5",
            "INFO6", "INFO7", "INFO8", "INFO9", "INFO10",
            "SERIALTEXT", "ARTICLE_ID",
        ],
        next_state=STATE_TERMINAL,
        order_columns=[],
    ),
}
