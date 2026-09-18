# Source : core/flow_registry.py
# Analogy: Automatic staff directory — scans flows/ and lists every flow that
# follows the contract (FLOW_NAME + extract()). Add a file, it shows up here.
"""
Central flow registry — auto-discovers all flow modules in flows/ package.

Each flow module must expose:
    FLOW_NAME : str
    extract(article: str, max_depth: int = 40) -> ExtractionResult

Optional:
    extract_all(max_depth: int = 40) -> list[ExtractionResult]

Adding a new flow = add one file to flows/ with FLOW_NAME + extract().
No other file needs to be edited.
"""
from __future__ import annotations

import importlib
import pkgutil
from typing import Callable, NamedTuple

import flows


class FlowInfo(NamedTuple):
    name: str
    extract: Callable
    extract_all: Callable | None


_REGISTRY: dict[str, FlowInfo] | None = None


def _discover() -> dict[str, FlowInfo]:
    registry: dict[str, FlowInfo] = {}
    for _, modname, _ in pkgutil.iter_modules(flows.__path__, flows.__name__ + "."):
        try:
            mod = importlib.import_module(modname)
        except Exception as e:
            print(f"  [flow_registry] skipped {modname}: {e}")
            continue
        flow_name = getattr(mod, "FLOW_NAME", None)
        extract_fn = getattr(mod, "extract", None)
        if not flow_name or not callable(extract_fn):
            continue
        if flow_name in registry:
            raise ValueError(f"Duplicate FLOW_NAME '{flow_name}' in {modname}")
        registry[flow_name] = FlowInfo(
            flow_name, extract_fn, getattr(mod, "extract_all", None)
        )
    return registry


def get_registry() -> dict[str, FlowInfo]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = _discover()
    return _REGISTRY


def flow_names() -> list[str]:
    return sorted(get_registry().keys())


def get_flow(name: str) -> FlowInfo | None:
    return get_registry().get(name)


def reset_registry() -> None:
    """Force re-discovery (e.g. after adding a flow file at runtime)."""
    global _REGISTRY
    _REGISTRY = None