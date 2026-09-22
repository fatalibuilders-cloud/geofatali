"""The engineering warning system.

Spec sections 39-40. Three severities, and they mean different things:

    INFO      worth knowing; the result stands.
    WARNING   the result stands but more data would materially improve it.
    CRITICAL  the result must not be relied on as it is.

The rule this module exists to enforce is that a missing input never becomes
a silent assumption. Where a value is required and absent, the calculation
returns ``status = INSUFFICIENT_DATA`` with a CRITICAL warning naming the
exact field, instead of substituting a plausible number and carrying on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


_ORDER = {Severity.INFO: 0, Severity.WARNING: 1, Severity.CRITICAL: 2}


@dataclass(frozen=True)
class EngineeringWarning:
    severity: Severity
    #: Stable machine code, e.g. "MISSING_UNIT_WEIGHT". Never localise this.
    code: str
    message: str
    #: The input field this is about, where there is one.
    field_name: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity.value,
            "code": self.code,
            "message": self.message,
            "field": self.field_name,
        }


@dataclass
class WarningList:
    items: list[EngineeringWarning] = field(default_factory=list)

    def info(self, code: str, message: str, field_name: str | None = None) -> None:
        self.items.append(EngineeringWarning(Severity.INFO, code, message, field_name))

    def warn(self, code: str, message: str, field_name: str | None = None) -> None:
        self.items.append(EngineeringWarning(Severity.WARNING, code, message, field_name))

    def critical(self, code: str, message: str, field_name: str | None = None) -> None:
        self.items.append(EngineeringWarning(Severity.CRITICAL, code, message, field_name))

    def extend(self, other: "WarningList | list[EngineeringWarning]") -> None:
        self.items.extend(other.items if isinstance(other, WarningList) else other)

    @property
    def has_critical(self) -> bool:
        return any(w.severity is Severity.CRITICAL for w in self.items)

    @property
    def worst(self) -> Severity | None:
        if not self.items:
            return None
        return max((w.severity for w in self.items), key=lambda s: _ORDER[s])

    def codes(self) -> list[str]:
        return [w.code for w in self.items]

    def as_list(self) -> list[dict[str, Any]]:
        return [w.as_dict() for w in self.items]

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.items)

    def __iter__(self):  # pragma: no cover - trivial
        return iter(self.items)


class InvalidInput(ValueError):
    """Raised for input that is not merely missing but impossible.

    A friction angle of 120 degrees or a negative footing width is not a data
    gap to warn about — it is wrong, and the caller must fix it. Missing data
    produces a warning; nonsense produces this.
    """

    def __init__(self, field_name: str, message: str) -> None:
        super().__init__(f"{field_name}: {message}")
        self.field_name = field_name
        self.message = message


def require_positive(field_name: str, value: float | None) -> float:
    if value is None:
        raise InvalidInput(field_name, "is required")
    if value <= 0:
        raise InvalidInput(field_name, f"must be greater than zero (got {value})")
    return float(value)


def require_non_negative(field_name: str, value: float | None) -> float:
    if value is None:
        raise InvalidInput(field_name, "is required")
    if value < 0:
        raise InvalidInput(field_name, f"cannot be negative (got {value})")
    return float(value)


def require_friction_angle(field_name: str, value: float | None) -> float:
    if value is None:
        raise InvalidInput(field_name, "is required")
    if value < 0:
        raise InvalidInput(field_name, f"cannot be negative (got {value})")
    if value >= 60:
        raise InvalidInput(
            field_name,
            f"of {value} deg is outside the range any soil reaches; check the units and the test",
        )
    return float(value)
