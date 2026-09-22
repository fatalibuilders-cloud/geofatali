"""Settlement, load estimation and footing sizing."""

from __future__ import annotations

import pytest

from geofatali_engine.bearing.capacity import GroundConditions, SoilParameters
from geofatali_engine.foundations.sizing import eccentricity_check, size_footing
from geofatali_engine.loads.estimator import (
    ColumnGeometry,
    estimate_column_load,
    typical_slab_thickness_mm,
    wall_load_per_metre,
)
from geofatali_engine.provenance import Source
from geofatali_engine.record import Status
from geofatali_engine.settlement.consolidation import (
    consolidation_settlement,
    consolidation_time_years,
    secondary_compression,
    stress_increment_2to1,
    time_factor_for_degree,
)
from geofatali_engine.settlement.elastic import elastic_settlement, influence_factor
from geofatali_engine.warnings import InvalidInput


class TestElasticSettlement:
    def test_no_modulus_means_no_number(self):
        record = elastic_settlement(applied_pressure_kpa=150, width_m=2.0)
        assert record.status is Status.INSUFFICIENT_DATA
        assert record.results == {}
        assert "oedometer" in record.warnings.items[0].message or "modulus" in record.warnings.items[0].message

    def test_settlement_is_inversely_proportional_to_modulus(self):
        soft = elastic_settlement(applied_pressure_kpa=150, width_m=2.0, youngs_modulus_kpa=10000)
        stiff = elastic_settlement(applied_pressure_kpa=150, width_m=2.0, youngs_modulus_kpa=40000)
        assert soft.results["settlement_mm"] == pytest.approx(
            4 * stiff.results["settlement_mm"], rel=0.001
        )

    def test_settlement_rises_with_pressure(self):
        low = elastic_settlement(applied_pressure_kpa=100, width_m=2.0, youngs_modulus_kpa=20000)
        high = elastic_settlement(applied_pressure_kpa=200, width_m=2.0, youngs_modulus_kpa=20000)
        assert high.results["settlement_mm"] > low.results["settlement_mm"]

    def test_a_longer_footing_has_a_larger_influence_factor(self):
        assert influence_factor(5.0) > influence_factor(1.0)

    def test_embedment_reduces_settlement(self):
        surface = elastic_settlement(
            applied_pressure_kpa=150, width_m=2.0, depth_m=0.0, youngs_modulus_kpa=20000)
        buried = elastic_settlement(
            applied_pressure_kpa=150, width_m=2.0, depth_m=2.0, youngs_modulus_kpa=20000)
        assert buried.results["settlement_mm"] < surface.results["settlement_mm"]

    def test_a_correlated_modulus_is_warned_about(self):
        record = elastic_settlement(
            applied_pressure_kpa=150, width_m=2.0, youngs_modulus_kpa=20000,
            modulus_source=Source.ESTIMATED,
        )
        assert "CORRELATED_MODULUS_IN_SETTLEMENT" in record.warnings.codes()
        assert record.is_preliminary

    def test_exceeding_the_standard_limit_is_flagged(self):
        record = elastic_settlement(
            applied_pressure_kpa=400, width_m=4.0, youngs_modulus_kpa=3000)
        assert "SETTLEMENT_EXCEEDS_LIMIT" in record.warnings.codes()


class TestConsolidation:
    def test_missing_oedometer_data_refuses(self):
        record = consolidation_settlement(
            layer_thickness_m=3, layer_mid_depth_m=6, initial_void_ratio=None,
            compression_index_cc=None, unit_weight_kn_m3=18, groundwater_depth_m=2,
            stress_increment_kpa=25,
        )
        assert record.status is Status.INSUFFICIENT_DATA
        assert {w.field_name for w in record.warnings} >= {
            "compression_index_cc", "initial_void_ratio"
        }

    def test_hand_check_of_the_normally_consolidated_case(self):
        # Sc = Cc H/(1+e0) log10((s0+ds)/s0)
        #    = 0.3 x 3 /(1.9) x log10(120/100) = 0.4737 x 0.0792 = 0.0375 m
        record = consolidation_settlement(
            layer_thickness_m=3, layer_mid_depth_m=5.556, initial_void_ratio=0.9,
            compression_index_cc=0.3, unit_weight_kn_m3=18, groundwater_depth_m=None,
            stress_increment_kpa=20,
        )
        assert record.results["initial_effective_stress_kpa"] == pytest.approx(100, rel=0.01)
        assert record.results["settlement_mm"] == pytest.approx(37.5, rel=0.02)

    def test_without_a_preconsolidation_pressure_it_assumes_the_conservative_case(self):
        record = consolidation_settlement(
            layer_thickness_m=3, layer_mid_depth_m=6, initial_void_ratio=0.9,
            compression_index_cc=0.3, unit_weight_kn_m3=18, groundwater_depth_m=2,
            stress_increment_kpa=25,
        )
        assert record.results["state"] == "normally_consolidated"
        assert "ASSUMED_NORMALLY_CONSOLIDATED" in record.warnings.codes()

    def test_an_over_consolidated_clay_settles_far_less(self):
        common = dict(
            layer_thickness_m=3, layer_mid_depth_m=6, initial_void_ratio=0.9,
            compression_index_cc=0.3, unit_weight_kn_m3=18, groundwater_depth_m=2,
            stress_increment_kpa=25,
        )
        nc = consolidation_settlement(**common)
        oc = consolidation_settlement(
            **common, preconsolidation_pressure_kpa=400, recompression_index_cr=0.05)
        assert oc.results["state"] == "over_consolidated_recompression_only"
        assert oc.results["settlement_mm"] < nc.results["settlement_mm"] / 3

    def test_crossing_the_preconsolidation_pressure_is_flagged(self):
        record = consolidation_settlement(
            layer_thickness_m=3, layer_mid_depth_m=6, initial_void_ratio=0.9,
            compression_index_cc=0.3, unit_weight_kn_m3=18, groundwater_depth_m=2,
            stress_increment_kpa=200, preconsolidation_pressure_kpa=100,
            recompression_index_cr=0.05,
        )
        assert record.results["state"] == "over_consolidated_crossing"
        assert "CROSSES_PRECONSOLIDATION" in record.warnings.codes()

    def test_missing_cr_is_estimated_openly_not_silently(self):
        record = consolidation_settlement(
            layer_thickness_m=3, layer_mid_depth_m=6, initial_void_ratio=0.9,
            compression_index_cc=0.3, unit_weight_kn_m3=18, groundwater_depth_m=2,
            stress_increment_kpa=25, preconsolidation_pressure_kpa=300,
        )
        assert "ASSUMED_RECOMPRESSION_INDEX" in record.warnings.codes()
        assert record.provenance.entries["recompression_index_cr"].source is Source.ESTIMATED

    def test_stress_spreads_and_decays_with_depth(self):
        shallow = stress_increment_2to1(load_kn=1000, width_m=2, length_m=2, depth_below_base_m=1)
        deep = stress_increment_2to1(load_kn=1000, width_m=2, length_m=2, depth_below_base_m=6)
        assert shallow > deep

    def test_time_factors_match_terzaghi(self):
        assert time_factor_for_degree(0.5) == pytest.approx(0.197, rel=0.02)
        assert time_factor_for_degree(0.9) == pytest.approx(0.848, rel=0.02)

    def test_full_consolidation_is_never_reached(self):
        with pytest.raises(ValueError):
            time_factor_for_degree(1.0)

    def test_double_drainage_halves_the_path_and_quarters_the_time(self):
        single = consolidation_time_years(
            degree_of_consolidation=0.9, drainage_path_m=3.0, cv_m2_per_year=2.0)
        double = consolidation_time_years(
            degree_of_consolidation=0.9, drainage_path_m=1.5, cv_m2_per_year=2.0)
        assert single == pytest.approx(4 * double, rel=0.001)

    def test_secondary_compression_is_zero_when_time_does_not_advance(self):
        assert secondary_compression(
            secondary_index_c_alpha=0.01, layer_thickness_m=2,
            void_ratio_end_primary=0.8, time_start_years=1, time_end_years=1) == 0.0


class TestLoadEstimation:
    def test_slab_thickness_follows_span_over_28(self):
        assert typical_slab_thickness_mm(5.6) == 200
        assert typical_slab_thickness_mm(2.0) == 125  # practical minimum

    def test_a_taller_building_loads_the_column_more(self):
        two = estimate_column_load(ColumnGeometry(5, 5, floors=2))
        six = estimate_column_load(ColumnGeometry(5, 5, floors=6))
        assert six.results["service_load_kn"] > two.results["service_load_kn"]

    def test_the_estimate_is_always_labelled_preliminary(self):
        record = estimate_column_load(ColumnGeometry(5, 5, floors=3))
        assert "PRELIMINARY_LOAD_ESTIMATE" in record.warnings.codes()
        assert record.results["mode"] == "B_estimated"
        assert record.is_preliminary

    def test_permanent_and_variable_actions_are_kept_apart(self):
        record = estimate_column_load(ColumnGeometry(5, 5, floors=4))
        assert record.results["permanent_gk_kn"] > 0
        assert record.results["variable_qk_kn"] > 0
        assert record.results["service_load_kn"] == pytest.approx(
            record.results["permanent_gk_kn"] + record.results["variable_qk_kn"], rel=0.001
        )

    def test_the_factored_load_uses_the_named_uls_combination(self):
        record = estimate_column_load(ColumnGeometry(5, 5, floors=4), standard_id="eurocode")
        gk = record.results["permanent_gk_kn"]
        qk = record.results["variable_qk_kn"]
        assert record.results["factored_combination"] == "uls_set_b"
        assert record.results["factored_load_kn"] == pytest.approx(1.35 * gk + 1.5 * qk, rel=0.001)

    def test_warehouse_imposed_load_exceeds_residential(self):
        home = estimate_column_load(ColumnGeometry(6, 6, floors=2, occupancy="residential"))
        store = estimate_column_load(ColumnGeometry(6, 6, floors=2, occupancy="warehouse"))
        assert store.results["variable_qk_kn"] > home.results["variable_qk_kn"]

    def test_no_double_counting_every_item_appears_once_per_floor(self):
        record = estimate_column_load(ColumnGeometry(5, 5, floors=3))
        titles = [line["item"] for line in record.results["breakdown"]]
        assert len(titles) == len(set(titles))

    def test_unknown_occupancy_is_rejected(self):
        with pytest.raises(InvalidInput):
            estimate_column_load(ColumnGeometry(5, 5, floors=2, occupancy="spaceport"))

    def test_wall_load_per_metre_rises_with_storeys(self):
        one = wall_load_per_metre(floors=1, floor_height_m=3, wall_type="concrete_block_200", slab_span_m=4)
        two = wall_load_per_metre(floors=2, floor_height_m=3, wall_type="concrete_block_200", slab_span_m=4)
        assert two["service_load_kn_per_m"] > one["service_load_kn_per_m"]


class TestFootingSizing:
    def test_it_converges_and_the_result_carries_the_load(self):
        record = size_footing(
            service_load_kn=800,
            soil=SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=25, friction_angle_deg=24),
            depth_m=1.5, shape="square", method="vesic",
        )
        assert record.status is Status.CALCULATED
        assert record.results["converged"]
        assert record.results["utilisation"] <= 1.0
        assert record.results["applied_pressure_kpa"] <= record.results["net_allowable_capacity_kpa"]

    def test_a_heavier_load_needs_a_bigger_footing(self):
        soil = SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=25, friction_angle_deg=24)
        light = size_footing(service_load_kn=300, soil=soil, depth_m=1.5)
        heavy = size_footing(service_load_kn=1500, soil=soil, depth_m=1.5)
        assert heavy.results["width_m"] > light.results["width_m"]

    def test_weaker_ground_needs_a_bigger_footing(self):
        strong = size_footing(
            service_load_kn=800,
            soil=SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=60, friction_angle_deg=30),
            depth_m=1.5)
        weak = size_footing(
            service_load_kn=800,
            soil=SoilParameters(unit_weight_kn_m3=16, cohesion_kpa=10, friction_angle_deg=18),
            depth_m=1.5)
        assert weak.results["width_m"] > strong.results["width_m"]

    def test_sizes_come_out_on_a_buildable_increment(self):
        record = size_footing(
            service_load_kn=737,
            soil=SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=25, friction_angle_deg=24),
            depth_m=1.5)
        assert round(record.results["width_m"] * 100) % 5 == 0

    def test_missing_soil_data_propagates_the_refusal(self):
        record = size_footing(
            service_load_kn=800, soil=SoilParameters(unit_weight_kn_m3=18), depth_m=1.5)
        assert record.status is Status.INSUFFICIENT_DATA
        assert record.calculation_type == "footing_sizing"

    def test_very_weak_ground_flags_that_a_raft_is_the_answer(self):
        record = size_footing(
            service_load_kn=2500,
            soil=SoilParameters(unit_weight_kn_m3=15, cohesion_kpa=8, friction_angle_deg=0,
                                analysis="undrained"),
            depth_m=1.0, max_width_m=4.0)
        assert "FOOTING_TOO_LARGE" in record.warnings.codes()


class TestEccentricity:
    def test_inside_the_middle_third_the_whole_base_bears(self):
        r = eccentricity_check(axial_load_kn=800, moment_knm=100, width_m=2.4, length_m=2.4)
        assert r["within_middle_third"]
        assert r["regime"] == "full_contact"
        assert r["q_min_kpa"] > 0

    def test_the_classic_six_e_over_b_formula(self):
        p, m, b = 900.0, 90.0, 3.0
        r = eccentricity_check(axial_load_kn=p, moment_knm=m, width_m=b, length_m=b)
        e = m / p
        area = b * b
        assert r["q_max_kpa"] == pytest.approx((p / area) * (1 + 6 * e / b), rel=0.001)
        assert r["q_min_kpa"] == pytest.approx((p / area) * (1 - 6 * e / b), rel=0.001)

    def test_outside_the_middle_third_it_switches_to_partial_contact(self):
        r = eccentricity_check(axial_load_kn=800, moment_knm=400, width_m=2.4, length_m=2.4)
        assert not r["within_middle_third"]
        assert r["regime"] == "partial_contact"
        assert r["q_min_kpa"] == 0.0
        assert r["base_in_contact_fraction"] < 1.0

    def test_an_eccentricity_beyond_half_the_width_is_unstable(self):
        r = eccentricity_check(axial_load_kn=100, moment_knm=200, width_m=2.0)
        assert r["regime"] == "unstable"

    def test_effective_width_follows_meyerhof(self):
        r = eccentricity_check(axial_load_kn=800, moment_knm=160, width_m=2.0, length_m=2.0)
        assert r["effective_width_m"] == pytest.approx(2.0 - 2 * 0.2, rel=0.001)

    def test_sliding_without_a_friction_angle_says_so(self):
        r = eccentricity_check(
            axial_load_kn=800, moment_knm=50, width_m=2.0, horizontal_load_kn=100)
        assert r["sliding"]["status"] == "INSUFFICIENT_DATA"

    def test_sliding_with_a_friction_angle_is_checked(self):
        r = eccentricity_check(
            axial_load_kn=800, moment_knm=50, width_m=2.0,
            horizontal_load_kn=100, base_friction_angle_deg=30)
        assert r["sliding"]["factor_of_safety"] == pytest.approx(800 * 0.5774 / 100, rel=0.01)
        assert r["sliding"]["adequate"]
