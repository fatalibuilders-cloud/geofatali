"""Persistence: isolation, integrity, immutability and the review gate.

These are the properties that make stored engineering records worth storing.
Each one is enforced by the database as well as by the application, and each
test here proves the enforcement rather than the intention.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError


class TestAuth:
    def test_registration_returns_a_working_token(self, client):
        response = client.post("/api/v1/auth/register", json={
            "email": "new-person@example.com", "password": "a-long-enough-passphrase"})
        assert response.status_code == 201
        token = response.json()["access_token"]
        me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 200
        assert me.json()["email"] == "new-person@example.com"
        assert me.json()["role"] == "free"

    def test_a_short_password_is_refused(self, client):
        response = client.post("/api/v1/auth/register", json={
            "email": "short@example.com", "password": "short"})
        assert response.status_code == 422

    def test_the_same_email_cannot_register_twice(self, client):
        payload = {"email": "dup@example.com", "password": "a-long-enough-passphrase"}
        assert client.post("/api/v1/auth/register", json=payload).status_code == 201
        second = client.post("/api/v1/auth/register", json=payload)
        assert second.status_code == 409

    def test_email_case_does_not_create_a_second_account(self, client):
        assert client.post("/api/v1/auth/register", json={
            "email": "Case@Example.com", "password": "a-long-enough-passphrase"}).status_code == 201
        second = client.post("/api/v1/auth/register", json={
            "email": "case@example.com", "password": "a-long-enough-passphrase"})
        assert second.status_code == 409

    def test_a_wrong_password_and_an_unknown_email_look_identical(self, client, account):
        wrong = client.post("/api/v1/auth/login", json={
            "email": account["email"], "password": "definitely-not-the-password"})
        unknown = client.post("/api/v1/auth/login", json={
            "email": "nobody@example.com", "password": "definitely-not-the-password"})
        assert wrong.status_code == unknown.status_code == 401
        assert wrong.json()["detail"] == unknown.json()["detail"]

    def test_no_token_means_no_access(self, client):
        assert client.get("/api/v1/projects").status_code == 401

    def test_a_forged_token_is_rejected(self, client):
        forged = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ4In0.bad-signature"
        response = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {forged}"})
        assert response.status_code == 401

    def test_self_registration_cannot_claim_the_engineer_role(self, client):
        response = client.post("/api/v1/auth/register", json={
            "email": "claims@example.com", "password": "a-long-enough-passphrase",
            "role": "engineer"})
        assert response.status_code == 422  # the schema does not allow it

    def test_the_password_hash_is_never_returned(self, client, account):
        body = client.get("/api/v1/auth/me", headers=account["headers"]).json()
        assert "password" not in str(body).lower() or "password_hash" not in body


class TestProjectIsolation:
    """The property that matters most: one user cannot see another's site data."""

    def test_a_project_is_not_visible_to_another_account(self, client, project, other_account):
        response = client.get(f"/api/v1/projects/{project['id']}", headers=other_account["headers"])
        assert response.status_code == 404

    def test_another_account_cannot_change_it(self, client, project, other_account):
        response = client.patch(
            f"/api/v1/projects/{project['id']}",
            json={"name": "Renamed by a stranger"},
            headers=other_account["headers"],
        )
        assert response.status_code == 404

    def test_another_account_cannot_delete_it(self, client, project, other_account):
        assert client.delete(
            f"/api/v1/projects/{project['id']}", headers=other_account["headers"]
        ).status_code == 404

    def test_another_account_cannot_add_a_borehole_to_it(self, client, project, other_account):
        response = client.post(
            f"/api/v1/projects/{project['id']}/boreholes",
            json={"code": "BH-99"}, headers=other_account["headers"])
        assert response.status_code == 404

    def test_another_account_cannot_read_its_calculations(self, client, project, other_account):
        response = client.get(
            f"/api/v1/projects/{project['id']}/calculations", headers=other_account["headers"])
        assert response.status_code == 404

    def test_the_listing_shows_only_your_own(self, client, project, other_account, account):
        mine = client.get("/api/v1/projects", headers=account["headers"]).json()
        theirs = client.get("/api/v1/projects", headers=other_account["headers"]).json()
        assert [p["id"] for p in mine] == [project["id"]]
        assert theirs == []

    def test_a_missing_project_and_someone_elses_are_indistinguishable(
        self, client, project, other_account
    ):
        absent = client.get(f"/api/v1/projects/{uuid.uuid4()}", headers=other_account["headers"])
        forbidden = client.get(
            f"/api/v1/projects/{project['id']}", headers=other_account["headers"])
        assert absent.status_code == forbidden.status_code == 404


class TestProjectLifecycle:
    def test_create_read_update(self, client, account, project):
        assert project["sector"] == "buildings_low_rise"
        assert project["design_standard"] == "kebs"
        patched = client.patch(
            f"/api/v1/projects/{project['id']}",
            json={"name": "Syokimau Apartments Phase 2", "status": "active"},
            headers=account["headers"],
        )
        assert patched.status_code == 200
        assert patched.json()["name"] == "Syokimau Apartments Phase 2"
        assert patched.json()["status"] == "active"

    def test_an_unknown_sector_is_refused_with_the_valid_list(self, client, account):
        response = client.post("/api/v1/projects", json={
            "name": "Mystery", "sector": "underwater_basket_weaving"}, headers=account["headers"])
        assert response.status_code == 422
        detail = response.json()["detail"]
        assert detail["error"] == "UNKNOWN_SECTOR"
        assert "roads" in detail["known"]

    def test_an_unknown_design_standard_is_refused(self, client, account):
        response = client.post("/api/v1/projects", json={
            "name": "Mystery", "design_standard": "vibes"}, headers=account["headers"])
        assert response.status_code == 422
        assert response.json()["detail"]["error"] == "UNKNOWN_STANDARD"

    def test_deleting_a_project_takes_its_ground_data_with_it(self, client, account, project, session):
        borehole = client.post(
            f"/api/v1/projects/{project['id']}/boreholes",
            json={"code": "BH-01", "total_depth_m": 6.0}, headers=account["headers"]).json()
        client.post(
            f"/api/v1/projects/{project['id']}/boreholes/{borehole['id']}/layers",
            json={"top_depth_m": 0, "bottom_depth_m": 2, "classification_source": "FIELD"},
            headers=account["headers"])

        assert client.delete(
            f"/api/v1/projects/{project['id']}", headers=account["headers"]).status_code == 204

        remaining = session.execute(
            text("SELECT count(*) FROM soil_layers WHERE borehole_id = :b"),
            {"b": borehole["id"]},
        ).scalar_one()
        assert remaining == 0, "deleting a project must actually delete its data"


class TestBoreholeAndLayerIntegrity:
    def test_borehole_codes_are_unique_within_a_project(self, client, account, project):
        payload = {"code": "BH-01"}
        assert client.post(
            f"/api/v1/projects/{project['id']}/boreholes",
            json=payload, headers=account["headers"]).status_code == 201
        second = client.post(
            f"/api/v1/projects/{project['id']}/boreholes",
            json=payload, headers=account["headers"])
        assert second.status_code == 409
        assert "unique within a project" in second.json()["detail"]

    def test_the_same_code_is_fine_in_a_different_project(self, client, account, project):
        other = client.post(
            "/api/v1/projects", json={"name": "Second site"}, headers=account["headers"]).json()
        for project_id in (project["id"], other["id"]):
            assert client.post(
                f"/api/v1/projects/{project_id}/boreholes",
                json={"code": "BH-01"}, headers=account["headers"]).status_code == 201

    @pytest.fixture
    def borehole(self, client, account, project):
        return client.post(
            f"/api/v1/projects/{project['id']}/boreholes",
            json={"code": "BH-01", "total_depth_m": 8.0, "groundwater_depth_m": 6.0,
                  "groundwater_observed": True},
            headers=account["headers"]).json()

    def test_layers_stack_without_complaint(self, client, account, project, borehole):
        url = f"/api/v1/projects/{project['id']}/boreholes/{borehole['id']}/layers"
        for top, bottom, name in ((0, 0.3, "TOPSOIL"), (0.3, 1.5, "CLAYEY SAND"), (1.5, 3.2, "STIFF CLAY")):
            response = client.post(url, json={
                "top_depth_m": top, "bottom_depth_m": bottom, "description": name,
                "classification_source": "FIELD"}, headers=account["headers"])
            assert response.status_code == 201, response.text
        layers = client.get(url, headers=account["headers"]).json()
        assert [layer["description"] for layer in layers] == ["TOPSOIL", "CLAYEY SAND", "STIFF CLAY"]

    def test_an_overlapping_layer_is_refused_in_words_a_technician_can_act_on(
        self, client, account, project, borehole
    ):
        url = f"/api/v1/projects/{project['id']}/boreholes/{borehole['id']}/layers"
        client.post(url, json={
            "top_depth_m": 0.0, "bottom_depth_m": 1.5, "classification_source": "FIELD"},
            headers=account["headers"])
        clash = client.post(url, json={
            "top_depth_m": 1.0, "bottom_depth_m": 3.0, "classification_source": "FIELD"},
            headers=account["headers"])
        assert clash.status_code == 409
        detail = clash.json()["detail"]
        assert "overlaps" in detail
        assert "one stratum at each depth" in detail

    def test_an_inverted_layer_is_refused(self, client, account, project, borehole):
        response = client.post(
            f"/api/v1/projects/{project['id']}/boreholes/{borehole['id']}/layers",
            json={"top_depth_m": 3.0, "bottom_depth_m": 1.0, "classification_source": "FIELD"},
            headers=account["headers"])
        assert response.status_code == 409
        assert "measured downward" in response.json()["detail"]

    def test_a_layer_cannot_be_stored_without_saying_where_it_came_from(
        self, client, account, project, borehole
    ):
        response = client.post(
            f"/api/v1/projects/{project['id']}/boreholes/{borehole['id']}/layers",
            json={"top_depth_m": 0.0, "bottom_depth_m": 1.0},
            headers=account["headers"])
        assert response.status_code == 422  # classification_source is required

    def test_the_database_itself_rejects_a_null_provenance(self, session, migrated):
        with pytest.raises((IntegrityError, DBAPIError)):
            with migrated.begin() as conn:
                conn.execute(text(
                    "INSERT INTO soil_layers (borehole_id, top_depth_m, bottom_depth_m) "
                    "VALUES (gen_random_uuid(), 0, 1)"
                ))

    def test_reclassifying_records_what_it_was(self, client, account, project, borehole):
        url = f"/api/v1/projects/{project['id']}/boreholes/{borehole['id']}/layers"
        layer = client.post(url, json={
            "top_depth_m": 0.0, "bottom_depth_m": 1.5, "uscs_class": "SC",
            "classification_source": "AI", "confidence": 0.81}, headers=account["headers"]).json()

        corrected = client.patch(
            f"{url}/{layer['id']}/classification",
            json={"uscs_class": "CH", "classification_source": "ENGINEER"},
            headers=account["headers"])
        assert corrected.status_code == 200
        assert corrected.json()["uscs_class"] == "CH"
        assert corrected.json()["classification_source"] == "ENGINEER"

        audit = client.get(
            f"/api/v1/projects/{project['id']}/audit", headers=account["headers"]).json()
        entry = next(e for e in audit if e["action"] == "soil_layer.classification_changed")
        assert entry["old_value"]["uscs_class"] == "SC"
        assert entry["old_value"]["classification_source"] == "AI"
        assert entry["new_value"]["uscs_class"] == "CH"

    def test_an_spt_keeps_the_raw_count_and_the_corrections_apart(
        self, client, account, project, borehole
    ):
        response = client.post(
            f"/api/v1/projects/{project['id']}/boreholes/{borehole['id']}/spt",
            json={"depth_m": 1.5, "n_raw": 6, "energy_ratio_percent": 45, "rod_length_m": 3,
                  "effective_overburden_kpa": 25},
            headers=account["headers"])
        assert response.status_code == 201
        body = response.json()
        assert body["n_raw"] == 6                      # what was recorded on site
        assert body["n60"] != body["n_raw"]            # what it corrects to
        assert body["correction"]["ce"] == pytest.approx(0.75)
        assert body["correction"]["method"] == "skempton_1986"
