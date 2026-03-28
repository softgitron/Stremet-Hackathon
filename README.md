# Stremet — Sheet Metal Manufacturing System

Django application for quotations, manufacturing plans, work orders, warehouse management, and role-based portals. The HTTP API is versioned under `/api/v1/` and documented with OpenAPI 3 (Swagger UI).

For a detailed walkthrough of all features, see [USER_GUIDE.md](my_django_setup/myproject/USER_GUIDE.md).

## Prerequisites

- **Python** 3.10+ (3.12 recommended; the project targets Django 6.x)
- **pip**

## Quick start

From the repository root:

```bash
cd my_django_setup/myproject
```

Create and activate a virtual environment (recommended):

```bash
python -m venv .venv
```

- **Windows (PowerShell):** `.venv\Scripts\Activate.ps1`
- **macOS/Linux:** `source .venv/bin/activate`

Install dependencies:

```bash
pip install -r requirements.txt
```

Apply database migrations:

```bash
python manage.py migrate
```

Create an administrator account (for Django admin and API session login):

```bash
python manage.py createsuperuser
```

Run the development server:

```bash
python manage.py runserver
```

Open **http://127.0.0.1:8000/** in your browser.

## Useful URLs (development)

| Path | Description |
|------|-------------|
| `/` | Home — portal entry points |
| `/admin/` | Django admin (models, users, `UserProfile`) |
| `/accounts/login/` | Session login (browsable API and authenticated API calls) |
| `/api/v1/docs/` | Swagger UI (OpenAPI) |
| `/api/v1/schema/` | OpenAPI schema (JSON/YAML) |
| `/api/v1/` | REST API root (requires authentication by default) |
| `/portal/customer/` | Customer portal (guest order lookup or logged-in dashboard) |
| `/portal/customer/upload/` | Customer self-service design upload |
| `/portal/sales/` | Sales workspace (quotes, revenue, design requests) |
| `/portal/design/` | Designer workspace (plans, blocks, requests) |
| `/portal/production/` | Manufacturing (work orders, step execution, machines) |
| `/portal/warehouse/` | Warehouse (inventory, pick lists, locations) |
| `/portal/ops/` | Operations admin (system KPIs, audit, notifications) |
| `/portal/admin/` | Legacy demo order form |

Legacy redirects: `/api/docs/` and `/api/schema/` redirect to the v1 paths.

## Customer portal login

For the full customer UI (quotes, orders, documents, design upload), a user needs a **`core.UserProfile`** with:

- **Role** set to **Customer**
- **Customer** set to the correct **`core.Customer`** record

Create or edit this in **Django admin** after the first migration.

## API usage

- Default API permission is **authenticated**. Use **session** (log in via `/accounts/login/` then call the API in the same browser) or **HTTP Basic** with a user account.
- List endpoints support pagination: `?page=1&page_size=25` (max `page_size` is 100).
- Filtering and ordering vary by resource; see Swagger UI under `/api/v1/docs/`.
- 88+ REST API endpoints covering all entities and workflow actions.

---

## Testing

The project includes three levels of automated testing: unit tests, API integration tests, and end-to-end browser tests.

### Prerequisites for testing

```bash
cd my_django_setup/myproject
pip install -r requirements.txt
pip install pytest pytest-django requests playwright
python -m playwright install chromium
python -m playwright install-deps  # system libraries for Chromium
```

### 1. Django Unit Tests (91 tests)

Tests models, services (quote lifecycle, cost calculation, work order generation, scheduling), API viewsets, and portal views.

```bash
cd my_django_setup/myproject
python manage.py test core.tests
```

Verbose output:

```bash
python manage.py test core.tests --verbosity=2
```

**Test modules:**

| Module | Covers |
|--------|--------|
| `core/tests/test_models.py` | BaseEntity UUID/revision, Customer, Part, Quote, Machine, Warehouse, UserProfile, PermissionGrant |
| `core/tests/test_services.py` | Quote snapshots, versioning, transitions, cost calculation, work order creation, scheduling, resource estimation, pick lists, audit logging |
| `core/tests/test_api.py` | REST API CRUD for all entities, custom actions (transition, recalculate, set-state, start/complete/block steps), authentication enforcement |
| `core/tests/test_views.py` | All portal template views (home, sales, design, warehouse, admin, customer, manufacturer), API docs, guest order lookup |

### 2. API Integration Tests (65 tests)

End-to-end API tests using pytest-django with the DRF test client. Tests realistic multi-step workflows.

```bash
cd my_django_setup/myproject
python -m pytest tests_integration/ -v
```

**Test modules:**

| Module | Covers |
|--------|--------|
| `test_quote_lifecycle.py` | Quote creation with lines, version snapshots, version comparison, full approval lifecycle, rejection, cost calculation with BOM, recalc flag, threaded discussions, design support requests |
| `test_manufacturing.py` | Plan + step CRUD, step I/O materials, step artifacts, resource estimation, design block create/version, hierarchical BOM, BOM-change recalc triggering |
| `test_production.py` | Work order generation with steps, snapshot immutability, idempotent WO creation, auto-scheduling, manual schedule override, step start/complete/block, completion %, pick list generation, delay tracking |
| `test_machines.py` | Machine CRUD, state transitions (available/busy/maintenance/offline), invalid state rejection, state change audit, utilization report, maintenance scheduling and completion |
| `test_warehouse.py` | Location and item creation, hierarchical locations, stock inbound/outbound, low-stock endpoint, batch/lot tracking, stock movement history |
| `test_quality_audit.py` | Quality report creation (pass/fail), traceability queries, audit log entries on transitions, audit log API filtering, CSV export, notification creation and read marking, RBAC customer scoping, permission grants |
| `test_files_documents.py` | Stored file upload, file versioning, file search, quote attachment upload |

### 3. Playwright E2E Tests (31 tests)

Browser-based tests using Python + Playwright (Chromium headless). Tests realistic user flows through the web UI and API.

```bash
cd my_django_setup/myproject
python -m pytest tests_e2e/ -v -p no:django
```

The E2E tests automatically start a Django dev server on port 8111, seed test data, and run Chromium in headless mode.

**Test modules:**

| Module | Covers |
|--------|--------|
| `test_portal_navigation.py` | Home dashboard loads, navbar links to all 6 portals, Sales KPIs and quote table, Design plans and blocks, Warehouse inventory and locations, Admin system KPIs and machine fleet |
| `test_customer_flow.py` | Guest entry page, guest order lookup, customer dashboard with quotes/orders, design upload page, self-service design submission |
| `test_manufacturing_flow.py` | Manufacturing panel with work orders, machine list, work order detail page with steps, back navigation |
| `test_full_order_flow.py` | **Complete lifecycle**: create customer → plan → steps → quote → lines → cost calc → approve → work order → schedule → pick list → execute all steps with QC → verify 100% → portal check → audit log. Also: customer self-service upload flow |
| `test_api_docs.py` | Swagger UI loads, OpenAPI schema has 80+ paths, unauthenticated access blocked |

### Running all tests

```bash
cd my_django_setup/myproject

# Unit tests
python manage.py test core.tests --verbosity=2

# Integration tests
python -m pytest tests_integration/ -v

# E2E tests (starts its own server)
python -m pytest tests_e2e/ -v -p no:django
```

### System checks (lint equivalent)

```bash
python manage.py check
```

No dedicated linter (flake8/ruff/pylint) is configured; Django system checks validate models, URLs, and settings.

---

## Configuration notes

- **Database:** SQLite at `my_django_setup/myproject/db.sqlite3` by default (`settings.py`).
- **Uploaded files:** served under `MEDIA_URL` in development; stored under the `media/` directory next to `manage.py`.
- **Large uploads:** `DATA_UPLOAD_MAX_MEMORY_SIZE` is raised for CAD-sized files (up to 500 MB); tune your reverse proxy in production.

## Production

This repository is configured for **local development** (`DEBUG = True`, insecure `SECRET_KEY`). Before any public deployment, change the secret key, set `DEBUG = False`, configure `ALLOWED_HOSTS`, use a production database, and serve static/media securely.

## Project structure

```
my_django_setup/myproject/
├── manage.py
├── requirements.txt
├── pytest.ini
├── USER_GUIDE.md              # Comprehensive user guide
├── myproject/                  # Django project settings
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── core/                       # Main application
│   ├── models/                 # 37 models across 8 modules
│   ├── views.py                # 37 DRF viewsets + custom actions
│   ├── serializers.py          # 39 serializers
│   ├── services.py             # Business logic (lifecycle, cost, scheduling)
│   ├── urls.py                 # REST API router
│   ├── admin.py                # All models registered
│   └── tests/                  # Unit tests (91 tests)
├── home/                       # Portal dashboard views + templates
├── customer/                   # Customer self-service portal
├── manufacturer/               # Manufacturing portal
├── administrator/              # Legacy admin form
├── tests_integration/          # API integration tests (65 tests)
└── tests_e2e/                  # Playwright E2E tests (31 tests)
```
