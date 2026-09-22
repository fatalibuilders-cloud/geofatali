"""The acceptance path, end to end, against a real database.

Spec section 62. One user registers, creates a project, logs a borehole and
its strata, records an SPT, runs the calculations, screens the foundations,
picks one, issues a report — and an engineer reviews it. Everything that
happens is stored, and everything stored can be read back.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text


def test_a_whole_project_from_registration_to_signed_report(client, session):
    # ── 1. Register ──────────────────────────────────────────────────────
    registration = client.post("/api/v1/auth/register", json={
        "email": "site.engineer@example.com",
        "password": "a-long-enough-passphrase",
        "name": "Site Engineer",
    })
    assert registration.status_code == 201
    headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}

    # ── 2. Create the project ────────────────────────────────────────────
    project = client.post("/api/v1/projects", json={
        "name": "Syokimau Apartments",
        "sector": "buildings_low_rise",
        "design_standard": "kebs",
        "client_name": "A. Client",
        "country": "Kenya",
        "administrative_area": "Machakos County",
        "latitude": -1.36, "longitude": 36.95,
        "floors": 4,
    }, headers=headers).json()
    pid = project["id"]

    # ── 3. Log a borehole and its strata ─────────────────────────────────
    borehole = client.post(f"/api/v1/projects/{pid}/boreholes", json={
        "code": "BH-01", "total_depth_m": 6.0,
        "groundwater_depth_m": 8.0, "groundwater_observed": True,
        "drilling_method": "Hand auger",
    }, headers=headers).json()
    bid = borehole["id"]

    strata = [
        (0.0, 0.3, "TOPSOIL", None),
        (0.3, 2.5, "BLACK COTTON CLAY", "CH"),
        (2.5, 4.0, "STIFF CLAY", "CL"),
        (4.0, 6.0, "WEATHERED ROCK", None),
    ]
    for top, bottom, description, uscs in strata:
        response = client.post(
            f"/api/v1/projects/{pid}/boreholes/{bid}/layers",
            json={"top_depth_m": top, "bottom_depth_m": bottom,
                  "description": description, "uscs_class": uscs,
                  "classification_source": "FIELD"},
            headers=headers)
        assert response.status_code == 201, response.text

    logged = client.get(
        f"/api/v1/projects/{pid}/boreholes/{bid}/layers", headers=headers).json()
    assert [layer["description"] for layer in logged] == [s[2] for s in strata]

    # ── 4. Record an SPT ─────────────────────────────────────────────────
    spt = client.post(f"/api/v1/projects/{pid}/boreholes/{bid}/spt", json={
        "depth_m": 1.5, "n_raw": 6, "energy_ratio_percent": 60,
        "rod_length_m": 3, "effective_overburden_kpa": 25,
    }, headers=headers).json()
    assert spt["n_raw"] == 6
    assert spt["n1_60"] is not None

    # ── 5. Bearing capacity, undrained, from a correlated Cu ─────────────
    bearing = client.post(
        f"/api/v1/projects/{pid}/calculations/bearing-capacity",
        json={
            "soil": {"unit_weight_kn_m3": 16.5, "cohesion_kpa": 20.3,
                     "analysis": "undrained", "cohesion_source": "ESTIMATED"},
            "foundation": {"width_m": 1.5, "depth_m": 1.5, "shape": "square"},
            "groundwater": {"groundwater_depth_m": 8.0, "groundwater_observed": True},
            "method": "hansen", "standard": "kebs",
        },
        headers=headers).json()
    assert bearing["status"] == "CALCULATED"
    assert bearing["preliminary"] is True, "a correlated Cu must keep the result preliminary"

    # ── 6. Size a footing ────────────────────────────────────────────────
    sizing = client.post(f"/api/v1/projects/{pid}/calculations/footing", json={
        "service_load_kn": 700,
        "soil": {"unit_weight_kn_m3": 16.5, "cohesion_kpa": 20.3,
                 "analysis": "undrained", "cohesion_source": "ESTIMATED"},
        "depth_m": 1.5, "shape": "square", "method": "hansen", "standard": "kebs",
    }, headers=headers).json()
    assert sizing["status"] in ("CALCULATED", "INSUFFICIENT_DATA")

    # ── 7. Screen the foundations ────────────────────────────────────────
    screening = client.post(
        f"/api/v1/projects/{pid}/calculations/foundation-options",
        json={
            "sector": "buildings_low_rise",
            "service_load_kn": 700,
            "net_allowable_kpa": sizing["results"].get("net_allowable_capacity_kpa", 100),
            "required_footing_width_m": sizing["results"].get("width_m", 1.8),
            "utilisation": sizing["results"].get("utilisation", 0.9),
            "total_settlement_mm": 45,
            "column_spacing_m": 4.5,
            "competent_stratum_depth_m": 2.5,
            "trial_founding_depth_m": 1.5,
            "findings": {
                "expansive_clay": True, "swell_potential": "VERY_HIGH",
                "black_cotton_depth_m": 2.5, "groundwater_depth_m": 8.0,
                "seismic_pga_g": 0.07,
            },
        },
        headers=headers).json()
    assert screening["status"] == "CALCULATED"
    candidates = screening["results"]["candidates"]
    assert len(candidates) > 1, "a screen offers options, never one approved answer"

    # The expansive clay must drive the ranking and the first step on site.
    top = candidates[0]
    assert top["foundation_type"] in ("ground_improvement_shallow", "raft")
    first_step = top["construction_steps"][0]
    assert "expansive clay" in (first_step["triggered_by"] or "").lower() or \
           "weak layer" in first_step["title"].lower()

    # ── 8. Choose one ────────────────────────────────────────────────────
    chosen = client.post(
        f"/api/v1/projects/{pid}/foundations/{screening['foundation_ids'][0]}/select",
        headers=headers).json()
    assert chosen["status"] == "selected"
    assert chosen["construction_steps"]

    # ── 9. Issue the report ──────────────────────────────────────────────
    report = client.post(f"/api/v1/projects/{pid}/reports", headers=headers).json()
    assert report["revision"] == 1
    assert "PRELIMINARY" in report["banner"]

    document = session.execute(
        text("SELECT document FROM reports WHERE id = :i"), {"i": report["id"]}
    ).scalar_one()
    markdown = document["markdown"]
    assert "Syokimau Apartments" in markdown
    assert "not a geotechnical site investigation" in markdown
    assert "Recommendations for further investigation" in markdown

    # ── 10. Everything that happened is on the record ────────────────────
    audit = client.get(f"/api/v1/projects/{pid}/audit", headers=headers).json()
    actions = {entry["action"] for entry in audit}
    assert {
        "project.created", "borehole.created", "soil_layer.created",
        "calculation.run", "foundation.selected", "report.generated",
    } <= actions

    history = client.get(f"/api/v1/projects/{pid}/calculations", headers=headers).json()
    assert len(history) == 3  # bearing, sizing, screening — all kept

    # ── 11. And the stored calculation is still reproducible ─────────────
    stored = client.get(
        f"/api/v1/projects/{pid}/calculations/{bearing['id']}", headers=headers).json()
    assert stored["inputs"]["soil"]["cohesion_kpa"] == 20.3
    assert stored["inputs"]["method"] == "hansen"
    assert stored["engine_version"]
    assert stored["provenance"]["cohesion_kpa"]["source"] == "ESTIMATED"


def test_the_report_only_loses_its_banner_after_a_registered_engineer_signs(
    client, account, engineer, project, shared_org, session
):
    client.post(
        f"/api/v1/projects/{project['id']}/calculations/bearing-capacity",
        json={"soil": {"cohesion_kpa": 25, "friction_angle_deg": 24, "unit_weight_kn_m3": 18},
              "foundation": {"width_m": 2.0, "depth_m": 1.5, "shape": "square"}},
        headers=account["headers"])

    before = client.post(
        f"/api/v1/projects/{project['id']}/reports", headers=account["headers"]).json()
    assert "PRELIMINARY" in before["banner"]

    # The project owner cannot clear it themselves.
    refused = client.post(
        f"/api/v1/projects/{project['id']}/reviews",
        json={"status": "APPROVED"}, headers=account["headers"])
    assert refused.status_code == 403

    client.post(
        f"/api/v1/projects/{project['id']}/reviews",
        json={"status": "APPROVED", "comments": "Reviewed."},
        headers=engineer["headers"])

    after = client.post(
        f"/api/v1/projects/{project['id']}/reports", headers=account["headers"]).json()
    assert "PRELIMINARY" not in after["banner"]
    assert after["revision"] == before["revision"] + 1, "a new banner means a new revision"
