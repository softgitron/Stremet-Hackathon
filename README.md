# Stremet Hackathon — Sheet Metal Manufacturing System

Django application for quotations, manufacturing plans, work orders, warehouse data, and role-based portals. The HTTP API is versioned under `/api/v1/` and documented with OpenAPI 3 (Swagger UI).

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
| `/api/v1/schema/` | OpenAPI schema |
| `/api/v1/` | REST API root (requires authentication by default) |
| `/portal/customer/` | Customer portal (guest order lookup or logged-in dashboard) |
| `/portal/sales/`, `/portal/design/`, `/portal/warehouse/`, `/portal/ops/` | Role-oriented dashboards (summaries + API hints) |
| `/portal/production/` | Manufacturing work order list |
| `/portal/admin/` | Legacy demo order form |

Legacy redirects: `/api/docs/` and `/api/schema/` redirect to the v1 paths.

## Customer portal login

For the full customer UI (quotes, orders, documents), a user needs a **`core.UserProfile`** with:

- **Role** set to **Customer**
- **Customer** set to the correct **`core.Customer`** record

Create or edit this in **Django admin** after the first migration.

## API usage

- Default API permission is **authenticated**. Use **session** (log in via `/accounts/login/` then call the API in the same browser) or **HTTP Basic** with a user account.
- List endpoints support pagination: `?page=1&page_size=25` (max `page_size` is 100).
- Filtering and ordering vary by resource; see Swagger UI under `/api/v1/docs/`.

## Configuration notes

- **Database:** SQLite at `my_django_setup/myproject/db.sqlite3` by default (`settings.py`).
- **Uploaded files:** served under `MEDIA_URL` in development; stored under the `media/` directory next to `manage.py`.
- **Large uploads:** `DATA_UPLOAD_MAX_MEMORY_SIZE` is raised for CAD-sized files; tune your reverse proxy in production.

## Production

This repository is configured for **local development** (`DEBUG = True`, insecure `SECRET_KEY`). Before any public deployment, change the secret key, set `DEBUG = False`, configure `ALLOWED_HOSTS`, use a production database, and serve static/media securely.
