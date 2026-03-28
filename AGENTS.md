# AGENTS.md

## Cursor Cloud specific instructions

### Project overview

This is a Django 6.0.3 web application ("Stremet Management System") for steel manufacturing order management. It uses SQLite and has no external service dependencies. The Django project lives at `my_django_setup/myproject/`.

### Running the dev server

```bash
cd my_django_setup/myproject
python3 manage.py runserver 0.0.0.0:8000
```

### Running tests

Unit tests (91 tests):

```bash
cd my_django_setup/myproject
python3 manage.py test core.tests --verbosity=2
```

API integration tests (65 tests):

```bash
cd my_django_setup/myproject
python3 -m pytest tests_integration/ -v
```

Playwright E2E tests (31 tests, starts its own server on port 8111):

```bash
cd my_django_setup/myproject
python3 -m pytest tests_e2e/ -v -p no:django
```

### Running system checks (lint-equivalent)

```bash
cd my_django_setup/myproject
python3 manage.py check
```

There is no dedicated linter (flake8/ruff/pylint) configured in the repo.

### Database

SQLite (`db.sqlite3`) — no external database needed. Run `python3 manage.py migrate` after any model changes.

### Dependencies

Listed in `my_django_setup/myproject/requirements.txt`. Install via `pip install -r requirements.txt`.

For testing also install: `pip install pytest pytest-django requests playwright && python3 -m playwright install chromium && python3 -m playwright install-deps`

### URL structure

| Path | App | Purpose |
|---|---|---|
| `/` | home | Landing page with links to all 6 portals |
| `/portal/sales/` | home | Sales workspace (quotes, revenue, design requests) |
| `/portal/design/` | home | Designer workspace (plans, blocks, requests) |
| `/portal/customer/` | customer | Customer portal (guest order lookup or dashboard) |
| `/portal/customer/upload/` | customer | Customer self-service design upload |
| `/portal/production/` | manufacturer | Work orders, step execution, machines |
| `/portal/warehouse/` | home | Warehouse (inventory, pick lists, locations) |
| `/portal/ops/` | home | Operations admin (system KPIs, audit, notifications) |
| `/portal/admin/` | administrator | Legacy demo order form |
| `/api/v1/` | core | REST API (88+ endpoints, OpenAPI 3.0) |
| `/api/v1/docs/` | drf-spectacular | Swagger UI |
| `/admin/` | Django built-in admin | Database admin UI |
