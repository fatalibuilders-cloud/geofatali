"""USCS classification and the empirical correlations."""

from __future__ import annotations

import pytest

from geofatali_engine.soil import correlations as corr
from geofatali_engine.soil.uscs import (
    IndexTests,
    a_line_pi,
    classify_uscs,
    is_problem_soil,
    swell_potential,
)
from geofatali_engine.provenance import Source
from geofatali_engine.warnings import InvalidInput


class TestUscs:
    def test_clayey_sand_is_sc(self):
        c = classify_uscs(IndexTests(
            fines_percent=29, gravel_percent=13, sand_percent=58,
            liquid_limit=38, plastic_limit=20,
        ))
        assert c.symbol == "SC"
        assert c.name == "Clayey sand"
        assert c.basis == "LAB_CONFIRMED_CLASSIFICATION"

    def test_silty_sand_is_sm(self):
        c = classify_uscs(IndexTests(
            fines_percent=25, gravel_percent=5, sand_percent=70,
            liquid_limit=32, plastic_limit=27,
        ))
        assert c.symbol == "SM"

    def test_fat_clay_is_ch_and_very_expansive(self):
        c = classify_uscs(IndexTests(fines_percent=80, liquid_limit=68, plastic_limit=26))
        assert c.symbol == "CH"
        assert swell_potential(c.plasticity_index) == "VERY_HIGH"
        assert is_problem_soil("CH")

    def test_lean_clay_is_cl(self):
        c = classify_uscs(IndexTests(fines_percent=70, liquid_limit=38, plastic_limit=20))
        assert c.symbol == "CL"

    def test_low_plasticity_silt_is_ml(self):
        c = classify_uscs(IndexTests(fines_percent=65, liquid_limit=30, plastic_limit=27))
        assert c.symbol == "ML"

    def test_elastic_silt_is_mh(self):
        c = classify_uscs(IndexTests(fines_percent=75, liquid_limit=60, plastic_limit=35))
        assert c.symbol == "MH"

    def test_the_cl_ml_band_between_pi_four_and_seven(self):
        c = classify_uscs(IndexTests(fines_percent=60, liquid_limit=28, plastic_limit=22))
        assert c.symbol == "CL-ML"

    def test_well_graded_sand_needs_cu_and_cc(self):
        well = classify_uscs(IndexTests(
            fines_percent=3, gravel_percent=10, sand_percent=87, cu=7.2, cc=1.8))
        poor = classify_uscs(IndexTests(
            fines_percent=3, gravel_percent=10, sand_percent=87, cu=3.0, cc=0.8))
        assert well.symbol == "SW"
        assert poor.symbol == "SP"

    def test_gravel_takes_the_g_prefix(self):
        c = classify_uscs(IndexTests(
            fines_percent=2, gravel_percent=70, sand_percent=28, cu=8.0, cc=2.0))
        assert c.symbol == "GW"

    def test_missing_gradation_falls_to_the_conservative_branch_with_a_warning(self):
        c = classify_uscs(IndexTests(fines_percent=3, gravel_percent=10, sand_percent=87))
        assert c.symbol == "SP"
        assert "MISSING_GRADATION_COEFFICIENTS" in c.warnings.codes()

    def test_borderline_fines_produce_a_dual_symbol(self):
        c = classify_uscs(IndexTests(
            fines_percent=8, gravel_percent=12, sand_percent=80,
            cu=7.0, cc=1.5, liquid_limit=30, plastic_limit=26,
        ))
        assert c.symbol == "SW-SM"
        assert "DUAL_SYMBOL" in c.warnings.codes()

    def test_peat_short_circuits_everything(self):
        assert classify_uscs(IndexTests(peat=True)).symbol == "PT"

    def test_fine_grained_soil_without_limits_refuses(self):
        with pytest.raises(InvalidInput):
            classify_uscs(IndexTests(fines_percent=70))

    def test_no_fines_percentage_refuses(self):
        with pytest.raises(InvalidInput):
            classify_uscs(IndexTests(gravel_percent=10, sand_percent=40))

    def test_plastic_limit_above_liquid_limit_is_rejected(self):
        with pytest.raises(InvalidInput):
            classify_uscs(IndexTests(fines_percent=70, liquid_limit=30, plastic_limit=40))

    def test_impossible_plasticity_above_the_u_line_is_flagged(self):
        c = classify_uscs(IndexTests(fines_percent=70, liquid_limit=40, plastic_limit=2))
        assert "ABOVE_U_LINE" in c.warnings.codes()

    def test_a_line_is_the_casagrande_definition(self):
        assert a_line_pi(50) == pytest.approx(0.73 * 30)

    def test_swell_bands(self):
        assert swell_potential(8) == "LOW"
        assert swell_potential(18) == "MEDIUM"
        assert swell_potential(28) == "HIGH"
        assert swell_potential(45) == "VERY_HIGH"
        assert swell_potential(None) == "UNKNOWN"


class TestSptCorrections:
    def test_corrections_are_reported_separately_never_applied_silently(self):
        c = corr.correct_spt(n_raw=20, energy_ratio_percent=45, rod_length_m=3,
                             effective_overburden_kpa=100)
        assert c.ce == pytest.approx(45 / 60)
        assert c.cr == 0.75
        assert c.n60 == pytest.approx(20 * (45 / 60) * 1.0 * 0.75)
        assert c.as_dict()["method"] == "skempton_1986"

    def test_overburden_correction_is_capped(self):
        c = corr.correct_spt(n_raw=10, effective_overburden_kpa=5)
        assert c.cn == pytest.approx(1.7)
        assert "SHALLOW_OVERBURDEN_CORRECTION" in c.warnings.codes()

    def test_without_overburden_there_is_no_normalised_blow_count(self):
        c = corr.correct_spt(n_raw=15)
        assert c.n1_60 is None
        assert "NO_OVERBURDEN_CORRECTION" in c.warnings.codes()

    def test_negative_blow_count_is_rejected(self):
        with pytest.raises(InvalidInput):
            corr.correct_spt(n_raw=-1)

    def test_correlated_friction_angle_is_marked_estimated_and_warned(self):
        result = corr.friction_angle_from_spt(20)
        assert result.measurement.source is Source.ESTIMATED
        assert result.measurement.is_measured is False
        assert "CORRELATED_FRICTION_ANGLE" in result.warnings.codes()
        assert 30 <= result.value <= 34

    def test_friction_angle_rises_with_blow_count(self):
        assert corr.friction_angle_from_spt(30).value > corr.friction_angle_from_spt(10).value

    def test_undrained_strength_factor_is_bounded(self):
        with pytest.raises(InvalidInput):
            corr.undrained_strength_from_spt(10, factor=50)

    def test_modulus_family_must_be_known(self):
        with pytest.raises(InvalidInput):
            corr.youngs_modulus_from_spt(10, soil_family="custard")


class TestDcp:
    def test_index_is_penetration_per_blow(self):
        assert corr.dcp_index(blows=5, penetration_mm=100) == 20

    def test_cbr_falls_as_the_index_rises(self):
        assert corr.cbr_from_dcp(10).value > corr.cbr_from_dcp(40).value

    def test_a_very_weak_subgrade_is_warned_about(self):
        result = corr.cbr_from_dcp(80)
        assert "VERY_SOFT_SUBGRADE" in result.warnings.codes()

    def test_subgrade_classes_follow_orn_31(self):
        assert corr.subgrade_class_from_cbr(2) == "S1"
        assert corr.subgrade_class_from_cbr(6) == "S3"
        assert corr.subgrade_class_from_cbr(40) == "S6"

    def test_zero_blows_is_rejected(self):
        with pytest.raises(InvalidInput):
            corr.dcp_index(blows=0, penetration_mm=100)


class TestCpt:
    def test_friction_ratio_and_behaviour_type(self):
        assert corr.friction_ratio(10.0, 50.0) == pytest.approx(0.5)
        assert corr.soil_behaviour_type(10.0, 50.0).startswith("Sand")
        # Rf = 4.0% falls in the clayey silt band; 6.0% is clay.
        assert corr.soil_behaviour_type(1.2, 48.0).startswith("Clayey silt")
        assert corr.soil_behaviour_type(0.8, 48.0) == "Clay"

    def test_cone_factor_is_bounded(self):
        with pytest.raises(InvalidInput):
            corr.undrained_strength_from_cpt(qc_mpa=1.0, total_overburden_kpa=50, nk=3)

    def test_qc_below_overburden_is_flagged_critical(self):
        result = corr.undrained_strength_from_cpt(
            qc_mpa=0.02, total_overburden_kpa=100, nk=17)
        assert result.warnings.has_critical

    def test_effective_overburden_accounts_for_the_water_table(self):
        dry = corr.effective_overburden(depth_m=5, unit_weight_kn_m3=18, groundwater_depth_m=None)
        wet = corr.effective_overburden(depth_m=5, unit_weight_kn_m3=18, groundwater_depth_m=1)
        assert dry == pytest.approx(90)
        assert wet < dry
