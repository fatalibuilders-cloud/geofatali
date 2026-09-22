"""Where a number came from.

Spec rule: *never allow a calculated value to masquerade as a measured value*.

Every geotechnical quantity that enters a calculation carries a ``Source``.
The bearing-capacity engine does not care whether a friction angle was
measured in a triaxial cell or guessed from a photograph — but the engineer
reading the report very much does, and so does the warning system, which
downgrades the confidence of any result that leans on AI or ESTIMATED input.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Source(str, Enum):
    """How a value was obtained, strongest evidence first."""

    LABORATORY = "LABORATORY"   # measured in a laboratory to a named standard
    FIELD = "FIELD"             # measured on site (SPT, CPT, DCP, plate test)
    ENGINEER = "ENGINEER"       # set by a qualified engineer's judgement
    IMPORTED = "IMPORTED"       # brought in from another dataset or report
    USER = "USER"               # typed in by a non-engineer user
    AI = "AI"                   # produced by visual classification
    ESTIMATED = "ESTIMATED"     # derived by the engine from an empirical rule


#: Sources that count as measured evidence. Anything outside this set makes a
#: result preliminary no matter how tidy the arithmetic is.
MEASURED_SOURCES = frozenset({Source.LABORATORY, Source.FIELD})

#: Ranking used when two records disagree about the same quantity.
_RANK = {
    Source.LABORATORY: 6,
    Source.FIELD: 5,
    Source.ENGINEER: 4,
    Source.IMPORTED: 3,
    Source.USER: 2,
    Source.ESTIMATED: 1,
    Source.AI: 0,
}


@dataclass(frozen=True)
class Measurement:
    """A number that knows where it came from.

    ``value`` is always in the engine's SI unit for that quantity; ``unit`` is
    carried so the report can print it without the renderer having to know the
    convention.
    """

    value: float
    unit: str
    source: Source
    #: Test/record identifier, e.g. "BH-01/SPT-3" or "LAB-2026-0412".
    reference: str | None = None
    #: The standard the measurement was taken to, e.g. "BS 1377-9".
    standard: str | None = None
    note: str | None = None

    @property
    def is_measured(self) -> bool:
        return self.source in MEASURED_SOURCES

    def as_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "unit": self.unit,
            "source": self.source.value,
            "reference": self.reference,
            "standard": self.standard,
            "note": self.note,
        }


def strongest(*measurements: Measurement | None) -> Measurement | None:
    """Pick the best-evidenced of several values for the same quantity."""
    present = [m for m in measurements if m is not None]
    if not present:
        return None
    return max(present, key=lambda m: _RANK[m.source])


@dataclass
class ProvenanceLedger:
    """Every input a calculation actually used, by name.

    Stored with the result so a report can state, line by line, which figures
    were measured and which were assumed — that table is the difference
    between an engineering document and a printout.
    """

    entries: dict[str, Measurement] = field(default_factory=dict)

    def record(self, name: str, measurement: Measurement) -> Measurement:
        self.entries[name] = measurement
        return measurement

    @property
    def weakest_source(self) -> Source | None:
        if not self.entries:
            return None
        return min(self.entries.values(), key=lambda m: _RANK[m.source]).source

    @property
    def fully_measured(self) -> bool:
        return bool(self.entries) and all(m.is_measured for m in self.entries.values())

    def unmeasured(self) -> dict[str, Measurement]:
        return {k: v for k, v in self.entries.items() if not v.is_measured}

    def as_dict(self) -> dict[str, Any]:
        return {name: m.as_dict() for name, m in self.entries.items()}
