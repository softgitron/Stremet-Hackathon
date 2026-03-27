from django.contrib.auth.models import User
from django.test import Client, TestCase

from core.models import (
    Customer,
    CustomerOrder,
    Machine,
    ManufacturingPlan,
    ManufacturingStep,
    Quote,
    UserProfile,
    WorkOrder,
)
from core.models.base import UserRole
from core.services import create_work_order_from_quote


class HomeViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("homeuser", password="pass")
        self.client.login(username="homeuser", password="pass")

    def test_dashboard(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Stremet")

    def test_portal_sales(self):
        resp = self.client.get("/portal/sales/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sales workspace")

    def test_portal_design(self):
        resp = self.client.get("/portal/design/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Design")

    def test_portal_warehouse(self):
        resp = self.client.get("/portal/warehouse/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Warehouse")

    def test_portal_admin(self):
        resp = self.client.get("/portal/ops/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Operations overview")


class CustomerPortalTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.customer = Customer.objects.create(company_name="TestCo", email="t@t.com")

    def test_guest_entry(self):
        resp = self.client.get("/portal/customer/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Customer portal")

    def test_guest_order_lookup(self):
        q = Quote.objects.create(
            quote_number="Q-GUEST", customer=self.customer,
            state=Quote.QuoteState.APPROVED
        )
        user = User.objects.create_user("wouser", password="pass")
        wo = create_work_order_from_quote(q, user)
        order = wo.customer_order
        resp = self.client.post("/portal/customer/", {"order_id": order.order_number})
        self.assertEqual(resp.status_code, 200)

    def test_guest_order_lookup_empty(self):
        resp = self.client.post("/portal/customer/", {"order_id": ""})
        self.assertEqual(resp.status_code, 302)

    def test_customer_dashboard_linked(self):
        user = User.objects.create_user("custlink", password="pass")
        UserProfile.objects.create(user=user, role=UserRole.CUSTOMER, customer=self.customer)
        self.client.login(username="custlink", password="pass")
        resp = self.client.get("/portal/customer/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "TestCo")

    def test_customer_quote_detail(self):
        user = User.objects.create_user("qdetail", password="pass")
        UserProfile.objects.create(user=user, role=UserRole.CUSTOMER, customer=self.customer)
        self.client.login(username="qdetail", password="pass")
        q = Quote.objects.create(quote_number="Q-DETAIL", customer=self.customer, title="Detail")
        resp = self.client.get(f"/portal/customer/quotes/{q.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Q-DETAIL")

    def test_customer_order_detail(self):
        user = User.objects.create_user("odetail", password="pass")
        UserProfile.objects.create(user=user, role=UserRole.CUSTOMER, customer=self.customer)
        self.client.login(username="odetail", password="pass")
        order = CustomerOrder.objects.create(
            order_number="ORD-DETAIL", customer=self.customer
        )
        resp = self.client.get(f"/portal/customer/orders/{order.order_number}/")
        self.assertEqual(resp.status_code, 200)


class ManufacturerPortalTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user("mfguser", password="pass")
        self.client.login(username="mfguser", password="pass")

    def test_manufacturer_panel(self):
        resp = self.client.get("/portal/production/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Production")

    def test_work_order_detail(self):
        customer = Customer.objects.create(company_name="WODetail", email="wd@w.com")
        q = Quote.objects.create(
            quote_number="Q-WD", customer=customer,
            state=Quote.QuoteState.APPROVED
        )
        wo = create_work_order_from_quote(q, self.user)
        resp = self.client.get(f"/portal/production/work-order/{wo.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, wo.wo_number)


class APIDocsTest(TestCase):
    def test_schema_accessible(self):
        resp = self.client.get("/api/v1/schema/")
        self.assertEqual(resp.status_code, 200)

    def test_swagger_ui(self):
        resp = self.client.get("/api/v1/docs/")
        self.assertEqual(resp.status_code, 200)

    def test_redirect_api_docs(self):
        resp = self.client.get("/api/docs/")
        self.assertEqual(resp.status_code, 302)
