# Calculation methods and their sources

Every formula in the engine is listed here with the publication it comes from.
If a method is not in this document, it is not in the engine.

## Rules this document exists to keep

1. **No mixing.** A calculation runs one author's method end to end. Vesic's
   N-gamma is not used with Meyerhof's shape factors.
2. **No silent corrections.** Every correction factor is returned separately in
   the result so the arithmetic can be checked line by line.
3. **No invented parameters.** A missing input produces `INSUFFICIENT_DATA` and
   a message naming the test that would supply it.
4. **Correlations are labelled.** Anything derived from an empirical
   relationship is marked `ESTIMATED` and carries its scatter in a warning.

## Bearing capacity

| Term | Source |
|---|---|
| `Nq = e^(π tanφ) tan²(45 + φ/2)` | Reissner (1924) |
| `Nc = (Nq − 1) / tanφ`, `Nc(φ=0) = 5.14` | Prandtl (1921) |
| `Nγ = 1.8 (Nq − 1) tanφ` | Terzaghi (1943), via Bowles' fit to the published chart |
| `Nγ = (Nq − 1) tan(1.4φ)` | Meyerhof (1963) |
| `Nγ = 1.5 (Nq − 1) tanφ` | Hansen (1970) |
| `Nγ = 2 (Nq + 1) tanφ` | Vesic (1973) |

Shape, depth and inclination factors: Meyerhof (1963) for the Meyerhof method;
Hansen (1970) for Hansen and Vesic, including ground-slope and base-tilt
factors. Terzaghi uses his own shape coefficients (1.3/0.4 square, 1.3/0.3
circular, 1.0/0.5 strip) and no depth factors, because his derivation neglects
the shear strength of the soil above founding level.

Water table, after Das:

- Case III — water deeper than `D + B`: no effect.
- Case II — water between the base and `B` below it: the unit weight in the
  self-weight term is interpolated between submerged and bulk.
- Case I — water at or above founding level: submerged unit weight in the
  self-weight term, and a part-moist, part-buoyant surcharge.

Allowable pressure is reported gross and net:
`q_net_ult = q_ult − q`, `q_allow_net = q_net_ult / FS`,
`q_allow_gross = q_allow_net + q`.

## Settlement

| Method | Source |
|---|---|
| Elastic: `Se = q B (1 − ν²) Is If / Es` | Bowles (1996) ch. 5; Fox embedment correction |
| 1D consolidation: `Sc = (Cc H / (1 + e0)) log₁₀((σ'₀ + Δσ)/σ'₀)` | Terzaghi & Peck (1967) |
| Over-consolidated, crossing σ'p | Two-part Cr then Cc form, Das ch. 11 |
| Secondary compression: `Ss = (Cα/(1 + ep)) H log₁₀(t₂/t₁)` | Mesri & Godlewski (1977) |
| Time factor `Tv(U)` | Terzaghi 1D consolidation theory |
| Stress increment, 2:1 spread | Das, Principles of Foundation Engineering ch. 6 |
| Stress increment, rectangle corner | Boussinesq (1885); Newmark (1935) |

## Field-test correlations

| Correlation | Source | Scatter |
|---|---|---|
| SPT energy, borehole, rod, sampler corrections | Skempton (1986); ASTM D6066 | — |
| `CN = √(100/σ'v)`, capped at 1.7 | Liao & Whitman (1986) | — |
| `φ = 27.1 + 0.3(N1)60 − 0.00054(N1)60²` | Peck, Hanson & Thornburn (1974); Wolff (1989) | ±3° |
| `Dr = √((N1)60/60)` | Skempton (1986) | wide |
| `Cu = k·N60`, k = 4–6 kPa/blow | Stroud (1974) | ~factor of 2 |
| `Es` from N60 by soil family | Bowles (1996) Table 5-6 | order of magnitude |
| `log₁₀(CBR) = 2.632 − 1.28 log₁₀(DN)` | Kleyn (1975); TRL ORN 18 | — |
| Subgrade classes S1–S6 from CBR | TRL ORN 31 | — |
| `Cu = (qc − σv0)/Nk`, Nk 15–20 | Lunne, Robertson & Powell (1997) | ±25% on Nk alone |
| `tanφ = (1/2.68)[log₁₀(qc/σ'v0) + 0.29]` | Robertson & Campanella (1983) | clean quartz sand only |

## Classification

USCS to ASTM D2487, implemented in full: the plasticity chart with the
Casagrande A-line `PI = 0.73(LL − 20)` and the U-line `PI = 0.9(LL − 8)`, the
gravel/sand split, the well-graded criteria (`Cu ≥ 4` for gravel, `Cu ≥ 6` for
sand, with `1 ≤ Cc ≤ 3`), and the dual symbols required in the 5–12% fines
band.

Swell potential bands from plasticity index follow Holtz & Gibbs / IS 1498
practice.

## Loads

Preliminary loads only, and always labelled as such. Occupancy imposed loads
follow EN 1991-1-1 Table 6.2 categories; the multi-storey imposed-load
reduction is EN 1991-1-1 6.3.1.2(11), `αn = (2 + (n − 2)ψ0)/n`. Load
combinations come from the selected standard's configuration, never from a
constant in the calculation body.

## What is deliberately not implemented

These return `CALCULATION_NOT_IMPLEMENTED` rather than an approximation:

- Pile axial capacity (shaft friction and end bearing), group effects and pile
  settlement. The spec is explicit that pile design must not be released
  without thorough validation.
- Slope stability.
- Liquefaction triggering.
- Seepage and piping analysis.
- Dynamic and cyclic soil response.

Each of these governs at least one of the sectors the engine already models,
and each is named in that sector's `governing_checks` so the gap is visible in
the output rather than hidden.
