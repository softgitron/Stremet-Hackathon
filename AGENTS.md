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

```bash
cd my_django_setup/myproject
python3 manage.py test
```

Note: The test files exist but contain no tests yet (`Ran 0 tests`).

### Running system checks (lint-equivalent)

```bash
cd my_django_setup/myproject
python3 manage.py check
```

There is no dedicated linter (flake8/ruff/pylint) configured in the repo.

### Database

SQLite (`db.sqlite3`) — no external database needed. Run `python3 manage.py migrate` after any model changes.

### Known issues

- The `customer` and `manufacturer` portal views reference templates (`customer/customer_login.html`, `customer/customer_tracking.html`, `manufacturer/manufacturer_panel.html`) that don't exist yet; those portals return HTTP 500. The admin portal and home dashboard work correctly.
- There is no `requirements.txt` or dependency manifest in the repo. Dependencies are: `django==6.0.3` and `pillow`.

### URL structure

| Path | App | Purpose |
|---|---|---|
| `/` | home | Landing page with links to the 3 portals |
| `/portal/admin/` | administrator | Create steel orders |
| `/portal/customer/` | customer | Customer order tracking (templates missing) |
| `/portal/production/` | manufacturer | Production stage management (templates missing) |
| `/admin/` | Django built-in admin | Database admin UI |
