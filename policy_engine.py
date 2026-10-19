"""Deterministic purchasing rules loaded from the authoritative handbook."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from models import VendorAssessment


@dataclass(frozen=True)
class HandbookPolicy:
    approved_vendors: frozenset[str]
    removed_vendors: frozenset[str]
    sku_max_cost: dict[str, Decimal]
    max_lead_time_days: int = 21
    max_minimum_order: int = 600


def _table_lines(text: str, start_heading: str, end_heading: str | None) -> list[list[str]]:
    start = text.index(start_heading)
    end = text.index(end_heading, start) if end_heading else len(text)
    result: list[list[str]] = []
    for line in text[start:end].splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [part.strip() for part in line.strip().strip("|").split("|")]
        if cells and not all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            result.append(cells)
    return result


def load_handbook_policy(path: Path) -> HandbookPolicy:
    text = path.read_text(encoding="utf-8")
    approved_rows = _table_lines(text, "## 5. Approved vendors", "## 6.")
    approved = {row[1] for row in approved_rows[1:] if len(row) >= 2 and row[0]}
    removed_rows = _table_lines(text, "## 6. Removed and pending vendors", "## 7.")
    removed = {row[0] for row in removed_rows[1:] if len(row) >= 2 and row[0]}
    sku_costs: dict[str, Decimal] = {}
    for row in _table_lines(text, "## 9. Product catalogue", None)[1:]:
        if len(row) < 5 or not row[0].startswith("CC-"):
            continue
        price = re.search(r"\$([0-9]+(?:\.[0-9]{1,2})?)", row[4])
        if not price:
            raise ValueError(f"Could not parse max unit cost for {row[0]} from the handbook.")
        sku_costs[row[0].upper()] = Decimal(price.group(1))
    if not approved or not removed or not sku_costs:
        raise ValueError("Handbook tables did not yield a complete approved/removed/catalogue policy.")
    return HandbookPolicy(frozenset(approved), frozenset(removed), sku_costs)


def make_assessment(
    *,
    vendor: str | None,
    sku: str | None,
    unit_price: Decimal | None,
    lead_time_days: int | None,
    minimum_order_units: int | None,
    policy: HandbookPolicy,
    uncertain_fields: set[str] | None = None,
) -> VendorAssessment:
    uncertain = uncertain_fields or set()
    facts: dict[str, object] = {
        "vendor": vendor,
        "sku": sku,
        "unit_price": unit_price,
        "lead_time_days": lead_time_days,
        "minimum_order_units": minimum_order_units,
    }
    failures: list[str] = []
    for field, value in facts.items():
        if value is None or field in uncertain:
            failures.append(f"{field.replace('_', ' ')} is unknown or uncertain")

    approved_names = {name.casefold(): name for name in policy.approved_vendors}
    removed_names = {name.casefold() for name in policy.removed_vendors}
    matched_vendor = approved_names.get((vendor or "").strip().casefold())
    if (vendor or "").strip().casefold() in removed_names:
        failures.append(f"{vendor} is on the handbook's removed/pending list")
    elif matched_vendor is None and vendor is not None:
        failures.append(f"{vendor} is not on the handbook's approved-vendor list")

    maximum = policy.sku_max_cost.get((sku or "").strip().upper())
    if sku is not None and maximum is None:
        failures.append(f"SKU {sku} is not in the handbook catalogue")
    elif maximum is not None and unit_price is not None and unit_price > maximum:
        failures.append(f"unit price ${unit_price:.2f} exceeds the {sku} maximum ${maximum:.2f}")
    if lead_time_days is not None and lead_time_days > policy.max_lead_time_days:
        failures.append(f"lead time {lead_time_days} days exceeds {policy.max_lead_time_days} days")
    if minimum_order_units is not None and minimum_order_units > policy.max_minimum_order:
        failures.append(f"minimum order {minimum_order_units} exceeds {policy.max_minimum_order} units")

    if failures:
        decision = "do_not_recommend"
        reason = "Fails or cannot verify handbook checks: " + "; ".join(failures) + "."
    else:
        decision = "recommend"
        reason = (
            f"{matched_vendor} is approved; {sku} price ${unit_price:.2f} is within the ${maximum:.2f} maximum, "
            f"lead time {lead_time_days} days is within {policy.max_lead_time_days}, "
            f"and minimum order {minimum_order_units} is within {policy.max_minimum_order}."
        )
    return VendorAssessment(
        vendor=vendor,
        sku=sku,
        unit_price=unit_price,
        lead_time_days=lead_time_days,
        minimum_order_units=minimum_order_units,
        decision=decision,
        reason=reason,
    )
