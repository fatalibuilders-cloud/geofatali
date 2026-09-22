"""Bearing capacity factors and correction factors.

Four methods are implemented, each complete and each kept apart from the
others. Spec section 22 is explicit about this: *do NOT mix formulas from
different standards without explicit method selection*. Mixing Vesic's
N-gamma with Meyerhof's shape factors produces a number that looks like
engineering and is not traceable to anything, so the method is chosen once
and every factor in the calculation then comes from that method's own author.

Common to all four:

    Nq = e^(pi tan phi) tan^2(45 + phi/2)          (Reissner, 1924)
    Nc = (Nq - 1) / tan phi                        (Prandtl, 1921)

They differ in N-gamma, which has no closed-form solution:

    Terzaghi   N_gamma ~ 1.8 (Nq - 1) tan phi      (Bowles' fit to Terzaghi's chart)
    Meyerhof   N_gamma = (Nq - 1) tan(1.4 phi)
    Hansen     N_gamma = 1.5 (Nq - 1) tan phi
    Vesic      N_gamma = 2 (Nq + 1) tan phi

Vesic is the largest and Hansen the most conservative; on a wide footing in
sand the choice moves the answer by a third, which is exactly why the method
is recorded in the result.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..warnings import InvalidInput

METHODS = ("terzaghi", "meyerhof", "hansen", "vesic")

#: Nc at phi = 0. Prandtl's value, 2 + pi, is used by everyone except
#: Terzaghi, whose chart gives 5.7.
NC_PHI_ZERO = 5.14
NC_PHI_ZERO_TERZAGHI = 5.7


@dataclass(frozen=True)
class BearingFactors:
    nc: float
    nq: float
    n_gamma: float
    method: str

    def as_dict(self) -> dict[str, float | str]:
        return {
            "Nc": round(self.nc, 2),
            "Nq": round(self.nq, 2),
            "Ngamma": round(self.n_gamma, 2),
            "method": self.method,
        }


def _nq(phi_rad: float) -> float:
    return math.exp(math.pi * math.tan(phi_rad)) * math.tan(math.pi / 4 + phi_rad / 2) ** 2


def bearing_factors(phi_deg: float, method: str = "vesic") -> BearingFactors:
    """Nc, Nq and N-gamma for a friction angle, by the named method."""
    if method not in METHODS:
        raise InvalidInput("method", f"must be one of {list(METHODS)} (got {method!r})")
    if phi_deg < 0:
        raise InvalidInput("friction_angle_deg", f"cannot be negative (got {phi_deg})")
    if phi_deg >= 60:
        raise InvalidInput(
            "friction_angle_deg",
            f"of {phi_deg} deg exceeds anything a soil reaches; check units and test data",
        )

    phi = math.radians(phi_deg)

    # phi = 0 is the undrained clay case and is handled as a limit, not by
    # dividing by tan(0).
    if phi_deg < 1e-9:
        nc = NC_PHI_ZERO_TERZAGHI if method == "terzaghi" else NC_PHI_ZERO
        return BearingFactors(nc, 1.0, 0.0, method)

    nq = _nq(phi)
    nc = (nq - 1.0) / math.tan(phi)

    if method == "terzaghi":
        n_gamma = 1.8 * (nq - 1.0) * math.tan(phi)
    elif method == "meyerhof":
        n_gamma = (nq - 1.0) * math.tan(1.4 * phi)
    elif method == "hansen":
        n_gamma = 1.5 * (nq - 1.0) * math.tan(phi)
    else:  # vesic
        n_gamma = 2.0 * (nq + 1.0) * math.tan(phi)

    return BearingFactors(nc, nq, n_gamma, method)


@dataclass(frozen=True)
class CorrectionFactors:
    """Shape, depth, load inclination, ground slope and base tilt factors."""

    sc: float = 1.0
    sq: float = 1.0
    s_gamma: float = 1.0
    dc: float = 1.0
    dq: float = 1.0
    d_gamma: float = 1.0
    ic: float = 1.0
    iq: float = 1.0
    i_gamma: float = 1.0
    gc: float = 1.0
    gq: float = 1.0
    g_gamma: float = 1.0
    bc: float = 1.0
    bq: float = 1.0
    b_gamma: float = 1.0

    def as_dict(self) -> dict[str, float]:
        return {k: round(v, 3) for k, v in self.__dict__.items()}


# ───────────────────────────── Terzaghi ─────────────────────────────

#: Terzaghi does not use correction factors. He uses different coefficients on
#: the cohesion and self-weight terms for each footing shape, which is a
#: different thing and is applied in ``capacity.py``.
TERZAGHI_SHAPE_COEFFICIENTS = {
    "strip": (1.0, 0.5),
    "square": (1.3, 0.4),
    "circular": (1.3, 0.3),
    "rectangular": (None, None),  # interpolated from B/L in capacity.py
}


# ───────────────────────────── Meyerhof ─────────────────────────────

def meyerhof_factors(
    *, phi_deg: float, b_over_l: float, d_over_b: float, load_inclination_deg: float
) -> CorrectionFactors:
    """Meyerhof (1963) shape, depth and inclination factors."""
    phi = math.radians(phi_deg)
    kp = math.tan(math.pi / 4 + phi / 2) ** 2

    sc = 1.0 + 0.2 * kp * b_over_l
    if phi_deg >= 10:
        sq = s_gamma = 1.0 + 0.1 * kp * b_over_l
    else:
        sq = s_gamma = 1.0

    dc = 1.0 + 0.2 * math.sqrt(kp) * d_over_b
    if phi_deg >= 10:
        dq = d_gamma = 1.0 + 0.1 * math.sqrt(kp) * d_over_b
    else:
        dq = d_gamma = 1.0

    alpha = load_inclination_deg
    ic = iq = (1.0 - alpha / 90.0) ** 2
    if phi_deg > 0:
        i_gamma = max((1.0 - alpha / phi_deg), 0.0) ** 2
    else:
        i_gamma = 0.0 if alpha > 0 else 1.0

    return CorrectionFactors(
        sc=sc, sq=sq, s_gamma=s_gamma, dc=dc, dq=dq, d_gamma=d_gamma,
        ic=ic, iq=iq, i_gamma=i_gamma,
    )


# ────────────────────── Hansen and Vesic (shared form) ──────────────────────

def _depth_k(d_over_b: float) -> float:
    """k = D/B for shallow footings, arctan(D/B) in radians beyond D/B = 1.

    Past one width of embedment the linear form over-credits the soil above
    the base, so Hansen switches to the arctangent.
    """
    return d_over_b if d_over_b <= 1.0 else math.atan(d_over_b)


def hansen_vesic_factors(
    *,
    phi_deg: float,
    nq: float,
    nc: float,
    b_over_l: float,
    d_over_b: float,
    load_inclination_deg: float = 0.0,
    ground_slope_deg: float = 0.0,
    base_tilt_deg: float = 0.0,
    method: str = "hansen",
) -> CorrectionFactors:
    """Hansen (1970) / Vesic (1973) correction factors.

    The two authors share the shape and depth forms. They are given together
    here because they are the same equations in both papers; N-gamma, which is
    where they genuinely differ, is handled in ``bearing_factors``.
    """
    phi = math.radians(phi_deg)
    tan_phi = math.tan(phi)

    sc = 1.0 + (nq / nc) * b_over_l if nc > 0 else 1.0
    sq = 1.0 + b_over_l * tan_phi
    s_gamma = max(1.0 - 0.4 * b_over_l, 0.6)

    k = _depth_k(d_over_b)
    dc = 1.0 + 0.4 * k
    dq = 1.0 + 2.0 * tan_phi * (1.0 - math.sin(phi)) ** 2 * k
    d_gamma = 1.0

    # Load inclination. Hansen's exponent form is used for both; the exact
    # Vesic m-factor needs the loading direction relative to L, which the MVP
    # does not collect, so the simpler conservative form is used and said so.
    alpha = load_inclination_deg
    if alpha <= 0:
        ic = iq = i_gamma = 1.0
    else:
        iq = max((1.0 - alpha / 90.0), 0.0) ** 2
        ic = iq - (1.0 - iq) / (nq - 1.0) if nq > 1.0 else iq
        i_gamma = max((1.0 - alpha / max(phi_deg, 1e-9)), 0.0) ** 2 if phi_deg > 0 else 0.0

    # Ground slope in front of the footing (Hansen).
    beta = ground_slope_deg
    if beta <= 0:
        gc = gq = g_gamma = 1.0
    else:
        gc = 1.0 - beta / 147.0
        gq = g_gamma = (1.0 - 0.5 * math.tan(math.radians(beta))) ** 5

    # Tilted footing base (Hansen).
    eta = base_tilt_deg
    if eta <= 0:
        bc = bq = b_gamma = 1.0
    else:
        bc = 1.0 - eta / 147.0
        bq = math.exp(-2.0 * math.radians(eta) * tan_phi)
        b_gamma = math.exp(-2.7 * math.radians(eta) * tan_phi)

    return CorrectionFactors(
        sc=sc, sq=sq, s_gamma=s_gamma,
        dc=dc, dq=dq, d_gamma=d_gamma,
        ic=ic, iq=iq, i_gamma=i_gamma,
        gc=gc, gq=gq, g_gamma=g_gamma,
        bc=bc, bq=bq, b_gamma=b_gamma,
    )
