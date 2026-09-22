"""Calculations, reports, reviews: the properties that make records evidence."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

BEARING = {
    "soil": {"cohesion_kpa": 25, "friction_angle_deg": 24, "unit_weight_kn_m3": 18},
    "foundation": {"width_m": 2.0, "depth_m": 1.5, "length_m": 2.0, "shape": "square"},
    "groundwater": {"groundwater_depth_m": 5.0},
    "method": "terzaghi",
    "safety_factor": 3.0,
}


def _run_bearing(client, account, project, **overrides):
    payload = {**BEARING, **overrides}
    return client.post(
        f"/api/v1/projects/{project['id']}/calculations/bearing-capacity",
        json=payload, headers=account["headers"])


class TestCalculationHistory:
    def test_a_run_is_stored_whole(self, client, account, project):
        response = _run_bearing(client, account, project)
        assert response.status_code == 201
        body = response.json()
        assert body["status"] == "CALCULATED"
        assert body["results"]["ultimate_capacity_kpa"] == pytest.approx(986.9, rel=0.01)

        stored = client.get(
            f"/api/v1/projects/{project['id']}/calculations/{body['id']}",
            headers=account["headers"]).json()
        # Everything needed to reproduce it, years later.
        assert stored["method"] == "terzaghi"
        assert stored["engine_version"]
        assert stored["standard"]
        assert stored["inputs"]["soil"]["cohesion_kpa"] == 25
        assert stored["provenance"]

    def test_a_refusal_is_stored_too(self, client, account, project):
        """"We could not calculate this, and here is what was missing" is history."""
        response = _run_bearing(client, account, project, soil={"unit_weight_kn_m3": 18})
        assert response.status_code == 201
        assert response.json()["status"] == "INSUFFICIENT_DATA"

        history = client.get(
            f"/api/v1/projects/{project['id']}/calculations", headers=account["headers"]).json()
        assert history[0]["status"] == "INSUFFICIENT_DATA"
        assert any(w["severity"] == "CRITICAL" for w in history[0]["warnings"])

    def test_re_running_adds_to_the_history_rather_than_replacing(self, client, account, project):
        _run_bearing(client, account, project, method="terzaghi")
        _run_bearing(client, account, project, method="vesic")
        history = client.get(
            f"/api/v1/projects/{project['id']}/calculations",
            headers=account["headers"]).json()
        assert len(history) == 2
        assert {h["method"] for h in history} == {"terzaghi", "vesic"}

    def test_the_history_can_be_filtered_by_type(self, client, account, project):
        _run_bearing(client, account, project)
        client.post(
            f"/api/v1/projects/{project['id']}/calculations/footing",
            json={"service_load_kn": 800,
                  "soil": {"cohesion_kpa": 25, "friction_angle_deg": 24, "unit_weight_kn_m3": 18},
                  "depth_m": 1.5, "shape": "square"},
            headers=account["headers"])
        only = client.get(
            f"/api/v1/projects/{project['id']}/calculations?calculation_type=footing_sizing",
            headers=account["headers"]).json()
        assert len(only) == 1
        assert only[0]["calculation_type"] == "footing_sizing"

    def test_a_preliminary_result_is_flagged_as_stored(self, client, account, project):
        response = _run_bearing(client, account, project)
        assert response.json()["preliminary"] is True  # cohesion source defaults to USER

    def test_running_a_calculation_is_audited(self, client, account, project):
        _run_bearing(client, account, project)
        audit = client.get(
            f"/api/v1/projects/{project['id']}/audit", headers=account["headers"]).json()
        assert any(e["action"] == "calculation.run" for e in audit)


class TestImmutability:
    """The database refuses, not just the application."""

    def test_a_stored_calculation_cannot_be_updated(self, client, account, project, migrated):
        body = _run_bearing(client, account, project).json()
        with pytest.raises((IntegrityError, DBAPIError)) as exc:
            with migrated.begin() as conn:
                conn.execute(
                    text("UPDATE calculations SET results = '{}'::jsonb WHERE id = :i"),
                    {"i": body["id"]},
                )
        assert "append-only" in str(exc.value)

    def test_a_stored_calculation_cannot_be_deleted(self, client, account, project, migrated):
        body = _run_bearing(client, account, project).json()
        with pytest.raises((IntegrityError, DBAPIError)):
            with migrated.begin() as conn:
                conn.execute(text("DELETE FROM calculations WHERE id = :i"), {"i": body["id"]})

    def test_the_refusal_explains_why(self, client, account, project, migrated):
        body = _run_bearing(client, account, project).json()
        with pytest.raises((IntegrityError, DBAPIError)) as exc:
            with migrated.begin() as conn:
                conn.execute(
                    text("UPDATE calculations SET method = 'vesic' WHERE id = :i"),
                    {"i": body["id"]},
                )
        message = str(exc.value)
        assert "evidence of what was calculated" in message
        assert "new revision" in message

    def test_an_audit_entry_cannot_be_rewritten(self, client, account, project, migrated):
        _run_bearing(client, account, project)
        with pytest.raises((IntegrityError, DBAPIError)):
            with migrated.begin() as conn:
                conn.execute(text("UPDATE audit_log SET action = 'nothing.happened'"))

    def test_there_is_no_update_function_to_call(self):
        from app.repositories import engineering

        assert not hasattr(engineering, "update_calculation")
        assert not hasattr(engineering, "update_report")


class TestReportRevisions:
    def test_a_report_is_issued_as_revision_one(self, client, account, project):
        _run_bearing(client, account, project)
        response = client.post(
            f"/api/v1/projects/{project['id']}/reports", headers=account["headers"])
        assert response.status_code == 201
        assert response.json()["revision"] == 1

    def test_issuing_again_creates_a_new_revision_not_an_edit(self, client, account, project):
        _run_bearing(client, account, project)
        first = client.post(
            f"/api/v1/projects/{project['id']}/reports", headers=account["headers"]).json()
        second = client.post(
            f"/api/v1/projects/{project['id']}/reports", headers=account["headers"]).json()
        assert (first["revision"], second["revision"]) == (1, 2)
        assert first["id"] != second["id"]

        listed = client.get(
            f"/api/v1/projects/{project['id']}/reports", headers=account["headers"]).json()
        assert [r["revision"] for r in listed] == [2, 1]  # both kept

    def test_an_unreviewed_report_carries_the_preliminary_banner(self, client, account, project):
        _run_bearing(client, account, project)
        report = client.post(
            f"/api/v1/projects/{project['id']}/reports", headers=account["headers"]).json()
        assert "PRELIMINARY" in report["banner"]

    def test_the_report_is_built_from_the_stored_calculations(
        self, client, account, project, session
    ):
        _run_bearing(client, account, project)
        client.post(f"/api/v1/projects/{project['id']}/reports", headers=account["headers"])
        document = session.execute(
            text("SELECT document FROM reports WHERE project_id = :p"),
            {"p": project["id"]},
        ).scalar_one()
        markdown = document["markdown"]
        assert "bearing_capacity" in markdown
        assert "terzaghi" in markdown
        assert "not a geotechnical site investigation" in markdown


class TestReviewGate:
    """Approval is the most consequential state change in the product."""

    def test_an_ordinary_account_cannot_approve(self, client, account, project):
        response = client.post(
            f"/api/v1/projects/{project['id']}/reviews",
            json={"status": "APPROVED", "comments": "Looks fine to me"},
            headers=account["headers"])
        assert response.status_code == 403
        assert "registered engineer" in response.json()["detail"]

    def test_an_ordinary_account_may_still_leave_comments(self, client, account, project):
        response = client.post(
            f"/api/v1/projects/{project['id']}/reviews",
            json={"status": "COMMENTS", "comments": "Please check the water table"},
            headers=account["headers"])
        assert response.status_code == 201
        assert response.json()["signed_at"] is None

    def test_an_engineer_can_approve_and_the_approval_is_signed(
        self, client, engineer, project, shared_org
    ):
        response = client.post(
            f"/api/v1/projects/{project['id']}/reviews",
            json={"status": "APPROVED", "comments": "Reviewed against BH-01."},
            headers=engineer["headers"])
        assert response.status_code == 201, response.text
        assert response.json()["signed_at"] is not None
        assert response.json()["status"] == "APPROVED"

    def test_an_approved_report_names_who_signed_it(
        self, client, account, engineer, project, shared_org, session
    ):
        client.post(
            f"/api/v1/projects/{project['id']}/calculations/bearing-capacity",
            json=BEARING, headers=account["headers"])
        client.post(
            f"/api/v1/projects/{project['id']}/reviews",
            json={"status": "APPROVED", "comments": "Reviewed against BH-01."},
            headers=engineer["headers"])

        report = client.post(
            f"/api/v1/projects/{project['id']}/reports", headers=account["headers"]).json()
        assert "PRELIMINARY" not in report["banner"]
        assert "REVIEWED" in report["banner"]

        document = session.execute(
            text("SELECT document FROM reports WHERE id = :i"), {"i": report["id"]}
        ).scalar_one()
        assert "EBK/PE/1234" in document["markdown"]

    def test_the_database_refuses_an_approval_with_no_signature(self, migrated, session):
        user_id = session.execute(
            text("INSERT INTO users (email, password_hash, role, registration_no) "
                 "VALUES ('sig@example.com', 'x', 'engineer', 'EBK/1') RETURNING id")
        ).scalar_one()
        project_id = session.execute(
            text("INSERT INTO projects (name, created_by) VALUES ('P', :u) RETURNING id"),
            {"u": user_id},
        ).scalar_one()
        session.commit()
        with pytest.raises((IntegrityError, DBAPIError)):
            with migrated.begin() as conn:
                conn.execute(
                    text("INSERT INTO reviews (project_id, reviewer_id, status) "
                         "VALUES (:p, :u, 'APPROVED')"),
                    {"p": project_id, "u": user_id},
                )

    def test_approving_is_audited_as_its_own_action(self, client, account, project):
        client.post(
            f"/api/v1/projects/{project['id']}/reviews",
            json={"status": "REJECTED", "comments": "Insufficient investigation"},
            headers=account["headers"])
        audit = client.get(
            f"/api/v1/projects/{project['id']}/audit", headers=account["headers"]).json()
        assert any(e["action"] == "review.rejected" for e in audit)


class TestFoundationScreeningPersistence:
    def test_candidates_are_stored_with_their_construction_steps(self, client, account, project):
        response = client.post(
            f"/api/v1/projects/{project['id']}/calculations/foundation-options",
            json={
                "sector": "buildings_low_rise",
                "service_load_kn": 400, "net_allowable_kpa": 180,
                "required_footing_width_m": 1.5, "utilisation": 0.6,
                "total_settlement_mm": 15, "competent_stratum_depth_m": 1.2,
                "findings": {"expansive_clay": True, "swell_potential": "HIGH",
                             "black_cotton_depth_m": 1.8, "groundwater_depth_m": 6.0},
            },
            headers=account["headers"])
        assert response.status_code == 201
        assert response.json()["foundation_ids"]

    def test_selecting_a_foundation_is_a_persons_decision_and_is_recorded(
        self, client, account, project
    ):
        screening = client.post(
            f"/api/v1/projects/{project['id']}/calculations/foundation-options",
            json={"sector": "buildings_low_rise", "service_load_kn": 400,
                  "net_allowable_kpa": 180, "required_footing_width_m": 1.5,
                  "utilisation": 0.6, "total_settlement_mm": 15,
                  "competent_stratum_depth_m": 1.2,
                  "findings": {"groundwater_depth_m": 6.0}},
            headers=account["headers"]).json()

        chosen = screening["foundation_ids"][0]
        response = client.post(
            f"/api/v1/projects/{project['id']}/foundations/{chosen}/select",
            headers=account["headers"])
        assert response.status_code == 200
        assert response.json()["status"] == "selected"
        assert response.json()["construction_steps"]

        audit = client.get(
            f"/api/v1/projects/{project['id']}/audit", headers=account["headers"]).json()
        assert any(e["action"] == "foundation.selected" for e in audit)

    def test_only_one_foundation_is_selected_at_a_time(self, client, account, project, session):
        screening = client.post(
            f"/api/v1/projects/{project['id']}/calculations/foundation-options",
            json={"sector": "buildings_low_rise", "service_load_kn": 400,
                  "net_allowable_kpa": 180, "required_footing_width_m": 1.5,
                  "utilisation": 0.6, "total_settlement_mm": 15,
                  "competent_stratum_depth_m": 1.2,
                  "findings": {"groundwater_depth_m": 6.0}},
            headers=account["headers"]).json()
        ids = screening["foundation_ids"]
        for foundation_id in ids[:2]:
            client.post(
                f"/api/v1/projects/{project['id']}/foundations/{foundation_id}/select",
                headers=account["headers"])
        selected = session.execute(
            text("SELECT count(*) FROM foundations WHERE project_id = :p AND status = 'selected'"),
            {"p": project["id"]},
        ).scalar_one()
        assert selected == 1
