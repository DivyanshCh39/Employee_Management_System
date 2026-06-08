"""
Tests for the audit log module.
"""
import pytest


class TestAuditAccessControl:

    def test_admin_can_list_logs(self, admin_client, admin_employee):
        resp = admin_client.get("/api/v1/audit/logs")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)

    def test_hr_cannot_list_logs(self, hr_client):
        resp = hr_client.get("/api/v1/audit/logs")
        assert resp.status_code == 403

    def test_manager_cannot_list_logs(self, manager_client):
        resp = manager_client.get("/api/v1/audit/logs")
        assert resp.status_code == 403

    def test_employee_cannot_list_logs(self, employee_client):
        resp = employee_client.get("/api/v1/audit/logs")
        assert resp.status_code == 403

    def test_unauthenticated_cannot_list_logs(self, client):
        resp = client.get("/api/v1/audit/logs")
        assert resp.status_code == 401


class TestAuditLogCreation:

    def test_login_writes_audit_log(self, client, admin_employee, admin_client):
        resp = admin_client.get("/api/v1/audit/logs?action=USER_LOGIN")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        login_logs = [item for item in data["items"] if item["action"] == "USER_LOGIN"]
        assert len(login_logs) >= 1
        assert login_logs[0]["entity_type"] == "Employee"

    def test_employee_create_writes_audit_log(self, admin_client):
        admin_client.post("/api/v1/employees/", json={
            "full_name": "Audit Test Staff",
            "email": "auditstaff@test.com",
            "password": "Audit@1234",
        })
        resp = admin_client.get("/api/v1/audit/logs?action=EMPLOYEE_CREATED")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        created_logs = [i for i in data["items"] if i["action"] == "EMPLOYEE_CREATED"]
        assert len(created_logs) >= 1
        assert created_logs[0]["entity_type"] == "Employee"

    def test_leave_apply_writes_audit_log(self, client, all_tokens, seed_leave_configs):
        from datetime import date, timedelta
        future = str(date.today() + timedelta(days=5))
        future2 = str(date.today() + timedelta(days=6))

        client.headers["Authorization"] = f"Bearer {all_tokens['employee']}"
        client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": future,
            "end_date": future2,
        })

        client.headers["Authorization"] = f"Bearer {all_tokens['admin']}"
        resp = client.get("/api/v1/audit/logs?action=LEAVE_APPLIED")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_leave_approve_writes_audit_log(self, client, all_tokens, seed_leave_configs):
        from datetime import date, timedelta
        start = str(date.today() + timedelta(days=15))
        end = str(date.today() + timedelta(days=16))

        client.headers["Authorization"] = f"Bearer {all_tokens['employee']}"
        leave_resp = client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": start,
            "end_date": end,
        })
        leave_id = leave_resp.json()["id"]

        client.headers["Authorization"] = f"Bearer {all_tokens['admin']}"
        client.patch(f"/api/v1/leaves/{leave_id}/approve")

        resp = client.get("/api/v1/audit/logs?action=LEAVE_APPROVED")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1


class TestAuditFilters:

    def test_filter_by_entity_type(self, admin_client, admin_employee):
        resp = admin_client.get("/api/v1/audit/logs?entity_type=Employee")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["entity_type"] == "Employee"

    def test_filter_by_actor_id(self, admin_client, admin_employee):
        resp = admin_client.get(f"/api/v1/audit/logs?actor_id={admin_employee.id}")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["actor_id"] == admin_employee.id

    def test_pagination(self, admin_client, admin_employee):
        resp = admin_client.get("/api/v1/audit/logs?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["page_size"] == 2


class TestGetAuditLog:

    def test_admin_can_get_log_by_id(self, admin_client, admin_employee):
        list_resp = admin_client.get("/api/v1/audit/logs?page_size=1")
        items = list_resp.json()["items"]
        if not items:
            pytest.skip("No audit log entries present")
        log_id = items[0]["id"]

        resp = admin_client.get(f"/api/v1/audit/logs/{log_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == log_id
        assert "action" in data
        assert "entity_type" in data
        assert "created_at" in data

    def test_not_found(self, admin_client):
        resp = admin_client.get("/api/v1/audit/logs/99999")
        assert resp.status_code == 404

    def test_non_admin_cannot_get_log(self, hr_client):
        resp = hr_client.get("/api/v1/audit/logs/1")
        assert resp.status_code == 403