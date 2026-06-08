"""
Tests for the leave management module.
"""
import pytest
from datetime import date, timedelta


def _future(days: int) -> str:
    return str(date.today() + timedelta(days=days))


def _auth(client, token):
    client.headers["Authorization"] = f"Bearer {token}"
    return client


class TestApplyLeave:

    def test_employee_can_apply(self, employee_client, seed_leave_configs):
        resp = employee_client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(3),
            "end_date": _future(5),
            "reason": "Personal work",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "PENDING"
        assert data["total_days"] == 3.0
        assert data["leave_type"] == "CASUAL"

    def test_total_days_computed_server_side(self, employee_client, seed_leave_configs):
        resp = employee_client.post("/api/v1/leaves/", json={
            "leave_type": "SICK",
            "start_date": _future(2),
            "end_date": _future(2),
        })
        assert resp.status_code == 201
        assert resp.json()["total_days"] == 1.0

    def test_end_before_start_rejected(self, employee_client, seed_leave_configs):
        resp = employee_client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(5),
            "end_date": _future(2),
        })
        assert resp.status_code == 422

    def test_past_start_date_rejected(self, employee_client, seed_leave_configs):
        yesterday = str(date.today() - timedelta(days=1))
        resp = employee_client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": yesterday,
            "end_date": yesterday,
        })
        assert resp.status_code == 422

    def test_overlap_rejected(self, employee_client, seed_leave_configs):
        r1 = employee_client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(10),
            "end_date": _future(12),
        })
        assert r1.status_code == 201
        r2 = employee_client.post("/api/v1/leaves/", json={
            "leave_type": "SICK",
            "start_date": _future(11),
            "end_date": _future(13),
        })
        assert r2.status_code == 400
        assert "overlap" in r2.json()["detail"].lower()

    def test_all_roles_can_apply(self, client, all_tokens, seed_leave_configs):
        for role, start in [("admin", 20), ("hr", 25), ("manager", 30), ("employee", 35)]:
            _auth(client, all_tokens[role])
            resp = client.post("/api/v1/leaves/", json={
                "leave_type": "CASUAL",
                "start_date": _future(start),
                "end_date": _future(start + 1),
            })
            assert resp.status_code == 201, f"{role} apply failed: {resp.text}"

    def test_insufficient_balance_rejected(self, employee_client, seed_leave_configs):
        resp = employee_client.post("/api/v1/leaves/", json={
            "leave_type": "SICK",
            "start_date": _future(2),
            "end_date": _future(14),
        })
        assert resp.status_code == 400
        assert "balance" in resp.json()["detail"].lower()

    def test_unpaid_has_no_balance_limit(self, employee_client, seed_leave_configs):
        resp = employee_client.post("/api/v1/leaves/", json={
            "leave_type": "UNPAID",
            "start_date": _future(2),
            "end_date": _future(60),
        })
        assert resp.status_code == 201


class TestListLeaves:

    def test_employee_sees_only_own(self, client, all_tokens, seed_leave_configs):
        _auth(client, all_tokens["employee"])
        client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(50),
            "end_date": _future(51),
        })
        _auth(client, all_tokens["hr"])
        client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(55),
            "end_date": _future(56),
        })
        _auth(client, all_tokens["employee"])
        resp = client.get("/api/v1/leaves/")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_admin_sees_all(self, client, all_tokens, seed_leave_configs):
        _auth(client, all_tokens["employee"])
        client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(70),
            "end_date": _future(71),
        })
        _auth(client, all_tokens["admin"])
        resp = client.get("/api/v1/leaves/")
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    def test_filter_by_status(self, employee_client, seed_leave_configs):
        employee_client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(80),
            "end_date": _future(81),
        })
        resp = employee_client.get("/api/v1/leaves/?status=PENDING")
        assert resp.status_code == 200
        for item in resp.json()["items"]:
            assert item["status"] == "PENDING"


class TestGetLeave:

    def test_owner_can_get_own_leave(self, employee_client, seed_leave_configs):
        cr = employee_client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(6),
            "end_date": _future(7),
        })
        leave_id = cr.json()["id"]
        resp = employee_client.get(f"/api/v1/leaves/{leave_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == leave_id

    def test_employee_cannot_get_others_leave(self, client, all_tokens, seed_leave_configs):
        _auth(client, all_tokens["admin"])
        cr = client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(40),
            "end_date": _future(41),
        })
        leave_id = cr.json()["id"]
        _auth(client, all_tokens["employee"])
        resp = client.get(f"/api/v1/leaves/{leave_id}")
        assert resp.status_code == 403

    def test_not_found(self, admin_client):
        resp = admin_client.get("/api/v1/leaves/99999")
        assert resp.status_code == 404


class TestApproveLeave:

    def _apply(self, client, token, offset):
        _auth(client, token)
        resp = client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(offset),
            "end_date": _future(offset + 1),
        })
        assert resp.status_code == 201, f"Apply failed: {resp.text}"
        return resp.json()["id"]

    def test_admin_can_approve(self, client, all_tokens, seed_leave_configs):
        leave_id = self._apply(client, all_tokens["employee"], 100)
        _auth(client, all_tokens["admin"])
        resp = client.patch(f"/api/v1/leaves/{leave_id}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"
        assert resp.json()["reviewed_by_id"] is not None

    def test_hr_can_approve(self, client, all_tokens, seed_leave_configs):
        leave_id = self._apply(client, all_tokens["employee"], 105)
        _auth(client, all_tokens["hr"])
        resp = client.patch(f"/api/v1/leaves/{leave_id}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"

    def test_manager_can_approve_direct_report(self, client, all_tokens, seed_leave_configs):
        leave_id = self._apply(client, all_tokens["employee"], 110)
        _auth(client, all_tokens["manager"])
        resp = client.patch(f"/api/v1/leaves/{leave_id}/approve")
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"

    def test_employee_cannot_approve(self, client, all_tokens, seed_leave_configs):
        leave_id = self._apply(client, all_tokens["admin"], 120)
        _auth(client, all_tokens["employee"])
        resp = client.patch(f"/api/v1/leaves/{leave_id}/approve")
        assert resp.status_code == 403

    def test_approve_non_pending_rejected(self, client, all_tokens, seed_leave_configs):
        leave_id = self._apply(client, all_tokens["employee"], 130)
        _auth(client, all_tokens["admin"])
        client.patch(f"/api/v1/leaves/{leave_id}/approve")
        resp = client.patch(f"/api/v1/leaves/{leave_id}/approve")
        assert resp.status_code == 400
        assert "PENDING" in resp.json()["detail"]


class TestRejectLeave:

    def _apply_employee(self, client, token, offset):
        _auth(client, token)
        resp = client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(offset),
            "end_date": _future(offset + 1),
        })
        assert resp.status_code == 201
        return resp.json()["id"]

    def test_admin_can_reject_with_reason(self, client, all_tokens, seed_leave_configs):
        leave_id = self._apply_employee(client, all_tokens["employee"], 200)
        _auth(client, all_tokens["admin"])
        resp = client.patch(f"/api/v1/leaves/{leave_id}/reject", json={
            "rejection_reason": "Team at minimum capacity that week."
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "REJECTED"
        assert "capacity" in data["rejection_reason"]

    def test_reject_without_reason_returns_400(self, client, all_tokens, seed_leave_configs):
        leave_id = self._apply_employee(client, all_tokens["employee"], 205)
        _auth(client, all_tokens["admin"])
        resp = client.patch(f"/api/v1/leaves/{leave_id}/reject", json={
            "rejection_reason": ""
        })
        assert resp.status_code == 400

    def test_reject_without_body_returns_400_or_422(self, client, all_tokens, seed_leave_configs):
        leave_id = self._apply_employee(client, all_tokens["employee"], 210)
        _auth(client, all_tokens["admin"])
        resp = client.patch(f"/api/v1/leaves/{leave_id}/reject", json={})
        assert resp.status_code in (400, 422)


class TestCancelLeave:

    def test_employee_can_cancel_own_pending(self, employee_client, seed_leave_configs):
        cr = employee_client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(300),
            "end_date": _future(301),
        })
        leave_id = cr.json()["id"]
        resp = employee_client.delete(f"/api/v1/leaves/{leave_id}/cancel")
        assert resp.status_code == 200
        assert "cancelled" in resp.json()["message"].lower()

    def test_cancel_approved_refunds_balance(self, client, all_tokens, seed_leave_configs):
        _auth(client, all_tokens["employee"])
        cr = client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(310),
            "end_date": _future(311),
        })
        leave_id = cr.json()["id"]
        _auth(client, all_tokens["admin"])
        client.patch(f"/api/v1/leaves/{leave_id}/approve")
        _auth(client, all_tokens["employee"])
        resp = client.delete(f"/api/v1/leaves/{leave_id}/cancel")
        assert resp.status_code == 200
        assert "refunded" in resp.json()["message"].lower()

    def test_employee_cannot_cancel_others(self, client, all_tokens, seed_leave_configs):
        _auth(client, all_tokens["admin"])
        cr = client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(320),
            "end_date": _future(321),
        })
        leave_id = cr.json()["id"]
        _auth(client, all_tokens["employee"])
        resp = client.delete(f"/api/v1/leaves/{leave_id}/cancel")
        assert resp.status_code == 403

    def test_cancel_already_cancelled_rejected(self, employee_client, seed_leave_configs):
        cr = employee_client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(330),
            "end_date": _future(331),
        })
        leave_id = cr.json()["id"]
        employee_client.delete(f"/api/v1/leaves/{leave_id}/cancel")
        resp = employee_client.delete(f"/api/v1/leaves/{leave_id}/cancel")
        assert resp.status_code == 400


class TestLeaveBalances:

    def test_employee_can_view_own_balances(
        self, employee_client, regular_employee, seed_leave_configs
    ):
        employee_client.post("/api/v1/leaves/", json={
            "leave_type": "CASUAL",
            "start_date": _future(400),
            "end_date": _future(401),
        })
        resp = employee_client.get(f"/api/v1/leaves/balances/{regular_employee.id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["employee_id"] == regular_employee.id
        assert isinstance(data["balances"], list)

    def test_employee_cannot_view_others_balances(self, client, all_tokens, admin_employee):
        _auth(client, all_tokens["employee"])
        resp = client.get(f"/api/v1/leaves/balances/{admin_employee.id}")
        assert resp.status_code == 403

    def test_admin_can_view_any_balances(self, client, all_tokens, regular_employee):
        _auth(client, all_tokens["admin"])
        resp = client.get(f"/api/v1/leaves/balances/{regular_employee.id}")
        assert resp.status_code == 200