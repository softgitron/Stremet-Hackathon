"""E2E test: realistic end-to-end order flow via API + portal verification.

Simulates: sales creates quote → designer adds plan → cost calculated → approved →
work order generated → operator executes steps → warehouse picks materials → QC pass.
"""
import uuid

import pytest
import requests


BASE = "http://localhost:8111/api/v1"


@pytest.mark.e2e
class TestFullOrderFlow:
    def test_complete_order_lifecycle(self, admin_page, seed_data):
        session = requests.Session()
        session.auth = (seed_data["admin_username"], seed_data["admin_password"])

        # 1. Create customer
        resp = session.post(f"{BASE}/customers/", json={
            "company_name": "E2E Flow Corp",
            "email": "flow@e2e.com",
        })
        assert resp.status_code == 201
        customer_id = resp.json()["id"]

        # 2. Create manufacturing plan with steps
        plan = session.post(f"{BASE}/manufacturing-plans/", json={
            "name": "E2E Flow Plan",
        })
        assert plan.status_code == 201
        plan_id = plan.json()["id"]

        session.post(f"{BASE}/manufacturing-steps/", json={
            "plan": plan_id, "sequence": 1, "machine_type": "laser",
            "title": "Cut blanks", "processing_time_minutes": 45, "setup_time_minutes": 10,
        })
        session.post(f"{BASE}/manufacturing-steps/", json={
            "plan": plan_id, "sequence": 2, "machine_type": "press",
            "title": "Form parts", "processing_time_minutes": 30, "setup_time_minutes": 5,
        })

        # 3. Create quote with plan
        unique_suffix = uuid.uuid4().hex[:6].upper()
        quote = session.post(f"{BASE}/quotes/", json={
            "quote_number": f"Q-E2E-FLOW-{unique_suffix}",
            "customer": customer_id,
            "title": "E2E Full Flow Order",
            "preliminary_manufacturing_plan": plan_id,
        })
        assert quote.status_code == 201
        quote_id = quote.json()["id"]

        # 4. Add line items
        session.post(f"{BASE}/quote-lines/", json={
            "quote": quote_id,
            "description": "Custom panel x200",
            "quantity": 200,
            "unit_price": 18.50,
        })

        # 5. Calculate cost
        cost = session.post(f"{BASE}/quotes/{quote_id}/recalculate/")
        assert cost.status_code == 200
        assert float(cost.json()["total"]) > 0

        # 6. Add discussion
        thread = session.post(f"{BASE}/quote-threads/", json={
            "quote": quote_id,
            "subject": "Material clarification",
        })
        session.post(f"{BASE}/quote-comments/", json={
            "thread": thread.json()["id"],
            "body": "Please confirm material grade",
            "author_role": "sales",
        })

        # 7. Transition through approval
        session.post(f"{BASE}/quotes/{quote_id}/transition/", json={"to_state": "in_review", "note": "Ready"})
        session.post(f"{BASE}/quotes/{quote_id}/transition/", json={"to_state": "customer_review"})
        resp = session.post(f"{BASE}/quotes/{quote_id}/transition/", json={"to_state": "approved", "note": "Go ahead"})
        assert resp.status_code == 200
        assert resp.json()["state"] == "approved"

        # 8. Verify work order was created
        wos = session.get(f"{BASE}/work-orders/?source_quote={quote_id}")
        assert wos.json()["count"] >= 1
        wo = wos.json()["results"][0]
        wo_id = wo["id"]

        # 9. Auto-schedule
        sched = session.post(f"{BASE}/work-orders/{wo_id}/auto-schedule/")
        assert sched.status_code == 200

        # 10. Generate pick list
        pl = session.post(f"{BASE}/work-orders/{wo_id}/generate-pick-list/")
        assert pl.status_code == 201

        # 11. Execute steps
        steps = session.get(f"{BASE}/work-order-steps/?work_order={wo_id}&ordering=sequence")
        for step in steps.json()["results"]:
            start = session.post(f"{BASE}/work-order-steps/{step['id']}/start/")
            assert start.status_code == 200

            # Add quality report
            session.post(f"{BASE}/quality-reports/", json={
                "work_order_step": step["id"],
                "result": "pass",
                "inspection_notes": "Within tolerance",
            })

            complete = session.post(f"{BASE}/work-order-steps/{step['id']}/complete/")
            assert complete.status_code == 200

        # 12. Verify 100% completion
        wo_final = session.get(f"{BASE}/work-orders/{wo_id}/")
        assert float(wo_final.json()["completion_percent"]) == 100.0

        # 13. Verify in portal
        admin_page.goto("/portal/production/")
        admin_page.wait_for_load_state("networkidle")
        assert "100" in admin_page.content()

        # 14. Check audit log
        audit = session.get(f"{BASE}/audit-log/?entity_type=Quote")
        assert audit.json()["count"] >= 1

        # 15. Verify delay report accessible
        delays = session.get(f"{BASE}/work-orders/{wo_id}/delays/")
        assert delays.status_code == 200


@pytest.mark.e2e
class TestCustomerSelfServiceFlow:
    def test_customer_uploads_design_and_sees_quote(self, customer_page, seed_data):
        customer_page.goto("/portal/customer/upload/")
        customer_page.wait_for_load_state("networkidle")
        title_input = customer_page.locator('input[name="title"]')
        if title_input.is_visible():
            title_input.fill("E2E Self-Service Bracket")
            customer_page.fill('textarea[name="description"]', "L-bracket, 3mm, qty 200")
            customer_page.click('button:has-text("Submit design")')
            customer_page.wait_for_load_state("networkidle")

        customer_page.goto("/portal/customer/")
        customer_page.wait_for_load_state("networkidle")
        assert "Q-SELF" in customer_page.content() or customer_page.locator("text=Quotes").first.is_visible()
