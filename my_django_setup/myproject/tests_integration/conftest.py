import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from core.models import (
    BOMNode,
    Customer,
    DesignBlockTemplate,
    InventoryItem,
    Machine,
    ManufacturingPlan,
    ManufacturingStep,
    UserProfile,
    WarehouseLocation,
)
from core.models.base import UserRole


@pytest.fixture
def admin_user(db):
    return User.objects.create_superuser("integration_admin", password="testpass123")


@pytest.fixture
def sales_user(db):
    user = User.objects.create_user("sales_user", password="testpass123")
    UserProfile.objects.create(user=user, role=UserRole.SALES)
    return user


@pytest.fixture
def designer_user(db):
    user = User.objects.create_user("designer_user", password="testpass123")
    UserProfile.objects.create(user=user, role=UserRole.DESIGNER)
    return user


@pytest.fixture
def manufacturer_user(db):
    user = User.objects.create_user("mfg_user", password="testpass123")
    UserProfile.objects.create(user=user, role=UserRole.MANUFACTURER)
    return user


@pytest.fixture
def warehouse_user(db):
    user = User.objects.create_user("wh_user", password="testpass123")
    UserProfile.objects.create(user=user, role=UserRole.WAREHOUSE)
    return user


@pytest.fixture
def customer_entity(db, admin_user):
    return Customer.objects.create(
        company_name="Integration Test Corp",
        email="inttest@corp.com",
        phone="+1-555-9999",
        billing_address="100 Test Lane",
        created_by=admin_user,
        updated_by=admin_user,
    )


@pytest.fixture
def customer_user(db, customer_entity):
    user = User.objects.create_user("customer_user", password="testpass123")
    UserProfile.objects.create(user=user, role=UserRole.CUSTOMER, customer=customer_entity)
    return user


@pytest.fixture
def api_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client


@pytest.fixture
def sales_client(sales_user):
    client = APIClient()
    client.force_authenticate(user=sales_user)
    return client


@pytest.fixture
def customer_client(customer_user):
    client = APIClient()
    client.force_authenticate(user=customer_user)
    return client


@pytest.fixture
def warehouse_location(db, admin_user):
    return WarehouseLocation.objects.create(
        code="INT-LOC-A01", name="Integration Shelf A01",
        created_by=admin_user, updated_by=admin_user,
    )


@pytest.fixture
def inventory_item(db, warehouse_location, admin_user):
    return InventoryItem.objects.create(
        sku="INT-STL-2MM", name="Steel Sheet 2mm (Integration)",
        location=warehouse_location, quantity=200, unit="sheets",
        unit_cost="12.50", created_by=admin_user, updated_by=admin_user,
    )


@pytest.fixture
def paint_item(db, warehouse_location, admin_user):
    return InventoryItem.objects.create(
        sku="INT-PNT-BLK", name="Black Paint (Integration)",
        location=warehouse_location, quantity=50, unit="liters",
        unit_cost="8.00", created_by=admin_user, updated_by=admin_user,
    )


@pytest.fixture
def machine_laser(db, admin_user):
    return Machine.objects.create(
        identifier="INT-LASER-01", name="Integration Laser",
        machine_type="laser", capacity_hours_per_day=8,
        capabilities=["cutting"], supported_operations=["laser_cut"],
        created_by=admin_user, updated_by=admin_user,
    )


@pytest.fixture
def machine_press(db, admin_user):
    return Machine.objects.create(
        identifier="INT-PRESS-01", name="Integration Press",
        machine_type="press", capacity_hours_per_day=8,
        capabilities=["bending"], supported_operations=["bend"],
        created_by=admin_user, updated_by=admin_user,
    )


@pytest.fixture
def design_block(db, admin_user):
    return DesignBlockTemplate.objects.create(
        name="INT Laser Cut Block", default_machine_type="laser",
        default_parameters={"power": 4}, version_tag="1.0.0",
        created_by=admin_user, updated_by=admin_user,
    )


@pytest.fixture
def manufacturing_plan(db, admin_user, inventory_item, paint_item, design_block):
    plan = ManufacturingPlan.objects.create(
        name="Integration Test Plan",
        created_by=admin_user, updated_by=admin_user,
    )
    ManufacturingStep.objects.create(
        plan=plan, sequence=1, machine_type="laser",
        title="Laser Cut", processing_time_minutes=45,
        setup_time_minutes=15, template_block=design_block,
        created_by=admin_user, updated_by=admin_user,
    )
    ManufacturingStep.objects.create(
        plan=plan, sequence=2, machine_type="press",
        title="Press Bend", processing_time_minutes=30,
        setup_time_minutes=10,
        created_by=admin_user, updated_by=admin_user,
    )
    BOMNode.objects.create(
        manufacturing_plan=plan, inventory_item=inventory_item,
        quantity=10, unit="sheets", sequence=1,
        created_by=admin_user, updated_by=admin_user,
    )
    BOMNode.objects.create(
        manufacturing_plan=plan, inventory_item=paint_item,
        quantity=2, unit="liters", sequence=2,
        created_by=admin_user, updated_by=admin_user,
    )
    return plan
