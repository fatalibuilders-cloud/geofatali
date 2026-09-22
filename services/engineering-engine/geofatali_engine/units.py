"""Units.

The engine works in SI throughout and converts only at the edges:

    length          m
    force           kN
    stress/pressure kPa
    unit weight     kN/m3
    angle           degrees (converted to radians inside formulas)
    settlement       mm (reported) / m (internal)

Mixing units is the single most common way an engineering calculation goes
quietly wrong, so every public dataclass field carries its unit in the name
(``width_m``, ``cohesion_kpa``) and nothing in the engine accepts a bare
number whose unit has to be inferred.
"""

from __future__ import annotations

# Unit weight of water, kN/m3. Used for every effective-stress and
# water-table correction in the engine.
GAMMA_WATER_KN_M3 = 9.81

# Acceleration due to gravity, m/s2 — for mass/force conversions only.
G_M_S2 = 9.81

M_PER_MM = 0.001
MM_PER_M = 1000.0
KPA_PER_MPA = 1000.0
KN_PER_TONNE_FORCE = 9.81


def mm_to_m(value_mm: float) -> float:
    return value_mm * M_PER_MM


def m_to_mm(value_m: float) -> float:
    return value_m * MM_PER_M


def mpa_to_kpa(value_mpa: float) -> float:
    return value_mpa * KPA_PER_MPA


def kpa_to_mpa(value_kpa: float) -> float:
    return value_kpa / KPA_PER_MPA


def kgf_cm2_to_kpa(value: float) -> float:
    """kg/cm2 still appears on older Kenyan and Indian lab sheets."""
    return value * 98.0665
