"""Integration tests for warehouse management: inventory, stock movements, pick lists."""
import pytest
from decimal import Decimal
from core.models import InventoryItem, StockMovement

pytestmark = pytest.mark.django_db


class TestInventoryManagement:
    def test_create_location_and_item(self, api_client):
        loc = api_client.post("/api/v1/warehouse-locations/", {
            "code": "INT-WH-C01", "name": "Integration Zone C Shelf 1",
        })
        assert loc.status_code == 201

        item = api_client.post("/api/v1/inventory-items/", {
            "sku": "INT-MAT-001", "name": "Test Material",
            "location": loc.data["id"], "quantity": 500,
            "unit": "kg", "unit_cost": "3.50",
        })
        assert item.status_code == 201
        assert item.data["status"] == "available"

    def test_hierarchical_locations(self, api_client):
        parent = api_client.post("/api/v1/warehouse-locations/", {
            "code": "INT-WH-ZONE-A", "name": "Zone A",
        })
        child = api_client.post("/api/v1/warehouse-locations/", {
            "code": "INT-WH-A-01", "name": "Zone A Bin 1",
            "parent": parent.data["id"],
        })
        assert child.status_code == 201
        assert str(child.data["parent"]) == str(parent.data["id"])

    def test_adjust_stock_inbound(self, api_client, inventory_item):
        resp = api_client.post(f"/api/v1/inventory-items/{inventory_item.id}/adjust/", {
            "quantity_delta": "50",
            "movement_type": "inbound",
            "reference": "PO-12345 delivery",
        })
        assert resp.status_code == 200
        inventory_item.refresh_from_db()
        assert inventory_item.quantity == Decimal("250")
        assert StockMovement.objects.filter(
            inventory_item=inventory_item, movement_type="inbound"
        ).exists()

    def test_adjust_stock_outbound(self, api_client, inventory_item):
        resp = api_client.post(f"/api/v1/inventory-items/{inventory_item.id}/adjust/", {
            "quantity_delta": "-20",
            "movement_type": "outbound",
            "reference": "WO consumption",
        })
        assert resp.status_code == 200
        inventory_item.refresh_from_db()
        assert inventory_item.quantity == Decimal("180")

    def test_low_stock_endpoint(self, api_client, inventory_item, warehouse_location, admin_user):
        low_item = InventoryItem.objects.create(
            sku="INT-LOW-STOCK", name="Low Stock Item",
            location=warehouse_location, quantity=3, unit="pcs",
            created_by=admin_user, updated_by=admin_user,
        )
        resp = api_client.get("/api/v1/inventory-items/low-stock/?threshold=10")
        assert resp.status_code == 200
        assert resp.data["count"] >= 1
        skus = [i["sku"] for i in resp.data["items"]]
        assert "INT-LOW-STOCK" in skus

    def test_batch_lot_tracking(self, api_client, warehouse_location):
        item = api_client.post("/api/v1/inventory-items/", {
            "sku": "INT-BATCH-01", "name": "Batch Tracked Steel",
            "location": warehouse_location.id, "quantity": 100,
            "batch_or_lot": "LOT-2026-03-001",
        })
        assert item.status_code == 201
        assert item.data["batch_or_lot"] == "LOT-2026-03-001"


class TestStockMovements:
    def test_movement_history(self, api_client, inventory_item):
        api_client.post(f"/api/v1/inventory-items/{inventory_item.id}/adjust/", {
            "quantity_delta": "10", "movement_type": "inbound", "reference": "delivery",
        })
        api_client.post(f"/api/v1/inventory-items/{inventory_item.id}/adjust/", {
            "quantity_delta": "-5", "movement_type": "outbound", "reference": "production",
        })
        movements = api_client.get(f"/api/v1/stock-movements/?inventory_item={inventory_item.id}")
        assert movements.data["count"] == 2

    def test_manual_stock_movement(self, api_client, inventory_item):
        resp = api_client.post("/api/v1/stock-movements/", {
            "inventory_item": str(inventory_item.id),
            "movement_type": "adjust",
            "quantity_delta": "-3",
            "reference": "Damaged goods writeoff",
        })
        assert resp.status_code == 201
