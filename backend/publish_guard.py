"""Refuse demonstration data on any path that produces a published output (MASTER section 15).

`data/sample_cells.json` is a development fixture. Its `dataset_status` starts with
"demonstration_only" and its cells carry `source_status` "demo_not_source_derived".
Any loader that feeds the website, a page, or a deck calls `assert_publishable`.
"""

from __future__ import annotations

from typing import Any

DEMO_PREFIX = "demo"
RECORD_LISTS = ("cells", "stations", "series", "sites")


class UnpublishableInput(ValueError):
    """Raised when demonstration data would reach a published output."""


def _is_demo(value: Any) -> bool:
    return isinstance(value, str) and value.lower().startswith(DEMO_PREFIX)


def assert_publishable(payload: Any, source: str) -> None:
    if not isinstance(payload, dict):
        return
    for key in ("dataset_status", "source_status", "status"):
        if _is_demo(payload.get(key)):
            raise UnpublishableInput(f"{source}: {key} is {payload[key]!r}; demonstration data cannot reach a published output")
    for key in RECORD_LISTS:
        records = payload.get(key)
        if isinstance(records, list):
            for record in records:
                if isinstance(record, dict) and _is_demo(record.get("source_status")):
                    raise UnpublishableInput(f"{source}: a {key} record has source_status {record['source_status']!r}; demonstration data cannot reach a published output")
