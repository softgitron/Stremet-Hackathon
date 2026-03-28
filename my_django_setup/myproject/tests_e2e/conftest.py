import os
import subprocess
import sys
import time

import pytest
from playwright.sync_api import sync_playwright

BASE_URL = "http://localhost:8111"
MANAGE_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "manage.py")
PROJECT_DIR = os.path.dirname(MANAGE_PY)


def _run_manage(args):
    return subprocess.run(
        [sys.executable, MANAGE_PY] + args,
        cwd=PROJECT_DIR,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "myproject.settings"},
        capture_output=True, text=True,
    )


@pytest.fixture(scope="session")
def django_server():
    _run_manage(["migrate", "--run-syncdb"])

    seed_script = """
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'myproject.settings')
django.setup()

from django.contrib.auth.models import User
from core.models import *
from core.models.base import UserRole
from core.services import compute_quote_cost, save_quote_version, transition_quote

admin, _ = User.objects.get_or_create(username='e2e_admin', defaults={'is_superuser': True, 'is_staff': True})
admin.set_password('e2e_pass_123')
admin.save()
UserProfile.objects.get_or_create(user=admin, defaults={'role': UserRole.ADMINISTRATOR})

customer, _ = Customer.objects.get_or_create(company_name='E2E Test Corp', defaults={'email': 'e2e@test.com', 'created_by': admin, 'updated_by': admin})

cust_user, _ = User.objects.get_or_create(username='e2e_customer', defaults={'is_staff': False})
cust_user.set_password('e2e_cust_123')
cust_user.save()
UserProfile.objects.get_or_create(user=cust_user, defaults={'role': UserRole.CUSTOMER, 'customer': customer})

part, _ = Part.objects.get_or_create(customer=customer, name='E2E Side Panel', defaults={'description': 'E2E test part', 'quantity': 50, 'created_by': admin, 'updated_by': admin})

loc, _ = WarehouseLocation.objects.get_or_create(code='E2E-A01', defaults={'name': 'E2E Shelf', 'created_by': admin, 'updated_by': admin})
inv, _ = InventoryItem.objects.get_or_create(sku='E2E-STL', defaults={'name': 'E2E Steel', 'location': loc, 'quantity': 100, 'unit': 'sheets', 'unit_cost': '10.00', 'created_by': admin, 'updated_by': admin})
Machine.objects.get_or_create(identifier='E2E-LASER', defaults={'name': 'E2E Laser', 'machine_type': 'laser', 'created_by': admin, 'updated_by': admin})
Machine.objects.get_or_create(identifier='E2E-PRESS', defaults={'name': 'E2E Press', 'machine_type': 'press', 'created_by': admin, 'updated_by': admin})

plan, _ = ManufacturingPlan.objects.get_or_create(name='E2E Plan', defaults={'part': part, 'created_by': admin, 'updated_by': admin})
ManufacturingStep.objects.get_or_create(plan=plan, sequence=1, defaults={'machine_type': 'laser', 'title': 'E2E Cut', 'processing_time_minutes': 30, 'setup_time_minutes': 10, 'created_by': admin, 'updated_by': admin})
BOMNode.objects.get_or_create(manufacturing_plan=plan, inventory_item=inv, defaults={'quantity': 5, 'unit': 'sheets', 'sequence': 1, 'created_by': admin, 'updated_by': admin})

q, created = Quote.objects.get_or_create(quote_number='Q-E2E-001', defaults={'customer': customer, 'title': 'E2E Test Quote', 'preliminary_manufacturing_plan': plan, 'created_by': admin, 'updated_by': admin})
if created:
    QuoteLine.objects.create(quote=q, description='E2E Panel x50', quantity=50, unit_price=20, created_by=admin, updated_by=admin)
    compute_quote_cost(q, admin)
    save_quote_version(q, admin)

q2, created = Quote.objects.get_or_create(quote_number='Q-E2E-002', defaults={'customer': customer, 'title': 'E2E Approved Quote', 'preliminary_manufacturing_plan': plan, 'created_by': admin, 'updated_by': admin})
if created:
    QuoteLine.objects.create(quote=q2, description='E2E Bracket x100', quantity=100, unit_price=5, created_by=admin, updated_by=admin)
    compute_quote_cost(q2, admin)
    transition_quote(q2, 'in_review', admin)
    transition_quote(q2, 'customer_review', admin)
    transition_quote(q2, 'approved', admin, note='E2E approved')

DesignSupportRequest.objects.get_or_create(quote=q, defaults={'description': 'E2E: Need mfg plan review', 'priority': 'high', 'status': 'open', 'created_by': admin, 'updated_by': admin})
DesignBlockTemplate.objects.get_or_create(name='E2E Laser Block', defaults={'default_machine_type': 'laser', 'version_tag': '1.0.0', 'created_by': admin, 'updated_by': admin})
print('E2E seed data created.')
"""
    result = subprocess.run(
        [sys.executable, "-c", seed_script],
        cwd=PROJECT_DIR,
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "myproject.settings"},
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print("SEED ERROR:", result.stderr)
    assert result.returncode == 0, f"Seed failed: {result.stderr}"

    proc = subprocess.Popen(
        [sys.executable, MANAGE_PY, "runserver", "0.0.0.0:8111", "--noreload"],
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "myproject.settings"},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=PROJECT_DIR,
    )
    for _ in range(30):
        try:
            import urllib.request
            urllib.request.urlopen(BASE_URL)
            break
        except Exception:
            time.sleep(0.5)
    yield proc
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="session")
def seed_data(django_server):
    return {
        "admin_username": "e2e_admin",
        "admin_password": "e2e_pass_123",
        "customer_username": "e2e_customer",
        "customer_password": "e2e_cust_123",
        "customer_name": "E2E Test Corp",
        "quote_number": "Q-E2E-001",
        "approved_quote": "Q-E2E-002",
    }


@pytest.fixture(scope="session")
def browser_context(seed_data):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            base_url=BASE_URL,
        )
        context.set_default_timeout(15000)
        yield context
        context.close()
        browser.close()


@pytest.fixture
def page(browser_context):
    pg = browser_context.new_page()
    yield pg
    pg.close()


@pytest.fixture
def admin_page(page, seed_data):
    page.goto("/accounts/login/")
    page.fill('input[name="username"]', seed_data["admin_username"])
    page.fill('input[name="password"]', seed_data["admin_password"])
    page.click('button[type="submit"]')
    page.wait_for_url("**/")
    return page


@pytest.fixture
def customer_page(page, seed_data):
    page.goto("/accounts/login/?next=/portal/customer/")
    page.fill('input[name="username"]', seed_data["customer_username"])
    page.fill('input[name="password"]', seed_data["customer_password"])
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    return page
