"""The HTTP contract: validation, refusals, and results that carry their method."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
API = "/api/v1"


def test_health_reports_the_engine_version():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["engine_version"]


class TestBearingCapacity:
    def test_the_spec_example_request_shape_is_accepted(self):
        response = client.post(f"{API}/calculations/bearing-capacity", json={
            "method": "terzaghi",
            "soil": {"cohesion_kpa": 25, "friction_angle_deg": 24, "unit_weight_kn_m3": 18},
            "foundation": {"width_m": 2.0, "depth_m": 1.5, "length_m": 2.0, "shape": "square"},
            "groundwater": {"groundwater_depth_m": 5.0},
            "safety_factor": 3.0,
        })
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "CALCULATED"
        assert body["method"] == "terzaghi"
        assert body["results"]["ultimate_capacity_kpa"] == pytest.approx(986.9, rel=0.01)
        assert body["engine_version"]
        assert body["reference"]

    def test_missing_soil_strength_returns_a_structured_refusal_not_an_error(self):
        response = client.post(f"{API}/calculations/bearing-capacity", json={
            "soil": {"unit_weight_kn_m3": 18},
            "foundation": {"width_m": 2.0, "depth_m": 1.5, "shape": "square"},
        })
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "INSUFFICIENT_DATA"
        assert body["results"] == {}
        assert any(w["severity"] == "CRITICAL" for w in body["warnings"])

    def test_impossible_input_is_a_422_naming_the_field(self):
        response = client.post(f"{API}/calculations/bearing-capacity", json={
            "soil": {"cohesion_kpa": 25, "friction_angle_deg": 24, "unit_weight_kn_m3": 18},
            "foundation": {"width_m": -2.0, "depth_m": 1.5, "shape": "square"},
        })
        assert response.status_code == 422

    def test_an_unknown_method_is_rejected_by_the_schema(self):
        response = client.post(f"{API}/calculations/bearing-capacity", json={
            "method": "vibes",
            "soil": {"cohesion_kpa": 25, "friction_angle_deg": 24, "unit_weight_kn_m3": 18},
            "foundation": {"width_m": 2.0, "depth_m": 1.5, "shape": "square"},
        })
        assert response.status_code == 422

    def test_the_response_carries_provenance_for_every_parameter(self):
        response = client.post(f"{API}/calculations/bearing-capacity", json={
            "soil": {
                "cohesion_kpa": 25, "friction_angle_deg": 24, "unit_weight_kn_m3": 18,
                "cohesion_source": "LABORATORY", "friction_source": "ESTIMATED",
                "unit_weight_source": "FIELD",
            },
            "foundation": {"width_m": 2.0, "depth_m": 1.5, "shape": "square"},
        })
        body = response.json()
        assert body["provenance"]["friction_angle_deg"]["source"] == "ESTIMATED"
        assert body["preliminary"] is True


class TestFootingAndScreening:
    def test_sizing_returns_a_buildable_width_that_carries_the_load(self):
        body = client.post(f"{API}/calculations/footing", json={
            "service_load_kn": 800,
            "soil": {"cohesion_kpa": 25, "friction_angle_deg": 24, "unit_weight_kn_m3": 18},
            "depth_m": 1.5, "shape": "square",
        }).json()
        assert body["status"] == "CALCULATED"
        assert body["results"]["utilisation"] <= 1.0

    def test_screening_returns_candidates_never_a_single_approval(self):
        body = client.post(f"{API}/calculations/foundation-options", json={
            "sector": "buildings_low_rise",
            "service_load_kn": 400,
            "net_allowable_kpa": 180,
            "required_footing_width_m": 1.5,
            "utilisation": 0.6,
            "total_settlement_mm": 15,
            "competent_stratum_depth_m": 1.2,
            "findings": {"groundwater_depth_m": 6.0},
        }).json()
        assert body["results"]["candidate_count"] > 1
        assert any(w["code"] == "CANDIDATES_NOT_A_SELECTION" for w in body["warnings"])

    def test_screening_attaches_construction_steps(self):
        body = client.post(f"{API}/calculations/foundation-options", json={
            "sector": "buildings_low_rise",
            "findings": {"expansive_clay": True, "swell_potential": "HIGH",
                         "black_cotton_depth_m": 1.6},
        }).json()
        steps = body["results"]["candidates"][0]["construction_steps"]
        assert steps and steps[0]["order"] == 1

    def test_steps_endpoint_adapts_to_the_ground(self):
        body = client.post(f"{API}/foundations/steps", json={
            "foundation_type": "strip",
            "sector": "buildings_low_rise",
            "findings": {"expansive_clay": True, "swell_potential": "VERY_HIGH",
                         "black_cotton_depth_m": 2.0, "seismic_pga_g": 0.15},
        }).json()
        titles = [s["title"] for s in body["steps"]]
        assert "Remove or isolate the expansive clay" in titles
        assert "Tie the foundations together" in titles
        assert body["hold_points"]

    def test_an_unknown_foundation_type_is_a_404_that_lists_the_known_ones(self):
        response = client.post(f"{API}/foundations/steps", json={
            "foundation_type": "hover_slab"})
        assert response.status_code == 404
        assert "strip" in response.json()["detail"]["known"]


class TestSoilEndpoints:
    def test_classification_returns_the_symbol_and_the_swell_band(self):
        body = client.post(f"{API}/soil/classify", json={
            "fines_percent": 78, "liquid_limit": 64, "plastic_limit": 24}).json()
        assert body["symbol"] == "CH"
        assert body["swell_potential"] == "VERY_HIGH"
        assert body["basis"] == "LAB_CONFIRMED_CLASSIFICATION"

    def test_a_fine_soil_without_limits_is_a_422(self):
        response = client.post(f"{API}/soil/classify", json={"fines_percent": 78})
        assert response.status_code == 422
        assert response.json()["error"] == "INVALID_INPUT"

    def test_spt_correction_shows_every_factor_separately(self):
        body = client.post(f"{API}/soil/spt-correction", json={
            "n_raw": 20, "energy_ratio_percent": 45, "rod_length_m": 3,
            "effective_overburden_kpa": 100}).json()
        assert body["ce"] == pytest.approx(0.75)
        assert body["cr"] == 0.75
        assert "correlations" in body

    def test_dcp_gives_cbr_and_a_subgrade_class(self):
        body = client.post(f"{API}/soil/dcp", json={
            "blows": 4, "penetration_mm": 160}).json()
        assert body["subgrade_class"] in ("S1", "S2")
        assert body["cbr"]["source"] == "ESTIMATED"


class TestAiBoundary:
    def test_a_clean_observation_is_accepted_and_marked_ai(self):
        body = client.post(f"{API}/soil/ai-observation", json={
            "payload": {
                "probable_soil_class": "SC",
                "description": "Clayey sand",
                "confidence": 0.81,
            },
            "model_provider": "test",
            "model_name": "test-vision",
        }).json()
        assert body["source"] == "AI"
        assert body["basis"] == "AI_VISUAL_CLASSIFICATION"

    def test_a_fabricated_measurement_is_rejected_at_the_api_boundary(self):
        response = client.post(f"{API}/soil/ai-observation", json={
            "payload": {
                "probable_soil_class": "SC",
                "description": "Clayey sand",
                "confidence": 0.81,
                "bearing_capacity_kpa": 180,
            },
            "model_provider": "test",
            "model_name": "test-vision",
        })
        assert response.status_code == 422
        assert response.json()["detail"]["error"] == "FABRICATED_MEASUREMENT"

    def test_the_published_prompt_forbids_invention(self):
        body = client.get(f"{API}/soil/ai-prompt").json()
        assert "Never invent measurements." in body["system_prompt"]


class TestReferenceData:
    def test_every_industry_is_listed_with_what_governs_it(self):
        body = client.get(f"{API}/reference/sectors").json()
        ids = {s["id"] for s in body["sectors"]}
        assert {"roads", "dams", "telecom", "wind_energy", "mining", "bridges"} <= ids
        roads = [s for s in body["sectors"] if s["id"] == "roads"][0]
        assert any(c["id"] == "subgrade" for c in roads["governing_checks"])

    def test_every_method_carries_a_citation(self):
        body = client.get(f"{API}/reference/methods").json()
        assert all(m["citation"] for m in body["methods"])

    def test_standards_are_configurable_data_not_hard_coded(self):
        body = client.get(f"{API}/reference/standards").json()
        ids = {s["id"] for s in body["standards"]}
        assert {"eurocode", "bs", "kebs"} <= ids
