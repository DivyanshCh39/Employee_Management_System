"""
Tests for the employee module.
"""
import pytest


class TestCreateEmployee:

    def test_admin_can_create(self, admin_client):
        resp = admin_client.post("/api/v1/employees/", json={
            "full_name": "New Staff",
            "email": "newstaff@test.com",
            "password": "Staff@1234",
            "role": "EMPLOYEE",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newstaff@test.com"
        assert data["full_name"] == "New Staff"
        assert data["emp_code"].startswith("EMP")
        assert "password" not in data
        assert "hashed_password" not in data

    def test_hr_can_create(self, hr_client):
        resp = hr_client.post("/api/v1/employees/", json={
            "full_name": "HR Created",
            "email": "hrcreated@test.com",
            "password": "HRCreate@1",
            "role": "EMPLOYEE",
        })
        assert resp.status_code == 201

    def test_manager_cannot_create(self, manager_client):
        resp = manager_client.post("/api/v1/employees/", json={
            "full_name": "Blocked",
            "email": "blocked@test.com",
            "password": "Blocked@1",
        })
        assert resp.status_code == 403

    def test_employee_cannot_create(self, employee_client):
        resp = employee_client.post("/api/v1/employees/", json={
            "full_name": "Self Serve",
            "email": "selfserve@test.com",
            "password": "SelfServe@1",
        })
        assert resp.status_code == 403

    def test_duplicate_email_returns_409(self, admin_client, admin_employee):
        resp = admin_client.post("/api/v1/employees/", json={
            "full_name": "Duplicate",
            "email": admin_employee.email,
            "password": "Duplicate@1",
        })
        assert resp.status_code == 409

    def test_emp_code_increments(self, admin_client, admin_employee):
        resp1 = admin_client.post("/api/v1/employees/", json={
            "full_name": "First New", "email": "first@test.com", "password": "First@123",
        })
        resp2 = admin_client.post("/api/v1/employees/", json={
            "full_name": "Second New", "email": "second@test.com", "password": "Second@123",
        })
        assert resp1.status_code == 201
        assert resp2.status_code == 201
        code1 = int(resp1.json()["emp_code"].replace("EMP", ""))
        code2 = int(resp2.json()["emp_code"].replace("EMP", ""))
        assert code2 == code1 + 1

    def test_hr_cannot_assign_admin_role(self, hr_client):
        resp = hr_client.post("/api/v1/employees/", json={
            "full_name": "Escalation",
            "email": "escalation@test.com",
            "password": "Esc@12345",
            "role": "ADMIN",
        })
        assert resp.status_code == 403

    def test_invalid_manager_id(self, admin_client):
        resp = admin_client.post("/api/v1/employees/", json={
            "full_name": "No Manager",
            "email": "nomanager@test.com",
            "password": "NoMgr@123",
            "manager_id": 99999,
        })
        assert resp.status_code == 400


class TestListEmployees:

    def test_admin_sees_all(self, admin_client, admin_employee, hr_employee, regular_employee):
        resp = admin_client.get("/api/v1/employees/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 3
        assert "items" in data
        assert "pages" in data

    def test_manager_sees_only_direct_reports(
        self, manager_client, manager_employee, regular_employee, admin_employee
    ):
        resp = manager_client.get("/api/v1/employees/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] >= 1
        for item in data["items"]:
            assert item["manager_id"] == manager_employee.id

    def test_employee_cannot_list(self, employee_client):
        resp = employee_client.get("/api/v1/employees/")
        assert resp.status_code == 403

    def test_filter_by_role(self, admin_client, admin_employee, hr_employee, manager_employee):
        resp = admin_client.get("/api/v1/employees/?role=HR")
        assert resp.status_code == 200
        data = resp.json()
        for item in data["items"]:
            assert item["role"] == "HR"

    def test_search_by_name(self, admin_client, admin_employee):
        resp = admin_client.get("/api/v1/employees/?search=System+Admin")
        assert resp.status_code == 200
        data = resp.json()
        assert any("admin" in item["email"] for item in data["items"])

    def test_pagination(self, admin_client, admin_employee, hr_employee, manager_employee, regular_employee):
        resp = admin_client.get("/api/v1/employees/?page=1&page_size=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) <= 2
        assert data["page"] == 1
        assert data["page_size"] == 2


class TestGetEmployee:

    def test_admin_can_get_any(self, admin_client, regular_employee):
        resp = admin_client.get(f"/api/v1/employees/{regular_employee.id}")
        assert resp.status_code == 200
        assert "@test.com" in resp.json()["email"]

    def test_employee_can_get_self(self, employee_client, regular_employee):
        resp = employee_client.get(f"/api/v1/employees/{regular_employee.id}")
        assert resp.status_code == 200

    def test_employee_cannot_get_others(self, client, all_tokens, admin_employee):
        client.headers["Authorization"] = f"Bearer {all_tokens['employee']}"
        resp = client.get(f"/api/v1/employees/{admin_employee.id}")
        assert resp.status_code == 403

    def test_manager_can_get_direct_report(self, client, all_tokens, regular_employee):
        client.headers["Authorization"] = f"Bearer {all_tokens['manager']}"
        resp = client.get(f"/api/v1/employees/{regular_employee.id}")
        assert resp.status_code == 200

    def test_manager_cannot_get_unrelated_employee(self, client, all_tokens, admin_employee):
        client.headers["Authorization"] = f"Bearer {all_tokens['manager']}"
        resp = client.get(f"/api/v1/employees/{admin_employee.id}")
        assert resp.status_code == 403

    def test_not_found(self, admin_client):
        resp = admin_client.get("/api/v1/employees/99999")
        assert resp.status_code == 404


class TestUpdateEmployee:

    def test_admin_can_update(self, admin_client, regular_employee):
        resp = admin_client.patch(
            f"/api/v1/employees/{regular_employee.id}",
            json={"full_name": "Updated Name"},
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"

    def test_hr_can_update(self, hr_client, regular_employee):
        resp = hr_client.patch(
            f"/api/v1/employees/{regular_employee.id}",
            json={"phone": "+91-9999999999"},
        )
        assert resp.status_code == 200
        assert resp.json()["phone"] == "+91-9999999999"

    def test_hr_cannot_update_admin(self, hr_client, admin_employee):
        resp = hr_client.patch(
            f"/api/v1/employees/{admin_employee.id}",
            json={"full_name": "Hacked Admin"},
        )
        assert resp.status_code == 403

    def test_patch_is_partial(self, admin_client, regular_employee):
        original_email = regular_employee.email
        resp = admin_client.patch(
            f"/api/v1/employees/{regular_employee.id}",
            json={"full_name": "Partial Update Only"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["full_name"] == "Partial Update Only"
        assert data["email"] == original_email

    def test_self_manager_rejected(self, admin_client, regular_employee):
        resp = admin_client.patch(
            f"/api/v1/employees/{regular_employee.id}",
            json={"manager_id": regular_employee.id},
        )
        assert resp.status_code == 400


class TestDeactivateReactivate:

    def test_admin_can_deactivate(self, client, all_tokens, regular_employee):
        client.headers["Authorization"] = f"Bearer {all_tokens['admin']}"
        resp = client.delete(f"/api/v1/employees/{regular_employee.id}")
        assert resp.status_code == 200
        assert "deactivated" in resp.json()["message"].lower()

    def test_hr_cannot_deactivate(self, client, all_tokens, regular_employee):
        client.headers["Authorization"] = f"Bearer {all_tokens['hr']}"
        resp = client.delete(f"/api/v1/employees/{regular_employee.id}")
        assert resp.status_code == 403

    def test_cannot_self_deactivate(self, admin_client, admin_employee):
        resp = admin_client.delete(f"/api/v1/employees/{admin_employee.id}")
        assert resp.status_code == 400

    def test_admin_can_reactivate(self, admin_client, db, regular_employee):
        regular_employee.is_active = False
        db.add(regular_employee)
        db.commit()

        resp = admin_client.post(f"/api/v1/employees/{regular_employee.id}/activate")
        assert resp.status_code == 200
        assert resp.json()["is_active"] is True

    def test_reactivate_already_active(self, admin_client, regular_employee):
        resp = admin_client.post(f"/api/v1/employees/{regular_employee.id}/activate")
        assert resp.status_code == 400