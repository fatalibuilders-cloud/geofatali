"""The AI layer, and the wall between it and the engineering.

Spec sections 4, 11, 32-33 and rules 2, 5, 8, 11.

The vision model's only job is to say what is *visible* in a soil photograph:
colour, texture, apparent grading, visible layering, moisture appearance. It
may propose a probable USCS class with a confidence. It may not, under any
circumstances, produce a bearing capacity, a cohesion, a friction angle, a
density, an SPT value, a groundwater level, a settlement or a statement that a
foundation is safe.

That is not a guideline here. ``validate_ai_result`` strips any such field out
of the model's response and raises, so a provider that starts hallucinating
measurements cannot poison the calculation engine downstream. The engine never
imports a provider; providers produce ``SoilObservation`` records marked
``Source.AI``, and the provenance ledger carries that marking into every
report.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from ..provenance import Source

PROMPT_VERSION = "2026-09-22.1"

SYSTEM_PROMPT = """You are a geotechnical visual-assessment assistant.

Analyze the supplied soil image or video frames only for visible characteristics.

Do not claim to know measured bearing capacity, shear strength, density,
SPT N-value, groundwater level, settlement, or foundation safety unless
those values are explicitly supplied as measured data.

Return:
1. visible soil characteristics
2. probable soil description
3. probable USCS class if defensible
4. confidence
5. evidence
6. limitations
7. recommended field/laboratory verification

Never invent measurements.
Never provide a final structural foundation approval."""

#: Keys a vision model must never return. If any appears, the response is
#: rejected outright rather than filtered quietly — a model that returns these
#: is misbehaving and the operator needs to know.
FORBIDDEN_KEYS: frozenset[str] = frozenset({
    "bearing_capacity",
    "bearing_capacity_kpa",
    "allowable_bearing_pressure",
    "cohesion",
    "cohesion_kpa",
    "friction_angle",
    "friction_angle_deg",
    "unit_weight",
    "unit_weight_kn_m3",
    "density",
    "dry_density",
    "spt_n",
    "spt_n_value",
    "n60",
    "cpt_qc",
    "groundwater_depth",
    "groundwater_depth_m",
    "settlement",
    "settlement_mm",
    "safe",
    "is_safe",
    "foundation_approved",
    "recommended_foundation",
    "factor_of_safety",
})


class FabricatedMeasurement(ValueError):
    """Raised when a vision model returns a value it cannot possibly have measured."""


@dataclass(frozen=True)
class SoilObservation:
    """What the model saw. Never what the ground is worth."""

    probable_soil_class: str | None
    description: str
    confidence: float
    observations: dict[str, Any] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    recommended_verification: list[str] = field(default_factory=list)
    model_provider: str = "unknown"
    model_name: str = "unknown"
    prompt_version: str = PROMPT_VERSION
    #: Always AI. There is no code path that changes this.
    source: Source = Source.AI
    basis: str = "AI_VISUAL_CLASSIFICATION"

    def as_dict(self) -> dict[str, Any]:
        return {
            "probable_soil_class": self.probable_soil_class,
            "description": self.description,
            "confidence": self.confidence,
            "observations": self.observations,
            "evidence": self.evidence,
            "limitations": self.limitations,
            "recommended_verification": self.recommended_verification,
            "model_provider": self.model_provider,
            "model_name": self.model_name,
            "prompt_version": self.prompt_version,
            "source": self.source.value,
            "basis": self.basis,
        }


def validate_ai_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Reject a model response that claims measured geotechnical values.

    Checks the top level and one level of nesting, which is where a model
    tends to smuggle a number it was told not to produce.
    """
    def offenders(d: dict[str, Any], prefix: str = "") -> list[str]:
        found: list[str] = []
        for key, value in d.items():
            normalised = str(key).strip().lower().replace(" ", "_")
            if normalised in FORBIDDEN_KEYS:
                found.append(f"{prefix}{key}")
            if isinstance(value, dict):
                found.extend(offenders(value, prefix=f"{prefix}{key}."))
        return found

    bad = offenders(payload)
    if bad:
        raise FabricatedMeasurement(
            "The vision model returned measured geotechnical values it cannot have measured "
            f"from an image: {', '.join(sorted(bad))}. The response was rejected. These "
            "values must come from field or laboratory testing."
        )

    confidence = payload.get("confidence")
    if confidence is None:
        raise FabricatedMeasurement(
            "The vision model returned no confidence value. An observation without a stated "
            "uncertainty is not usable — spec section 11 requires the AI to return uncertainty."
        )
    if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
        raise FabricatedMeasurement(
            f"Confidence must be a number between 0 and 1 (got {confidence!r})."
        )
    return payload


def observation_from_payload(
    payload: dict[str, Any], *, model_provider: str, model_name: str
) -> SoilObservation:
    validated = validate_ai_result(payload)
    return SoilObservation(
        probable_soil_class=validated.get("probable_soil_class"),
        description=validated.get("description", ""),
        confidence=float(validated["confidence"]),
        observations=validated.get("observations", {}),
        evidence=list(validated.get("evidence", [])),
        limitations=list(validated.get("limitations", []))
        or ["Visual classification only", "Laboratory confirmation recommended"],
        recommended_verification=list(validated.get("recommended_verification", []))
        or [
            "Atterberg limits and particle-size distribution to confirm the class",
            "A trial pit or borehole to establish what lies below the visible surface",
        ],
        model_provider=model_provider,
        model_name=model_name,
    )


class AIProvider(ABC):
    """Replaceable vision backend. The engine never depends on a concrete one."""

    name: str = "abstract"

    @abstractmethod
    def analyse_images(
        self, images: list[bytes], *, context: dict[str, Any] | None = None
    ) -> SoilObservation:
        """Return a visual observation, or raise. Never return a measurement."""

    def analyse_video_frames(
        self, frames: list[bytes], *, context: dict[str, Any] | None = None
    ) -> SoilObservation:
        """Default: treat selected frames as images. Frame selection is upstream."""
        return self.analyse_images(frames, context=context)


class UnavailableProvider(AIProvider):
    """The honest default when no vision backend is configured.

    It refuses rather than returning an empty or invented observation, so a
    deployment with no AI credentials degrades to "soil AI unavailable" instead
    of to "soil AI says nothing is wrong".
    """

    name = "unavailable"

    def analyse_images(
        self, images: list[bytes], *, context: dict[str, Any] | None = None
    ) -> SoilObservation:
        raise RuntimeError(
            "No AI vision provider is configured. Soil image analysis is unavailable. "
            "Borehole logs, field tests and laboratory results can still be entered by hand, "
            "and every engineering calculation runs without the AI layer."
        )
