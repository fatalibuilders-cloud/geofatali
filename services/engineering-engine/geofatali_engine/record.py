"""The calculation record.

Spec sections 24, 36 and rule 3: *every calculation must be reproducible from
stored inputs*, and *every result must identify its calculation method*.

So no calculation in this engine returns a bare number. Each returns a
``CalculationRecord`` carrying the inputs it actually used, the method, the
standard configuration, the engine version, the warnings raised, and the
provenance of every parameter. Persist this object and the calculation can be
re-run years later and checked line by line.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from .provenance import Measurement, ProvenanceLedger, Source
from .standards import METHOD_REFERENCES, Standard
from .version import ENGINE_VERSION
from .warnings import EngineeringWarning, Severity, WarningList


class Status(str, Enum):
    CALCULATED = "CALCULATED"
    #: A required input was absent. No number is returned — spec rule 7.
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    #: The method exists in the roadmap but is not implemented. Spec rule:
    #: return this rather than inventing a result.
    NOT_IMPLEMENTED = "CALCULATION_NOT_IMPLEMENTED"


@dataclass
class CalculationRecord:
    calculation_type: str
    method: str
    status: Status
    inputs: dict[str, Any] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    warnings: WarningList = field(default_factory=WarningList)
    provenance: ProvenanceLedger = field(default_factory=ProvenanceLedger)
    standard_id: str | None = None
    standard_edition: str | None = None
    engine_version: str = ENGINE_VERSION
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def reference(self) -> str | None:
        ref = METHOD_REFERENCES.get(self.method)
        return ref.citation if ref else None

    @property
    def is_preliminary(self) -> bool:
        """True unless every parameter used was measured and nothing is critical.

        A GeoFatali result is preliminary by default. It stops being
        preliminary only when the inputs are measured AND an engineer has
        signed the review — and the review lives outside the engine, so the
        engine never reports anything as final.
        """
        return not self.provenance.fully_measured or self.warnings.has_critical

    def as_dict(self) -> dict[str, Any]:
        return {
            "calculation_type": self.calculation_type,
            "method": self.method,
            "reference": self.reference,
            "status": self.status.value,
            "standard": self.standard_id,
            "standard_edition": self.standard_edition,
            "engine_version": self.engine_version,
            "created_at": self.created_at,
            "inputs": self.inputs,
            "results": self.results,
            "warnings": self.warnings.as_list(),
            "provenance": self.provenance.as_dict(),
            "preliminary": self.is_preliminary,
        }


    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "CalculationRecord":
        """Rebuild a record from its stored form.

        The promise that a calculation is reproducible from stored inputs is
        only real if the stored form can be read back. This is the inverse of
        ``as_dict``: persistence layers round-trip through it, and the report
        builder works on rehydrated records exactly as it does on fresh ones.
        """
        warnings = WarningList()
        for item in payload.get("warnings") or []:
            warnings.items.append(
                EngineeringWarning(
                    severity=Severity(item["severity"]),
                    code=item["code"],
                    message=item["message"],
                    field_name=item.get("field"),
                )
            )
        ledger = ProvenanceLedger()
        for name, entry in (payload.get("provenance") or {}).items():
            ledger.entries[name] = Measurement(
                value=entry["value"],
                unit=entry["unit"],
                source=Source(entry["source"]),
                reference=entry.get("reference"),
                standard=entry.get("standard"),
                note=entry.get("note"),
            )
        return cls(
            calculation_type=payload["calculation_type"],
            method=payload["method"],
            status=Status(payload["status"]),
            inputs=payload.get("inputs") or {},
            results=payload.get("results") or {},
            warnings=warnings,
            provenance=ledger,
            standard_id=payload.get("standard"),
            standard_edition=payload.get("standard_edition"),
            engine_version=payload.get("engine_version", ENGINE_VERSION),
            created_at=payload.get("created_at")
            or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )


def insufficient_data(
    calculation_type: str,
    method: str,
    missing: dict[str, str],
    *,
    standard: Standard | None = None,
    inputs: dict[str, Any] | None = None,
) -> CalculationRecord:
    """Build the refusal every calculation returns when a required input is absent.

    ``missing`` maps a field name to why it is needed. Naming the reason is
    the whole point: "INSUFFICIENT DATA" on its own sends a site technician
    back to the office without knowing what to go and measure.
    """
    w = WarningList()
    for field_name, why in missing.items():
        w.critical(
            "MISSING_REQUIRED_INPUT",
            f"{field_name} is required and was not supplied. {why}",
            field_name,
        )
    return CalculationRecord(
        calculation_type=calculation_type,
        method=method,
        status=Status.INSUFFICIENT_DATA,
        inputs=inputs or {},
        results={},
        warnings=w,
        standard_id=standard.id if standard else None,
        standard_edition=standard.edition if standard else None,
    )
