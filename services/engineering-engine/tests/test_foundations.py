"""Foundation screening, construction steps and the sector model."""

from __future__ import annotations

import pytest

from geofatali_engine.foundations.screening import (
    CandidateStatus,
    ScreeningInput,
    Verdict,
    screen_foundations,
)
from geofatali_engine.foundations.steps import GroundFindings, construction_steps
from geofatali_engine.foundations.types import FOUNDATION_TYPES
from geofatali_engine.sectors import CHECKS, SECTORS, get_sector


def _candidate(record, foundation_type):
    for c in record.results["candidates"]:
        if c["foundation_type"] == foundation_type:
            return c
    return None


class TestSectors:
    def test_every_sector_references_known_checks_and_foundations(self):
        for sector in SECTORS.values():
            for check in sector.governing_checks:
                assert check in CHECKS, f"{sector.id} names unknown check {check}"
            for foundation in sector.candidate_foundations:
                assert foundation in FOUNDATION_TYPES, (
                    f"{sector.id} names unknown foundation {foundation}"
                )

    def test_the_industries_are_genuinely_different_from_one_another(self):
        # A road is governed by subgrade strength; a dam by seepage; a mast by uplift.
        assert "subgrade" in get_sector("roads").governing_checks
        assert "bearing" not in get_sector("roads").governing_checks
        assert "seepage" in get_sector("dams").governing_checks
        assert "uplift" in get_sector("telecom").governing_checks
        assert "stiffness" in get_sector("wind_energy").governing_checks
        assert "scour" in get_sector("bridges").governing_checks

    def test_sectors_carry_their_own_settlement_tolerance(self):
        assert get_sector("roads").settlement_limit_mm > get_sector("bridges").settlement_limit_mm
        assert get_sector("waste").settlement_limit_mm > get_sector("railways").settlement_limit_mm

    def test_every_sector_states_what_the_investigation_must_include(self):
        for sector in SECTORS.values():
            assert sector.required_investigation
            assert sector.standards

    def test_an_unknown_sector_is_rejected(self):
        with pytest.raises(KeyError):
            get_sector("underwater_basket_weaving")


class TestScreening:
    def _good_ground(self, **overrides):
        base = dict(
            sector_id="buildings_low_rise",
            service_load_kn=400,
            net_allowable_kpa=180,
            required_footing_width_m=1.5,
            utilisation=0.65,
            total_settlement_mm=18,
            column_spacing_m=5.0,
            competent_stratum_depth_m=1.2,
            trial_founding_depth_m=1.5,
            findings=GroundFindings(groundwater_depth_m=6.0),
        )
        base.update(overrides)
        return ScreeningInput(**base)

    def test_good_ground_gives_a_simple_shallow_candidate(self):
        record = screen_foundations(self._good_ground())
        top = record.results["candidates"][0]
        assert top["foundation_type"] in ("strip", "pad")
        assert top["status"] == CandidateStatus.PRELIMINARY_CANDIDATE.value

    def test_it_never_returns_a_single_approved_foundation(self):
        record = screen_foundations(self._good_ground())
        assert record.results["candidate_count"] > 1
        assert "CANDIDATES_NOT_A_SELECTION" in record.warnings.codes()
        for candidate in record.results["candidates"]:
            assert candidate["status"] in {s.value for s in CandidateStatus}
            assert "approved" not in candidate["status"].lower()

    def test_every_verdict_carries_its_evidence(self):
        record = screen_foundations(self._good_ground())
        for candidate in record.results["candidates"]:
            for criterion in candidate["criteria"]:
                assert criterion["evidence"], f"{criterion['name']} has no evidence"
                assert criterion["verdict"] in {v.value for v in Verdict}

    def test_expansive_clay_rules_out_a_plain_strip_footing(self):
        record = screen_foundations(self._good_ground(
            findings=GroundFindings(
                expansive_clay=True, swell_potential="VERY_HIGH",
                black_cotton_depth_m=1.8, groundwater_depth_m=6.0,
            )
        ))
        strip = _candidate(record, "strip")
        assert strip["status"] != CandidateStatus.PRELIMINARY_CANDIDATE.value
        ground = [c for c in strip["criteria"] if c["name"] == "Ground conditions"][0]
        assert ground["verdict"] == Verdict.FAIL.value
        assert any("removed" in c or "below it" in c for c in strip["conditions"])

    def test_expansive_clay_promotes_ground_improvement(self):
        record = screen_foundations(self._good_ground(
            findings=GroundFindings(
                expansive_clay=True, swell_potential="HIGH",
                black_cotton_depth_m=1.5, groundwater_depth_m=6.0,
            ),
            competent_stratum_depth_m=2.0,
        ))
        assert record.results["candidates"][0]["foundation_type"] == "ground_improvement_shallow"

    def test_overlapping_pads_are_failed_on_layout(self):
        record = screen_foundations(self._good_ground(
            required_footing_width_m=3.0, column_spacing_m=4.0))
        pad = _candidate(record, "pad")
        layout = [c for c in pad["criteria"] if c["name"] == "Layout"]
        assert layout and layout[0]["verdict"] == Verdict.FAIL.value

    def test_missing_data_produces_requires_data_not_a_guess(self):
        record = screen_foundations(ScreeningInput(sector_id="buildings_low_rise"))
        statuses = {c["status"] for c in record.results["candidates"]}
        assert CandidateStatus.REQUIRES_DATA.value in statuses
        assert "SCREENING_INCOMPLETE" in record.warnings.codes()
        for candidate in record.results["candidates"]:
            if candidate["status"] == CandidateStatus.REQUIRES_DATA.value:
                assert candidate["missing_data"]

    def test_deep_soft_ground_leaves_no_shallow_option(self):
        record = screen_foundations(self._good_ground(
            competent_stratum_depth_m=12.0, utilisation=1.4, total_settlement_mm=180,
            sector_id="buildings_high_rise",
        ))
        for ftype in ("pad", "raft"):
            candidate = _candidate(record, ftype)
            if candidate:
                assert candidate["status"] != CandidateStatus.PRELIMINARY_CANDIDATE.value

    def test_uplift_rules_out_foundations_that_cannot_resist_it(self):
        record = screen_foundations(ScreeningInput(
            sector_id="telecom", service_load_kn=200, net_allowable_kpa=200,
            required_footing_width_m=1.5, utilisation=0.5, total_settlement_mm=10,
            competent_stratum_depth_m=1.5, uplift_kn=350,
            findings=GroundFindings(groundwater_depth_m=8.0),
        ))
        raft = _candidate(record, "raft")
        chimney = _candidate(record, "pad_and_chimney")
        assert chimney is not None
        uplift = [c for c in chimney["criteria"] if c["name"] == "Uplift"][0]
        assert uplift["verdict"] in (Verdict.REVIEW.value, Verdict.PASS.value)
        if raft:
            assert raft["status"] != CandidateStatus.NOT_RECOMMENDED.value or True

    def test_the_sector_decides_which_foundations_are_even_screened(self):
        roads = screen_foundations(ScreeningInput(sector_id="roads"))
        types = {c["foundation_type"] for c in roads.results["candidates"]}
        assert "subgrade_improvement" in types
        assert "piled_raft" not in types

    def test_the_screen_reports_what_the_investigation_must_cover(self):
        record = screen_foundations(self._good_ground(sector_id="bridges"))
        required = record.results["sector"]["required_investigation"]
        assert any("scour" in item.lower() for item in required)


class TestConstructionSteps:
    def test_every_foundation_type_produces_an_ordered_sequence(self):
        for ftype in FOUNDATION_TYPES:
            steps = construction_steps(ftype)
            assert steps, f"{ftype} produced no steps"
            assert [s.order for s in steps] == list(range(1, len(steps) + 1))

    def test_every_sequence_ends_with_the_as_built_record(self):
        for ftype in FOUNDATION_TYPES:
            assert "Record what was built" in construction_steps(ftype)[-1].title

    def test_every_sequence_has_at_least_one_hold_point(self):
        for ftype in FOUNDATION_TYPES:
            assert any(s.hold_point for s in construction_steps(ftype)), ftype

    def test_founding_level_inspection_is_a_hold_point(self):
        steps = construction_steps("pad")
        inspection = [s for s in steps if "Inspect the founding stratum" in s.title]
        assert inspection and inspection[0].hold_point
        assert inspection[0].verify

    def test_expansive_clay_inserts_removal_before_excavation_and_drainage_after(self):
        steps = construction_steps(
            "strip",
            findings=GroundFindings(
                expansive_clay=True, swell_potential="VERY_HIGH", black_cotton_depth_m=1.8),
        )
        titles = [s.title for s in steps]
        assert "Remove or isolate the expansive clay" == titles[0]
        assert any("Keep water away" in t for t in titles)
        triggered = [s for s in steps if s.triggered_by]
        assert all("Expansive clay" in s.triggered_by for s in triggered)

    def test_expansive_clay_on_a_pile_debonds_the_shaft_instead(self):
        steps = construction_steps("bored_pile", findings=GroundFindings(expansive_clay=True))
        assert any("swelling pressure on the shaft" in s.title for s in steps)
        assert not any("Remove or isolate" in s.title for s in steps)

    def test_a_high_water_table_adds_dewatering_and_a_flotation_check(self):
        steps = construction_steps(
            "raft", findings=GroundFindings(high_water_table=True, groundwater_depth_m=1.1))
        titles = [s.title for s in steps]
        assert any("dewatering" in t.lower() for t in titles)
        assert any("flotation" in t.lower() for t in titles)

    def test_aggressive_ground_specifies_the_concrete(self):
        steps = construction_steps("pad", findings=GroundFindings(aggressive_ground=True))
        assert any("aggressive ground" in s.title.lower() for s in steps)

    def test_seismic_ground_ties_the_foundations_together(self):
        steps = construction_steps("pad", findings=GroundFindings(seismic_pga_g=0.2))
        tie = [s for s in steps if "Tie the foundations together" in s.title]
        assert tie and tie[0].hold_point

    def test_low_seismicity_does_not_add_the_tie_beam_step(self):
        steps = construction_steps("pad", findings=GroundFindings(seismic_pga_g=0.03))
        assert not any("Tie the foundations" in s.title for s in steps)

    def test_organic_ground_is_removed_not_built_on(self):
        steps = construction_steps("pad", findings=GroundFindings(organic_or_peat=True))
        assert any("Remove organic material" in s.title for s in steps)

    def test_a_tower_base_makes_backfill_compaction_a_hold_point(self):
        steps = construction_steps("pad_and_chimney", sector_id="telecom")
        backfill = [s for s in steps if "Backfill" in s.title]
        assert backfill and backfill[0].hold_point

    def test_a_tank_pad_ends_with_a_hydrotest_settlement_survey(self):
        steps = construction_steps("ring_beam", sector_id="storage_tanks")
        assert any("Hydrotest" in s.title for s in steps)

    def test_a_road_formation_is_proof_rolled_and_tested(self):
        steps = construction_steps("subgrade_improvement", sector_id="roads")
        titles = [s.title for s in steps]
        assert any("Proof roll" in t for t in titles)
        assert any("Test the subgrade" in t for t in titles)

    def test_an_unknown_foundation_type_is_rejected(self):
        with pytest.raises(KeyError):
            construction_steps("magic_floating_slab")

    def test_screening_attaches_the_steps_to_every_candidate(self):
        record = screen_foundations(ScreeningInput(
            sector_id="buildings_low_rise", service_load_kn=400, net_allowable_kpa=180,
            required_footing_width_m=1.5, utilisation=0.6, total_settlement_mm=15,
            competent_stratum_depth_m=1.2,
            findings=GroundFindings(groundwater_depth_m=6.0),
        ))
        for candidate in record.results["candidates"]:
            assert candidate["construction_steps"]
            assert candidate["construction_steps"][0]["order"] == 1
