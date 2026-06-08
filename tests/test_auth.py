"""
Tests for the authentication module.
"""
import pytest


class TestLogin:

    def test_login_success(self, client, admin_employee):
        resp = client.post("/api/v1/auth/login", json={
            "email": admin_employee.email,
            "password": "Admin@1234",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0
        assert "@test.com" in data["employee"]["email"]
        assert data["employee"]["role"] == "ADMIN"
        assert data["employee"]["emp_code"].startswith("ADM") or \
               data["employee"]["emp_code"].startswith("EMP")

    def test_login_wrong_password(self, client, admin_employee):
        resp = client.post("/api/v1/auth/login", json={
            "email": admin_employee.email,
            "password": "WrongPassword",
        })
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"]

    def test_login_unknown_email(self, client):
        resp = client.post("/api/v1/auth/login", json={
            "email": "nobody@test.com",
            "password": "anything",
        })
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["detail"]

    def test_login_inactive_account(self, client, db, admin_employee):
        admin_employee.is_active = False
        db.add(admin_employee)
        db.commit()

        resp = client.post("/api/v1/auth/login", json={
            "email": admin_employee.email,
            "password": "Admin@1234",
        })
        assert resp.status_code == 401
        assert "deactivated" in resp.json()["detail"].lower()

    def test_login_missing_fields(self, client):
        resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com"})
        assert resp.status_code == 422


class TestRefresh:

    def test_refresh_success(self, client, admin_employee):
        login_resp = client.post("/api/v1/auth/login", json={
            "email": admin_employee.email, "password": "Admin@1234",
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        refresh_token = login_resp.json()["refresh_token"]

        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] > 0

    def test_refresh_invalid_token(self, client):
        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "not.a.real.token"})
        assert resp.status_code == 401

    def test_refresh_with_access_token_rejected(self, client, admin_employee):
        login_resp = client.post("/api/v1/auth/login", json={
            "email": admin_employee.email, "password": "Admin@1234",
        })
        assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
        access_token = login_resp.json()["access_token"]

        resp = client.post("/api/v1/auth/refresh", json={"refresh_token": access_token})
        assert resp.status_code == 401


class TestGetMe:

    def test_get_me_authenticated(self, admin_client, admin_employee):
        resp = admin_client.get("/api/v1/auth/me")
        assert resp.status_code == 200
        data = resp.json()
        assert "@test.com" in data["email"]
        assert data["role"] == "ADMIN"
        assert data["emp_code"]
        assert "hashed_password" not in data

    def test_get_me_unauthenticated(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    def test_get_me_invalid_token(self, client):
        resp = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401


class TestChangePassword:

    def test_change_password_success(self, employee_client, regular_employee):
        resp = employee_client.post("/api/v1/auth/change-password", json={
            "current_password": "Emp@12345",
            "new_password": "NewEmp@9999",
            "confirm_password": "NewEmp@9999",
        })
        assert resp.status_code == 200
        assert "successfully" in resp.json()["message"].lower()

    def test_change_password_wrong_current(self, employee_client):
        resp = employee_client.post("/api/v1/auth/change-password", json={
            "current_password": "WrongOldPass",
            "new_password": "NewEmp@9999",
            "confirm_password": "NewEmp@9999",
        })
        assert resp.status_code == 400
        assert "incorrect" in resp.json()["detail"].lower()

    def test_change_password_mismatch(self, employee_client):
        resp = employee_client.post("/api/v1/auth/change-password", json={
            "current_password": "Emp@12345",
            "new_password": "NewPass@1234",
            "confirm_password": "DifferentPass@1234",
        })
        assert resp.status_code == 422

    def test_change_password_same_as_current(self, employee_client):
        resp = employee_client.post("/api/v1/auth/change-password", json={
            "current_password": "Emp@12345",
            "new_password": "Emp@12345",
            "confirm_password": "Emp@12345",
        })
        assert resp.status_code == 400
        assert "different" in resp.json()["detail"].lower()

    def test_change_password_too_short(self, employee_client):
        resp = employee_client.post("/api/v1/auth/change-password", json={
            "current_password": "Emp@12345",
            "new_password": "short",
            "confirm_password": "short",
        })
        assert resp.status_code == 422