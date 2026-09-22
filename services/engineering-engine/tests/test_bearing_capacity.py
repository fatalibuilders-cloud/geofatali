"""Bearing capacity: formula, corrections, water table, and the refusal path."""

from __future__ import annotations

import math

import pytest

from geofatali_engine.bearing.capacity import (
    Footing,
    GroundConditions,
    SoilParameters,
    bearing_capacity,
    water_table_effect,
)
from geofatali_engine.bearing.factors import bearing_factors
from geofatali_engine.record import Status
from geofatali_engine.units import GAMMA_WATER_KN_M3
from geofatali_engine.warnings import InvalidInput


class TestBearingFactors:
    """Against the values every foundation textbook tabulates."""

    @pytest.mark.parametrize(
        "phi,nq,nc",
        [
            (0, 1.00, 5.14),
            (20, 6.40, 14.83),
            (30, 18.40, 30.14),
            (35, 33.30, 46.12),
            (40, 64.20, 75.31),
        ],
    )
    def test_nq_and_nc_match_published_tables(self, phi, nq, nc):
        f = bearing_factors(phi, "vesic")
        assert f.nq == pytest.approx(nq, rel=0.01)
        assert f.nc == pytest.approx(nc, rel=0.01)

    @pytest.mark.parametrize(
        "method,expected",
        [("vesic", 22.40), ("hansen", 15.07), ("meyerhof", 15.67), ("terzaghi", 18.08)],
    )
    def test_n_gamma_differs_by_method_as_published(self, method, expected):
        assert bearing_factors(30, method).n_gamma == pytest.approx(expected, rel=0.01)

    def test_phi_zero_is_the_undrained_limit_not_a_division_by_zero(self):
        for method in ("vesic", "hansen", "meyerhof"):
            f = bearing_factors(0, method)
            assert f.nc == pytest.approx(5.14, rel=0.001)
            assert f.nq == 1.0
            assert f.n_gamma == 0.0

    def test_terzaghi_uses_its_own_nc_at_phi_zero(self):
        assert bearing_factors(0, "terzaghi").nc == pytest.approx(5.7)

    def test_factors_increase_monotonically_with_friction_angle(self):
        previous = bearing_factors(0, "vesic")
        for phi in range(1, 45):
            current = bearing_factors(phi, "vesic")
            assert current.nq > previous.nq
            assert current.n_gamma >= previous.n_gamma
            previous = current

    def test_impossible_friction_angle_is_rejected(self):
        with pytest.raises(InvalidInput):
            bearing_factors(75, "vesic")
        with pytest.raises(InvalidInput):
            bearing_factors(-5, "vesic")

    def test_unknown_method_is_rejected_rather_than_defaulted(self):
        with pytest.raises(InvalidInput):
            bearing_factors(30, "some_method_we_do_not_have")


class TestTerzaghiRegression:
    """A worked example checked by hand, kept as a regression case."""

    def test_square_footing_matches_hand_calculation(self):
        # c = 25 kPa, phi = 24 deg, gamma = 18 kN/m3, B = 2.0 m, D = 1.5 m.
        # Nq = 9.60, Nc = 19.33, Ngamma = 6.90 (Terzaghi via Bowles' fit)
        # q_ult = 1.3(25)(19.33) + 18(1.5)(9.60) + 0.4(18)(2)(6.90)
        #       = 628.2 + 259.3 + 99.4 = 986.9 kPa
        record = bearing_capacity(
            soil=SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=25, friction_angle_deg=24),
            footing=Footing(width_m=2.0, depth_m=1.5, length_m=2.0, shape="square"),
            ground=GroundConditions(groundwater_depth_m=5.0),
            method="terzaghi",
            factor_of_safety=3.0,
        )
        assert record.status is Status.CALCULATED
        assert record.results["ultimate_capacity_kpa"] == pytest.approx(986.9, rel=0.005)
        net_ultimate = 986.9 - 18 * 1.5
        assert record.results["net_allowable_capacity_kpa"] == pytest.approx(
            net_ultimate / 3.0, rel=0.005
        )

    def test_every_result_carries_method_standard_and_engine_version(self):
        record = bearing_capacity(
            soil=SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=25, friction_angle_deg=24),
            footing=Footing(width_m=2.0, depth_m=1.5, shape="square"),
            method="hansen",
            standard_id="kebs",
        )
        d = record.as_dict()
        assert d["method"] == "hansen"
        assert d["standard"] == "kebs"
        assert d["engine_version"]
        assert d["reference"]  # the published citation is always attached
        assert d["inputs"]["soil"]["cohesion_kpa"] == 25  # reproducible from inputs


class TestWaterTable:
    def test_deep_water_table_has_no_effect(self):
        effect = water_table_effect(
            SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=10, friction_angle_deg=30),
            Footing(width_m=2.0, depth_m=1.5, shape="square"),
            GroundConditions(groundwater_depth_m=20.0),
        )
        assert effect.case == "III"
        assert effect.effective_gamma_kn_m3 == 18

    def test_water_table_at_founding_level_makes_the_soil_buoyant(self):
        effect = water_table_effect(
            SoilParameters(unit_weight_kn_m3=20, saturated_unit_weight_kn_m3=20,
                           cohesion_kpa=10, friction_angle_deg=30),
            Footing(width_m=2.0, depth_m=1.5, shape="square"),
            GroundConditions(groundwater_depth_m=1.0),
        )
        assert effect.case == "I"
        assert effect.effective_gamma_kn_m3 == pytest.approx(20 - GAMMA_WATER_KN_M3)

    def test_water_table_within_a_width_below_is_interpolated(self):
        effect = water_table_effect(
            SoilParameters(unit_weight_kn_m3=20, saturated_unit_weight_kn_m3=20,
                           cohesion_kpa=10, friction_angle_deg=30),
            Footing(width_m=2.0, depth_m=1.5, shape="square"),
            GroundConditions(groundwater_depth_m=2.5),
        )
        assert effect.case == "II"
        submerged = 20 - GAMMA_WATER_KN_M3
        assert submerged < effect.effective_gamma_kn_m3 < 20

    def test_rising_water_table_never_increases_capacity(self):
        soil = SoilParameters(unit_weight_kn_m3=19, saturated_unit_weight_kn_m3=20,
                              cohesion_kpa=0, friction_angle_deg=33)
        footing = Footing(width_m=2.5, depth_m=1.5, shape="square")
        previous = math.inf
        for depth in (10.0, 5.0, 4.0, 3.0, 2.0, 1.5, 1.0, 0.0):
            record = bearing_capacity(
                soil=soil, footing=footing,
                ground=GroundConditions(groundwater_depth_m=depth), method="vesic",
            )
            current = record.results["ultimate_capacity_kpa"]
            assert current <= previous + 1e-6, f"capacity rose as water table rose to {depth} m"
            previous = current


class TestRefusalsAndValidation:
    def test_no_strength_parameters_refuses_rather_than_assuming(self):
        record = bearing_capacity(
            soil=SoilParameters(unit_weight_kn_m3=18),
            footing=Footing(width_m=2.0, depth_m=1.5, shape="square"),
        )
        assert record.status is Status.INSUFFICIENT_DATA
        assert record.results == {}
        assert record.warnings.has_critical
        assert any("friction_angle_deg" == w.field_name for w in record.warnings)

    def test_undrained_analysis_without_cu_refuses(self):
        record = bearing_capacity(
            soil=SoilParameters(unit_weight_kn_m3=18, analysis="undrained"),
            footing=Footing(width_m=2.0, depth_m=1.5, shape="square"),
        )
        assert record.status is Status.INSUFFICIENT_DATA
        assert any(w.field_name == "cohesion_kpa" for w in record.warnings)

    def test_the_refusal_says_what_to_go_and_measure(self):
        record = bearing_capacity(
            soil=SoilParameters(unit_weight_kn_m3=18, analysis="undrained"),
            footing=Footing(width_m=2.0, depth_m=1.5, shape="square"),
        )
        message = record.warnings.items[0].message
        assert "triaxial" in message or "vane" in message

    @pytest.mark.parametrize(
        "kwargs",
        [
            {"width_m": 0, "depth_m": 1.5},
            {"width_m": -2, "depth_m": 1.5},
            {"width_m": 2, "depth_m": -1},
        ],
    )
    def test_impossible_geometry_raises(self, kwargs):
        with pytest.raises(InvalidInput):
            bearing_capacity(
                soil=SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=20, friction_angle_deg=25),
                footing=Footing(shape="square", **kwargs),
            )

    def test_negative_groundwater_depth_raises(self):
        with pytest.raises(InvalidInput):
            bearing_capacity(
                soil=SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=20, friction_angle_deg=25),
                footing=Footing(width_m=2, depth_m=1.5, shape="square"),
                ground=GroundConditions(groundwater_depth_m=-1),
            )

    def test_unit_weight_in_kg_per_m3_is_caught(self):
        record = bearing_capacity(
            soil=SoilParameters(unit_weight_kn_m3=1800, cohesion_kpa=20, friction_angle_deg=25),
            footing=Footing(width_m=2, depth_m=1.5, shape="square"),
        )
        assert "UNIT_WEIGHT_OUT_OF_RANGE" in record.warnings.codes()


class TestProperties:
    """Properties that must hold whatever the numbers are."""

    def test_deeper_footings_carry_more(self):
        soil = SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=10, friction_angle_deg=30)
        previous = 0.0
        for depth in (0.5, 1.0, 1.5, 2.0, 2.5):
            record = bearing_capacity(
                soil=soil, footing=Footing(width_m=2.0, depth_m=depth, shape="square"),
                method="vesic",
            )
            current = record.results["ultimate_capacity_kpa"]
            assert current > previous
            previous = current

    def test_wider_footings_carry_more_pressure_in_granular_soil(self):
        soil = SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=0, friction_angle_deg=34)
        previous = 0.0
        for width in (1.0, 2.0, 3.0, 4.0):
            record = bearing_capacity(
                soil=soil, footing=Footing(width_m=width, depth_m=1.5, shape="square"),
                method="vesic",
            )
            current = record.results["ultimate_capacity_kpa"]
            assert current > previous
            previous = current

    def test_a_higher_factor_of_safety_lowers_the_allowable(self):
        soil = SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=25, friction_angle_deg=24)
        footing = Footing(width_m=2.0, depth_m=1.5, shape="square")
        low = bearing_capacity(soil=soil, footing=footing, factor_of_safety=2.0)
        high = bearing_capacity(soil=soil, footing=footing, factor_of_safety=4.0)
        assert high.results["net_allowable_capacity_kpa"] < low.results["net_allowable_capacity_kpa"]

    def test_vesic_is_not_more_conservative_than_hansen_in_sand(self):
        soil = SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=0, friction_angle_deg=35)
        footing = Footing(width_m=3.0, depth_m=1.5, shape="square")
        vesic = bearing_capacity(soil=soil, footing=footing, method="vesic")
        hansen = bearing_capacity(soil=soil, footing=footing, method="hansen")
        assert vesic.results["ultimate_capacity_kpa"] > hansen.results["ultimate_capacity_kpa"]

    def test_undrained_clay_capacity_is_the_classic_five_point_one_four_cu(self):
        # A strip footing at the surface on phi = 0 clay: q_ult = 5.14 Cu.
        record = bearing_capacity(
            soil=SoilParameters(unit_weight_kn_m3=18, cohesion_kpa=50, analysis="undrained"),
            footing=Footing(width_m=2.0, depth_m=0.0, shape="strip"),
            method="hansen",
        )
        assert record.results["ultimate_capacity_kpa"] == pytest.approx(5.14 * 50, rel=0.02)


class TestProvenance:
    def test_a_correlated_parameter_makes_the_result_preliminary(self):
        from geofatali_engine.provenance import Source

        measured = bearing_capacity(
            soil=SoilParameters(
                unit_weight_kn_m3=18, cohesion_kpa=25, friction_angle_deg=24,
                cohesion_source=Source.LABORATORY,
                friction_source=Source.LABORATORY,
                unit_weight_source=Source.LABORATORY,
            ),
            footing=Footing(width_m=2.0, depth_m=1.5, shape="square"),
        )
        correlated = bearing_capacity(
            soil=SoilParameters(
                unit_weight_kn_m3=18, cohesion_kpa=25, friction_angle_deg=24,
                cohesion_source=Source.LABORATORY,
                friction_source=Source.ESTIMATED,
                unit_weight_source=Source.LABORATORY,
            ),
            footing=Footing(width_m=2.0, depth_m=1.5, shape="square"),
        )
        assert measured.is_preliminary is False
        assert correlated.is_preliminary is True
        assert "PRELIMINARY_RESULT" in correlated.warnings.codes()

    def test_an_ai_sourced_parameter_is_never_treated_as_measured(self):
        from geofatali_engine.provenance import Source

        record = bearing_capacity(
            soil=SoilParameters(
                unit_weight_kn_m3=18, cohesion_kpa=25, friction_angle_deg=24,
                friction_source=Source.AI,
            ),
            footing=Footing(width_m=2.0, depth_m=1.5, shape="square"),
        )
        assert record.provenance.entries["friction_angle_deg"].is_measured is False
        assert record.is_preliminary
