"""The wall between the vision model and the engineering.

Spec rules 2, 5, 8 and 11. These are the tests that matter most for the
product's honesty: they prove that no path exists from a photograph to a
measured geotechnical value.
"""

from __future__ import annotations

import pytest

from geofatali_engine.ai.provider import (
    FORBIDDEN_KEYS,
    SYSTEM_PROMPT,
    AIProvider,
    FabricatedMeasurement,
    SoilObservation,
    UnavailableProvider,
    observation_from_payload,
    validate_ai_result,
)
from geofatali_engine.provenance import Source

VALID = {
    "probable_soil_class": "SC",
    "description": "Clayey sand",
    "confidence": 0.81,
    "observations": {
        "sand": 0.58, "clay": 0.29, "silt": 0.13,
        "gravel": "low", "organic_content": "low", "moisture": "moderate",
    },
    "limitations": ["Visual classification only", "Laboratory confirmation recommended"],
}


class TestValidation:
    def test_a_well_formed_observation_passes(self):
        assert validate_ai_result(dict(VALID))

    @pytest.mark.parametrize("key", sorted(FORBIDDEN_KEYS))
    def test_every_forbidden_measurement_is_rejected(self, key):
        payload = dict(VALID)
        payload[key] = 42
        with pytest.raises(FabricatedMeasurement):
            validate_ai_result(payload)

    def test_a_measurement_hidden_one_level_down_is_still_caught(self):
        payload = dict(VALID)
        payload["observations"] = dict(VALID["observations"], spt_n=14)
        with pytest.raises(FabricatedMeasurement):
            validate_ai_result(payload)

    def test_key_casing_and_spacing_do_not_evade_the_check(self):
        for key in ("Bearing Capacity", "FRICTION_ANGLE_DEG", " settlement_mm "):
            payload = dict(VALID)
            payload[key] = 1
            with pytest.raises(FabricatedMeasurement):
                validate_ai_result(payload)

    def test_an_observation_without_confidence_is_rejected(self):
        payload = {k: v for k, v in VALID.items() if k != "confidence"}
        with pytest.raises(FabricatedMeasurement):
            validate_ai_result(payload)

    @pytest.mark.parametrize("bad", [-0.1, 1.4, "high", None])
    def test_confidence_must_be_a_number_between_zero_and_one(self, bad):
        with pytest.raises(FabricatedMeasurement):
            validate_ai_result(dict(VALID, confidence=bad))

    def test_the_rejection_explains_where_the_value_must_come_from(self):
        with pytest.raises(FabricatedMeasurement) as exc:
            validate_ai_result(dict(VALID, bearing_capacity_kpa=150))
        assert "field or laboratory testing" in str(exc.value)


class TestObservation:
    def test_an_observation_is_always_ai_sourced_and_never_measured(self):
        observation = observation_from_payload(
            dict(VALID), model_provider="test", model_name="test-vision")
        assert observation.source is Source.AI
        assert observation.basis == "AI_VISUAL_CLASSIFICATION"
        assert observation.probable_soil_class == "SC"

    def test_limitations_are_supplied_even_if_the_model_omits_them(self):
        payload = {k: v for k, v in VALID.items() if k != "limitations"}
        observation = observation_from_payload(
            payload, model_provider="test", model_name="test-vision")
        assert observation.limitations
        assert observation.recommended_verification

    def test_the_model_and_prompt_version_are_recorded(self):
        observation = observation_from_payload(
            dict(VALID), model_provider="anthropic", model_name="some-vision-model")
        assert observation.model_provider == "anthropic"
        assert observation.prompt_version

    def test_an_ai_class_never_becomes_a_lab_confirmed_class(self):
        observation = observation_from_payload(
            dict(VALID), model_provider="test", model_name="t")
        assert observation.basis != "LAB_CONFIRMED_CLASSIFICATION"


class TestPromptAndProvider:
    def test_the_system_prompt_forbids_inventing_measurements(self):
        assert "Never invent measurements." in SYSTEM_PROMPT
        assert "Never provide a final structural foundation approval." in SYSTEM_PROMPT

    def test_the_default_provider_refuses_rather_than_inventing(self):
        with pytest.raises(RuntimeError) as exc:
            UnavailableProvider().analyse_images([b"not-an-image"])
        assert "unavailable" in str(exc.value).lower()

    def test_a_provider_must_implement_the_interface(self):
        with pytest.raises(TypeError):
            AIProvider()  # abstract

    def test_a_custom_provider_plugs_in_without_the_engine_knowing(self):
        class StubProvider(AIProvider):
            name = "stub"

            def analyse_images(self, images, *, context=None):
                return observation_from_payload(
                    dict(VALID), model_provider=self.name, model_name="stub-1")

        observation = StubProvider().analyse_images([b"x"])
        assert isinstance(observation, SoilObservation)
        assert observation.model_provider == "stub"

    def test_a_misbehaving_provider_cannot_reach_the_engine(self):
        class RogueProvider(AIProvider):
            name = "rogue"

            def analyse_images(self, images, *, context=None):
                return observation_from_payload(
                    dict(VALID, bearing_capacity_kpa=250),
                    model_provider=self.name, model_name="rogue-1",
                )

        with pytest.raises(FabricatedMeasurement):
            RogueProvider().analyse_images([b"x"])
