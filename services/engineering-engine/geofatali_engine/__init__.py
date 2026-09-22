"""GeoFatali engineering engine.

A pure-Python, dependency-free, deterministic geotechnical calculation
library. It has no knowledge of HTTP, of databases, or of any AI vendor:
those live in the services that call it. That separation is deliberate and is
what makes every number it produces reproducible and testable.

Nothing here is a foundation design. Every result is preliminary until a
qualified engineer has reviewed it against measured ground data.
"""

from .record import CalculationRecord, Status
from .sectors import SECTORS, get_sector
from .standards import STANDARDS, get_standard
from .version import ENGINE_VERSION

__all__ = [
    "CalculationRecord",
    "Status",
    "SECTORS",
    "get_sector",
    "STANDARDS",
    "get_standard",
    "ENGINE_VERSION",
]
