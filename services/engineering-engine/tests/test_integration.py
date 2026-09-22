"""End to end: project -> soil -> field tests -> calculations -> report.

This is the spec's acceptance path (section 62) run as software. Two sites are
taken all the way through: a black cotton plot on the eastern edge of Nairobi,
and a transmission tower in the Rift. They exercise different sectors,
different governing checks and different answers.
"""

from __future__ import annotations

import pytest

from geofatali_engine.bearing.capacity import (
    Footing,
    GroundConditions,
    SoilParameters,
    bearing_capacity,
)
from geofatali_engine.foundations.screening import ScreeningInput, screen_foundations
from geofatali_engine.foundations.sizing import size_footing
from geofatali_engine.foundations.steps import GroundFindings
from geofatali_engine.loads.estimator import ColumnGeometry, estimate_column_load
from geofatali_engine.provenance import Source
from geofatali_engine.record import Status
from geofatali_engine.report.markdown import render_markdown
from geofatali_engine.report.model import (
    PRELIMINARY_BANNER,
    REVIEWED_BANNER,
    SECTION_ORDER,
    Review,
    build_report,
)
from geofatali_engine.settlement.consolidation import consolidation_settlement
from geofatali_engine.settlement.elastic import elastic_settlement
from geofatali_engine.soil import correlations as corr
from geofatali_engine.soil.uscs import IndexTests, classify_uscs, swell_potential


class TestBlackCottonHouse:
    """A four-storey block on expansive clay — the commonest hard case in Kenya."""

    @pytest.fixture(scope="class")
    @staticmethod
    def project():
        # 1. Laboratory index tests from a trial pit at 1.0 m.
        classification = classify_uscs(IndexTests(
            fines_percent=78, liquid_limit=64, plastic_limit=24))

        # 2. SPT in the borehole at founding level, corrected properly.
        overburden = corr.effective_overburden(
            depth_m=1.5, unit_weight_kn_m3=16.5, groundwater_depth_m=None)
        spt = corr.correct_spt(
            n_raw=6, energy_ratio_percent=60, rod_length_m=3,
            effective_overburden_kpa=overburden)
        cu = corr.undrained_strength_from_spt(spt.n60, reference="BH-01/SPT-1")

        # 3. Preliminary column load from geometry.
        loads = estimate_column_load(ColumnGeometry(
            tributary_width_m=4.5, tributary_length_m=4.5, floors=4,
            occupancy="residential"))

        # 4. Bearing capacity, undrained, from the correlated Cu.
        soil = SoilParameters(
            unit_weight_kn_m3=16.5,
            cohesion_kpa=cu.value,
            analysis="undrained",
            cohesion_source=Source.ESTIMATED,
            unit_weight_source=Source.FIELD,
            reference="BH-01",
        )
        bearing = bearing_capacity(
            soil=soil,
            footing=Footing(width_m=1.5, depth_m=1.5, shape="square"),
            ground=GroundConditions(groundwater_depth_m=8.0, groundwater_observed=True),
            method="hansen",
            standard_id="kebs",
        )
        sizing = size_footing(
            service_load_kn=loads.results["service_load_kn"],
            soil=soil, depth_m=1.5, shape="square", method="hansen",
            standard_id="kebs",
        )
        settlement = consolidation_settlement(
            layer_thickness_m=2.5, layer_mid_depth_m=3.0, initial_void_ratio=1.1,
            compression_index_cc=0.42, unit_weight_kn_m3=16.5, groundwater_depth_m=8.0,
            load_kn=loads.results["service_load_kn"],
            footing_width_m=sizing.results["width_m"],
            footing_length_m=sizing.results["width_m"],
            footing_depth_m=1.5,
            standard_id="kebs",
        )
        findings = GroundFindings(
            expansive_clay=True,
            swell_potential=swell_potential(classification.plasticity_index),
            black_cotton_depth_m=2.5,
            groundwater_depth_m=8.0,
            seismic_pga_g=0.07,
        )
        screening = screen_foundations(ScreeningInput(
            sector_id="buildings_low_rise",
            service_load_kn=loads.results["service_load_kn"],
            net_allowable_kpa=sizing.results["net_allowable_capacity_kpa"],
            required_footing_width_m=sizing.results["width_m"],
            utilisation=sizing.results["utilisation"],
            total_settlement_mm=settlement.results["settlement_mm"],
            column_spacing_m=4.5,
            competent_stratum_depth_m=2.5,
            trial_founding_depth_m=1.5,
            findings=findings,
            standard_id="kebs",
        ))
        return {
            "classification": classification, "spt": spt, "cu": cu, "loads": loads,
            "bearing": bearing, "sizing": sizing, "settlement": settlement,
            "screening": screening, "findings": findings,
            # The correlation warnings are raised before any calculation record
            # exists; the report carries them as data gaps.
            "data_gaps": [w.message for w in list(spt.warnings) + list(cu.warnings)],
        }

    def test_the_laboratory_identifies_expansive_clay(self, project):
        assert project["classification"].symbol == "CH"
        assert swell_potential(project["classification"].plasticity_index) == "VERY_HIGH"

    def test_the_whole_chain_calculates(self, project):
        for key in ("bearing", "sizing", "settlement", "loads", "screening"):
            assert project[key].status is Status.CALCULATED, key

    def test_every_result_is_preliminary_because_cu_was_correlated(self, project):
        assert project["bearing"].is_preliminary
        assert project["bearing"].provenance.entries["cohesion_kpa"].source is Source.ESTIMATED

    def test_the_screen_does_not_recommend_a_plain_shallow_footing(self, project):
        candidates = project["screening"].results["candidates"]
        strip = [c for c in candidates if c["foundation_type"] == "strip"][0]
        assert strip["status"] != "PRELIMINARY_CANDIDATE"

    def test_the_top_candidate_tells_the_builder_to_deal_with_the_clay_first(self, project):
        top = project["screening"].results["candidates"][0]
        first_step = top["construction_steps"][0]
        assert "expansive clay" in (first_step["triggered_by"] or "").lower() or \
               "weak layer" in first_step["title"].lower()

    def test_the_report_has_every_section_and_the_preliminary_banner(self, project):
        report = build_report(
            project_name="Syokimau Apartments",
            client_name="A. Client",
            site_location="Syokimau, Machakos County",
            sector_id="buildings_low_rise",
            standard_id="kebs",
            bearing=project["bearing"],
            sizing=project["sizing"],
            settlement=[project["settlement"]],
            loads=project["loads"],
            screening=project["screening"],
        )
        assert [s.title for s in report.sections] == list(SECTION_ORDER)
        assert report.banner == PRELIMINARY_BANNER

    def test_the_report_gathers_every_warning_as_a_data_gap(self, project):
        report = build_report(
            project_name="Syokimau Apartments", sector_id="buildings_low_rise",
            standard_id="kebs", bearing=project["bearing"], sizing=project["sizing"],
            settlement=[project["settlement"]], loads=project["loads"],
            screening=project["screening"], data_gaps=project["data_gaps"],
        )
        gaps = report.section("Recommendations for further investigation").items
        assert any("correlated" in g.lower() for g in gaps)
        assert any("factor of two" in g for g in gaps)  # the Cu correlation warning survives

    def test_a_missing_borehole_log_is_reported_as_missing_not_hidden(self, project):
        report = build_report(
            project_name="Syokimau Apartments", sector_id="buildings_low_rise",
            bearing=project["bearing"])
        logs = report.section("Borehole logs")
        assert logs.absent_reason
        assert "correlated or assumed" in logs.absent_reason

    def test_the_rendered_report_carries_the_banner_and_the_limitations(self, project):
        report = build_report(
            project_name="Syokimau Apartments", sector_id="buildings_low_rise",
            standard_id="kebs", bearing=project["bearing"], sizing=project["sizing"],
            settlement=[project["settlement"]], loads=project["loads"],
            screening=project["screening"],
        )
        markdown = render_markdown(report)
        assert PRELIMINARY_BANNER in markdown
        assert "not a geotechnical site investigation" in markdown
        assert "engine v" in markdown

    def test_an_engineer_review_is_the_only_thing_that_clears_the_banner(self, project):
        report = build_report(
            project_name="Syokimau Apartments", sector_id="buildings_low_rise",
            bearing=project["bearing"],
            review=Review(
                reviewer_name="J. Mwangi",
                registration_number="EBK/PE/1234",
                status="APPROVED",
                comments="Reviewed against BH-01 and the laboratory report.",
                signed_at="2026-09-22T10:00:00Z",
            ),
        )
        assert report.banner == REVIEWED_BANNER


class TestTransmissionTowerInTheRift:
    """A different industry entirely: uplift, not bearing, decides this one."""

    def test_the_tower_is_screened_on_uplift_and_gets_an_uplift_foundation(self):
        findings = GroundFindings(
            groundwater_depth_m=9.0, collapsible_soil=True, seismic_pga_g=0.2)
        record = screen_foundations(ScreeningInput(
            sector_id="power_transmission",
            service_load_kn=280,
            net_allowable_kpa=220,
            required_footing_width_m=1.4,
            utilisation=0.55,
            total_settlement_mm=9,
            competent_stratum_depth_m=1.8,
            trial_founding_depth_m=2.2,
            uplift_kn=240,
            findings=findings,
        ))
        assert record.status is Status.CALCULATED
        types = [c["foundation_type"] for c in record.results["candidates"]]
        assert "pad_and_chimney" in types
        chimney = [c for c in record.results["candidates"]
                   if c["foundation_type"] == "pad_and_chimney"][0]
        titles = [s["title"] for s in chimney["construction_steps"]]
        assert any("uplift design" in t for t in titles)
        assert any("wet, not only dry" in t for t in titles)  # collapsible soil step
        assert any("Tie the foundations together" in t for t in titles)  # seismic step

    def test_this_sector_reports_its_own_governing_checks(self):
        record = screen_foundations(ScreeningInput(sector_id="power_transmission"))
        checks = record.results["sector"]["governing_checks"]
        assert "uplift" in checks
        assert "thermal" in checks


class TestRoadSubgrade:
    """A road: CBR decides everything, and the app must not talk about footings."""

    def test_dcp_to_cbr_to_subgrade_class_to_treatment(self):
        index = corr.dcp_index(blows=4, penetration_mm=160)
        cbr = corr.cbr_from_dcp(index)
        assert cbr.value < 5
        assert corr.subgrade_class_from_cbr(cbr.value) in ("S1", "S2")

        record = screen_foundations(ScreeningInput(
            sector_id="roads",
            findings=GroundFindings(expansive_clay=True, swell_potential="HIGH"),
        ))
        types = [c["foundation_type"] for c in record.results["candidates"]]
        assert types[0] in ("subgrade_improvement", "ground_improvement_shallow")
        steps = [c for c in record.results["candidates"]
                 if c["foundation_type"] == "subgrade_improvement"][0]["construction_steps"]
        assert any("Proof roll" in s["title"] for s in steps)


class TestReproducibility:
    def test_a_calculation_can_be_re_run_from_its_stored_inputs(self):
        soil = SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=25, friction_angle_deg=24)
        footing = Footing(width_m=2.0, depth_m=1.5, length_m=2.0, shape="square")
        first = bearing_capacity(soil=soil, footing=footing, method="vesic")
        stored = first.as_dict()["inputs"]

        replayed = bearing_capacity(
            soil=SoilParameters(
                unit_weight_kn_m3=stored["soil"]["unit_weight_kn_m3"],
                cohesion_kpa=stored["soil"]["cohesion_kpa"],
                friction_angle_deg=stored["soil"]["friction_angle_deg"],
                analysis=stored["soil"]["analysis"],
            ),
            footing=Footing(
                width_m=stored["footing"]["width_m"],
                depth_m=stored["footing"]["depth_m"],
                length_m=stored["footing"]["length_m"],
                shape=stored["footing"]["shape"],
            ),
            method=stored["method"],
            factor_of_safety=stored["factor_of_safety"],
        )
        assert replayed.results["ultimate_capacity_kpa"] == first.results["ultimate_capacity_kpa"]

    def test_the_whole_record_serialises_to_json(self):
        import json

        record = bearing_capacity(
            soil=SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=25, friction_angle_deg=24),
            footing=Footing(width_m=2.0, depth_m=1.5, shape="square"),
        )
        blob = json.dumps(record.as_dict())
        assert json.loads(blob)["method"] == "vesic"

    def test_the_screening_record_serialises_with_its_steps(self):
        import json

        record = screen_foundations(ScreeningInput(
            sector_id="buildings_low_rise", service_load_kn=400, net_allowable_kpa=180,
            required_footing_width_m=1.4, utilisation=0.6, total_settlement_mm=12,
            competent_stratum_depth_m=1.2,
            findings=GroundFindings(groundwater_depth_m=6.0),
        ))
        blob = json.loads(json.dumps(record.as_dict()))
        assert blob["results"]["candidates"][0]["construction_steps"]
