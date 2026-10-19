"""Strict structured result schema for the vendor desk agent."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class VendorAssessment(BaseModel):
    """Extracted quote facts and a handbook-based recommendation."""

    model_config = ConfigDict(extra="forbid", strict=True)

    vendor: str | None = Field(description="Vendor name stated in the document, or null if absent/unclear.")
    sku: str | None = Field(description="Campus Customs SKU stated in the document, or null if absent/unclear.")
    unit_price: Decimal | None = Field(description="Quoted per-unit price as a decimal amount, or null if absent/unclear.")
    lead_time_days: int | None = Field(description="Lead time in days when stated unambiguously, otherwise null.")
    minimum_order_units: int | None = Field(description="Minimum order quantity in units, or null if absent/unclear.")
    decision: Literal["recommend", "do_not_recommend"] = Field(
        description="Recommend only if all handbook approval, price, lead-time, and minimum-order checks pass."
    )
    reason: str = Field(min_length=1, description="Concise reason naming the handbook check that determines the decision.")


class FieldEvidence(BaseModel):
    """Verbatim evidence for one extracted field from visible document text."""

    model_config = ConfigDict(extra="forbid", strict=True)

    field: Literal["vendor", "sku", "unit_price", "lead_time_days", "minimum_order_units"]
    quote: str = Field(min_length=1, max_length=600)


class VendorFactExtraction(BaseModel):
    """Facts only: deliberately has no decision field and no tool surface."""

    model_config = ConfigDict(extra="forbid", strict=True)

    vendor: str | None
    sku: str | None
    unit_price: Decimal | None
    lead_time_days: int | None
    minimum_order_units: int | None
    evidence: list[FieldEvidence] = Field(default_factory=list)
    uncertain_fields: list[Literal["vendor", "sku", "unit_price", "lead_time_days", "minimum_order_units"]] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
