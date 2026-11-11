"""Applied-correction contract for NISAR displacement artifacts (MASTER 4.4, 6.3.1).

Every NISAR pair artifact carries an ``applied_corrections`` record that states,
for the displacement values *in that artifact*, whether each correction has
been applied, and the evidence for that state:

- ``True``: applied (by the product or by TerraGauge). The source says which.
- ``False``: verified not applied. The source names the product metadata
  that shows it.
- ``None``: not verified. Nothing may be applied on top of an unknown state,
  because the product might already have applied it.

A correction can therefore be applied only once, and only after the product's
own state has been verified. ``source_processing_corrections`` (the raw product
flags) is kept separately. The flags recorded so far are geocoding flags, not
phase-correction evidence (audit A1).
"""

from __future__ import annotations

from typing import Any

CONTRACT = "terragauge-applied-corrections-v1"
CORRECTIONS = ("ionosphere", "troposphere", "tide")


def empty_correction_record() -> dict[str, Any]:
    record: dict[str, Any] = {"contract": CONTRACT}
    for name in CORRECTIONS:
        record[f"{name}_applied"] = None
        record[f"{name}_source"] = None
    return record


def _check_name(name: str) -> None:
    if name not in CORRECTIONS:
        raise ValueError(f"unknown correction {name!r}; expected one of {CORRECTIONS}")


def set_product_state(record: dict[str, Any], name: str, applied: bool, evidence: str) -> dict[str, Any]:
    """Record the verified state the product delivered, from its metadata."""
    _check_name(name)
    if not isinstance(applied, bool) or not evidence:
        raise ValueError("product state needs a boolean and the metadata evidence that shows it")
    if record.get(f"{name}_applied") is not None:
        raise ValueError(f"{name} state is already recorded as {record[f'{name}_applied']!r}; it cannot be overwritten")
    return {**record, f"{name}_applied": applied, f"{name}_source": evidence}


def mark_applied(record: dict[str, Any], name: str, source: str) -> dict[str, Any]:
    """Return a copy of the record with ``name`` applied by ``source``.

    Refuses a second application, and refuses to apply on top of an
    unverified state.
    """
    _check_name(name)
    state = record.get(f"{name}_applied")
    if state is True:
        raise ValueError(f"{name} correction is already applied ({record.get(f'{name}_source')}); refusing to apply it twice")
    if state is None:
        raise ValueError(f"{name} state is unverified; record the product state with set_product_state() before applying")
    if not source:
        raise ValueError("an applied correction needs a source")
    return {**record, f"{name}_applied": True, f"{name}_source": source}


def validate_correction_record(record: Any) -> list[str]:
    """Return findings; an empty list means the record satisfies the contract."""
    if not isinstance(record, dict):
        return ["applied_corrections record is missing"]
    findings = []
    if record.get("contract") != CONTRACT:
        findings.append(f"applied_corrections contract must be {CONTRACT}")
    for name in CORRECTIONS:
        if f"{name}_applied" not in record or f"{name}_source" not in record:
            findings.append(f"applied_corrections is missing {name}_applied or {name}_source")
            continue
        state, source = record[f"{name}_applied"], record[f"{name}_source"]
        if state is not None and not isinstance(state, bool):
            findings.append(f"{name}_applied must be true, false, or null")
        elif isinstance(state, bool) and not (isinstance(source, str) and source):
            findings.append(f"{name}_applied is {state} but {name}_source gives no evidence")
    return findings


def require_same_corrections(records: list[Any]) -> dict[str, Any]:
    """Pairs combined into one series must share one correction state."""
    for record in records:
        findings = validate_correction_record(record)
        if findings:
            raise ValueError("; ".join(findings))
    if any(record != records[0] for record in records[1:]):
        raise ValueError("pairs have different applied_corrections states and cannot be combined")
    return dict(records[0])
