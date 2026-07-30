"""
$variable and #descriptor token parser.

Rules (confirmed from uploaded test cases and diagram):
- Scan the ENTIRE string for tokens; do not require the string to start with $ or #.
- A $ token starts at $ and ends before the next whitespace, comma, colon, ),
  +, -, *, /, (, or end-of-string.
- A # token starts at # and ends before whitespace or end-of-string.
- A string may contain both $ and # tokens simultaneously.
- Preserve the original string and token order.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


_DOLLAR_RE = re.compile(r'\$([A-Za-z_][A-Za-z0-9_]*)')
_HASH_RE   = re.compile(r'#([A-Za-z_][A-Za-z0-9_]*)')


@dataclass
class ParsedValue:
    original: str
    variables: list[str] = field(default_factory=list)   # names without $
    descriptors: list[str] = field(default_factory=list)  # names without #

    @property
    def has_variable(self) -> bool:
        return bool(self.variables)

    @property
    def has_descriptor(self) -> bool:
        return bool(self.descriptors)

    @property
    def is_raw(self) -> bool:
        """True if the value contains no $ or # tokens at all."""
        return not self.variables and not self.descriptors

    @property
    def is_blank(self) -> bool:
        return not self.original.strip()


def parse(value: str | None) -> ParsedValue | None:
    """
    Parse a single value string.
    Returns None if the value is None or blank.
    """
    if value is None:
        return None
    s = value.strip()
    if not s:
        return None
    variables   = _DOLLAR_RE.findall(s)
    descriptors = _HASH_RE.findall(s)
    return ParsedValue(original=s, variables=variables, descriptors=descriptors)


def parse_multi(value: str | None) -> list[ParsedValue]:
    """
    Some value fields (e.g. descriptor LINDIV like '27mm:128mm:1') contain
    colon-separated sub-values.  Parse each sub-value individually and
    collect non-blank results.
    """
    if value is None:
        return []
    parts = value.split(":")
    out = []
    for p in parts:
        pv = parse(p.strip())
        if pv is not None:
            out.append(pv)
    return out