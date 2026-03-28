"""Integration tests for machine management, state tracking, and maintenance."""
import pytest
from datetime import timedelta
from django.utils import timezone
from core.models import Machine, AuditLogEntry

pytestmark = pytest.mark.django_db


class TestMachineLifecycle:
    def test_create_machine(self, api_client):
        resp = api_client.post("/api/v1/machines/", {
            "identifier": "INT-M-NEW",
            "name": "New Integration Machine",
            "machine_type": "laser",
            "capabilities": ["cutting", "marking"],
            "supported_operations": ["laser_cut"],
            "capacity_hours_per_day": 10,
        }, format="json")
        assert resp.status_code == 201
        assert resp.data["state"] == "available"

    def test_state_transitions(self, api_client, machine_laser):
        for new_state in ["busy", "maintenance", "offline", "available"]:
            resp = api_client.post(f"/api/v1/machines/{machine_laser.id}/set-state/", {
                "state": new_state,
            })
            assert resp.status_code == 200
            assert resp.data["state"] == new_state

    def test_invalid_state_rejected(self, api_client, machine_laser):
        resp = api_client.post(f"/api/v1/machines/{machine_laser.id}/set-state/", {
            "state": "broken",
        })
        assert resp.status_code == 400

    def test_state_change_audited(self, api_client, machine_laser):
        api_client.post(f"/api/v1/machines/{machine_laser.id}/set-state/", {"state": "busy"})
        entries = AuditLogEntry.objects.filter(
            entity_type="Machine", entity_id=str(machine_laser.id), action="machine_state_change"
        )
        assert entries.exists()

    def test_utilization_report(self, api_client, machine_laser):
        resp = api_client.get(f"/api/v1/machines/{machine_laser.id}/utilization/")
        assert resp.status_code == 200
        assert "utilization_pct" in resp.data
        assert "capacity_hours_per_day" in resp.data


class TestMaintenance:
    def test_schedule_maintenance(self, api_client, machine_laser):
        now = timezone.now()
        resp = api_client.post("/api/v1/machine-maintenance/", {
            "machine": str(machine_laser.id),
            "title": "Quarterly calibration",
            "starts_at": now.isoformat(),
            "ends_at": (now + timedelta(hours=4)).isoformat(),
            "blocks_scheduling": True,
        })
        assert resp.status_code == 201
        assert resp.data["blocks_scheduling"] is True

    def test_complete_maintenance(self, api_client, machine_laser):
        now = timezone.now()
        maint = api_client.post("/api/v1/machine-maintenance/", {
            "machine": str(machine_laser.id),
            "title": "Oil change",
            "starts_at": (now - timedelta(hours=2)).isoformat(),
            "ends_at": now.isoformat(),
        })
        api_client.patch(f"/api/v1/machine-maintenance/{maint.data['id']}/", {
            "completed": True,
        })
        updated = api_client.get(f"/api/v1/machine-maintenance/{maint.data['id']}/")
        assert updated.data["completed"] is True

    def test_active_maintenance_in_utilization(self, api_client, machine_laser):
        now = timezone.now()
        api_client.post("/api/v1/machine-maintenance/", {
            "machine": str(machine_laser.id),
            "title": "Active maintenance",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(hours=1)).isoformat(),
        })
        util = api_client.get(f"/api/v1/machines/{machine_laser.id}/utilization/")
        assert util.data["active_maintenance_windows"] == 1
