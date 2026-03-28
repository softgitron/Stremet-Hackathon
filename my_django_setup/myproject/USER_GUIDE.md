# Stremet User Guide

Comprehensive guide for the Stremet Manufacturing Management System — a sheet metal quotation, manufacturing design, production execution, and warehouse management platform.

---

## Table of Contents

1. [Getting Started](#1-getting-started)
2. [User Roles and Permissions](#2-user-roles-and-permissions)
3. [Quotation Management](#3-quotation-management)
4. [Manufacturing Design](#4-manufacturing-design)
5. [Production Execution](#5-production-execution)
6. [Machine Management](#6-machine-management)
7. [Warehouse Management](#7-warehouse-management)
8. [Quality Management](#8-quality-management)
9. [Customer Self-Service Portal](#9-customer-self-service-portal)
10. [Notifications and Audit Trail](#10-notifications-and-audit-trail)
11. [API Reference](#11-api-reference)
12. [Administration](#12-administration)

---

## 1. Getting Started

### First Login

1. Navigate to `http://localhost:8000/accounts/login/`
2. Enter credentials created via `python manage.py createsuperuser`
3. You will be redirected to the home dashboard

### Home Dashboard

The home page at `/` displays cards linking to each role-specific portal:

| Portal | Path | Purpose |
|--------|------|---------|
| Sales | `/portal/sales/` | Quotes, customer interactions, design requests |
| Designer | `/portal/design/` | Manufacturing plans, steps, BOM, design blocks |
| Customer | `/portal/customer/` | Self-service: order tracking, design uploads |
| Manufacturing | `/portal/production/` | Work orders, step execution, machine status |
| Warehouse | `/portal/warehouse/` | Inventory, picking lists, stock movements |
| Ops Admin | `/portal/ops/` | System-wide KPIs, audit log, user management |

The navigation bar at the top provides quick access to all portals, the API docs, Django admin, and logout.

---

## 2. User Roles and Permissions

### Available Roles

| Role | Code | Typical Access |
|------|------|----------------|
| Customer | `customer` | Own quotes, orders, delivery dates, design uploads |
| Sales | `sales` | All quotes, customer interactions, design requests |
| Designer | `designer` | Manufacturing plans, steps, BOM, design blocks |
| Manufacturer | `manufacturer` | Work orders, step execution, quality reports |
| Warehouse | `warehouse` | Inventory, pick lists, stock movements |
| Administrator | `administrator` | Full system access, user management, audit |

### Setting Up a User

1. Go to **Django Admin** → **Users** → create a new user
2. Go to **Django Admin** → **User profiles** → create a profile for that user
3. Set the **Role** field to the appropriate role
4. For customer users, also set the **Customer** field to link them to a company

### Permission Matrix

Administrators can configure fine-grained permissions via the API:

```
POST /api/v1/permissions/
{
  "role": "sales",
  "entity": "Quote",
  "can_read": true,
  "can_write": true,
  "can_approve": true,
  "can_delete": false
}
```

View the matrix: `GET /api/v1/permissions/`

### Data Visibility

- **Customer** users see only data belonging to their linked customer record
- **Internal** roles (sales, designer, manufacturer, warehouse) see role-filtered views
- **Administrator** and **superuser** accounts see all data

---

## 3. Quotation Management

### Quote Lifecycle

Every quote follows a state machine:

```
Draft → In Review → Customer Review → Approved → (Expired)
                  ↘ Rejected
         ↗ Draft
```

| State | Description |
|-------|-------------|
| Draft | Initial state. Sales creates the quote and adds line items |
| In Review | Internal review by sales/design team |
| Customer Review | Sent to customer for approval |
| Approved | Customer accepted. Work order is auto-generated |
| Rejected | Terminal state. Cannot be re-opened |
| Expired | Approved quote that passed its validity date |

### Creating a Quote

**Via the API:**

```bash
# Create the quote
curl -u admin:password -X POST http://localhost:8000/api/v1/quotes/ \
  -H "Content-Type: application/json" \
  -d '{
    "quote_number": "Q-2026-001",
    "customer": "<customer-uuid>",
    "title": "Side Panel Production Run",
    "currency": "EUR"
  }'

# Add line items
curl -u admin:password -X POST http://localhost:8000/api/v1/quote-lines/ \
  -H "Content-Type: application/json" \
  -d '{
    "quote": "<quote-uuid>",
    "description": "Steel side panel 100x200mm",
    "quantity": 100,
    "unit_price": 24.50
  }'
```

### Cost Calculation

The system calculates quote cost from:

- **Material cost** — from BOM nodes linked to inventory items with unit costs
- **Machine time** — processing + setup minutes from manufacturing steps × rate
- **Labor cost** — derived from machine time × labor rate
- **Overhead** — configurable percentage (default 15%) of subtotal

```bash
POST /api/v1/quotes/<id>/recalculate/
```

The response includes a full breakdown with all input values stored for audit.

### Transitioning a Quote

```bash
POST /api/v1/quotes/<id>/transition/
{
  "to_state": "in_review",
  "note": "Ready for sales review"
}
```

Each transition is logged with timestamp and user. When a quote reaches **approved**, the system automatically creates a **CustomerOrder** and **WorkOrder**.

### Versioning

Every change to a quote creates a version snapshot. You can compare versions:

```bash
# Create a snapshot manually
POST /api/v1/quotes/<id>/snapshot-version/

# Compare two versions
GET /api/v1/quotes/<id>/compare-versions/?left=1&right=2
```

### Collaboration

Quotes support threaded discussions for internal and customer communication:

```bash
# Create a discussion thread
POST /api/v1/quote-threads/
{ "quote": "<id>", "subject": "Material clarification" }

# Add a comment (supports parent for replies)
POST /api/v1/quote-comments/
{
  "thread": "<thread-id>",
  "body": "What material grade is required?",
  "author_role": "sales"
}
```

Role-based commenting supports `customer`, `sales`, `designer`, and `internal` roles.

### File Attachments

Upload CAD files, PDFs, or images to quotes:

```bash
POST /api/v1/quote-attachments/ (multipart form)
  quote=<id>
  file=@drawing.pdf
  original_name=drawing.pdf
  content_type=application/pdf
```

### Design Support Requests

Sales can request manufacturing design assistance:

```bash
POST /api/v1/design-support/
{
  "quote": "<quote-id>",
  "description": "Need manufacturing plan for custom bracket",
  "priority": "high"
}
```

Designers accept/reject/request clarification, and can attach preliminary manufacturing plans.

---

## 4. Manufacturing Design

### Manufacturing Plans

A plan defines the ordered sequence of operations to produce a part:

```bash
POST /api/v1/manufacturing-plans/
{ "name": "Side Panel Process", "part": "<part-id>" }
```

### Manufacturing Steps

Each step represents an atomic manufacturing operation:

```bash
POST /api/v1/manufacturing-steps/
{
  "plan": "<plan-id>",
  "sequence": 1,
  "machine_type": "laser",
  "title": "Laser cut outline",
  "processing_time_minutes": 45,
  "setup_time_minutes": 15
}
```

Steps support:
- **Input materials** (`/api/v1/step-inputs/`) — links to inventory items consumed
- **Output parts** (`/api/v1/step-outputs/`) — parts produced by the step
- **Artifacts** (`/api/v1/step-artifacts/`) — 3D models, G-code, SOPs, quality docs

### Bill of Materials (BOM)

BOM nodes link a manufacturing plan to inventory items with hierarchical support:

```bash
POST /api/v1/bom-nodes/
{
  "manufacturing_plan": "<plan-id>",
  "inventory_item": "<item-id>",
  "quantity": 10,
  "unit": "sheets",
  "parent": null
}
```

Child nodes reference a `parent` for nested BOM structures.

### Reusable Design Blocks

Template steps that can be reused across plans:

```bash
POST /api/v1/design-blocks/
{
  "name": "Laser Cutting",
  "default_machine_type": "laser",
  "default_parameters": {"power_kw": 4, "speed_mm_min": 3000},
  "version_tag": "1.0.0"
}
```

Assign to a step via `"template_block": "<block-id>"`.

### Resource Estimation

Auto-calculate required machine hours, labor, and materials:

```bash
POST /api/v1/manufacturing-plans/<id>/estimate-resources/
```

---

## 5. Production Execution

### Work Orders

Work orders are created automatically when a quote is approved. Each contains:

- An **immutable snapshot** of the manufacturing plan, BOM, and cost at creation time
- A **delivery deadline** and **priority**
- **Steps** cloned from the manufacturing plan

View work orders: `GET /api/v1/work-orders/`

### Auto-Scheduling

Assign steps to available machines based on machine type:

```bash
POST /api/v1/work-orders/<id>/auto-schedule/
```

The scheduler finds available machines matching each step's `machine_type` and creates `ScheduledStep` entries with planned start/end times. Steps move from `pending` to `ready`.

### Step Execution

Operators manage step lifecycle through the API:

```bash
# Start a step (reserves materials automatically)
POST /api/v1/work-order-steps/<id>/start/

# Complete a step (updates work order progress)
POST /api/v1/work-order-steps/<id>/complete/

# Block a step with an issue
POST /api/v1/work-order-steps/<id>/block/
{ "issue": "Material defect detected on sheet #45" }
```

Step statuses: `pending` → `ready` → `in_progress` → `completed` / `blocked`

### Progress Tracking

Work order completion percentage updates automatically as steps complete. View real-time progress in the Manufacturing portal or via the API.

### Delay Tracking

Compare planned vs actual timelines:

```bash
GET /api/v1/work-orders/<id>/delays/
```

Returns per-step delays and overall order delay in hours/days.

### Pick Lists

Generate a picking list from the work order's BOM snapshot:

```bash
POST /api/v1/work-orders/<id>/generate-pick-list/
```

---

## 6. Machine Management

### Machine Registry

Register machines with type, capabilities, and capacity:

```bash
POST /api/v1/machines/
{
  "identifier": "LASER-01",
  "name": "Trumpf TruLaser 1030",
  "machine_type": "laser",
  "capabilities": ["cutting", "marking"],
  "supported_operations": ["laser_cut"],
  "capacity_hours_per_day": 8
}
```

### Machine States

Machines track their current state: `available`, `busy`, `maintenance`, `offline`.

```bash
POST /api/v1/machines/<id>/set-state/
{ "state": "maintenance" }
```

State changes are logged in the audit trail.

### Utilization Tracking

```bash
GET /api/v1/machines/<id>/utilization/
```

Returns capacity, scheduled workload, actual usage, utilization percentage, and active maintenance windows.

### Maintenance Scheduling

Schedule preventive maintenance that blocks the machine from scheduling:

```bash
POST /api/v1/machine-maintenance/
{
  "machine": "<machine-id>",
  "title": "Quarterly calibration",
  "starts_at": "2026-04-01T08:00:00Z",
  "ends_at": "2026-04-01T12:00:00Z",
  "blocks_scheduling": true
}
```

---

## 7. Warehouse Management

### Locations

Define a hierarchical storage layout (zones, aisles, shelves, bins):

```bash
POST /api/v1/warehouse-locations/
{ "code": "A-01", "name": "Aisle A Shelf 1" }

# Nested location
POST /api/v1/warehouse-locations/
{ "code": "A-01-B1", "name": "Bin 1", "parent": "<parent-id>" }
```

### Inventory Items

Track stock by SKU with quantity, location, status, and optional batch/lot:

```bash
POST /api/v1/inventory-items/
{
  "sku": "STL-2MM",
  "name": "Steel Sheet 2mm",
  "location": "<location-id>",
  "quantity": 200,
  "unit": "sheets",
  "unit_cost": "12.50",
  "batch_or_lot": "LOT-2026-03-001"
}
```

Statuses: `available`, `reserved`, `in_production`

### Stock Adjustments

Record inbound/outbound/adjustment movements:

```bash
POST /api/v1/inventory-items/<id>/adjust/
{
  "quantity_delta": "-20",
  "movement_type": "outbound",
  "reference": "WO-Q-2026-001 consumption"
}
```

Each adjustment creates a `StockMovement` audit record.

### Low Stock Alerts

```bash
GET /api/v1/inventory-items/low-stock/?threshold=10
```

The Warehouse portal also highlights items below threshold in the UI.

### Pick Lists

Pick lists are auto-generated from work orders. View and manage via:

- `GET /api/v1/pick-lists/` — list with status filter
- `GET /api/v1/pick-list-lines/?pick_list=<id>` — items to pick

---

## 8. Quality Management

### Quality Reports

Record inspection results per manufacturing step:

```bash
POST /api/v1/quality-reports/
{
  "work_order_step": "<step-id>",
  "machine": "<machine-id>",
  "operator": "<user-id>",
  "result": "pass",
  "inspection_notes": "All dimensions within tolerance",
  "material_batch": "LOT-2026-001"
}
```

Result values: `pass`, `fail`, `pending`

### Traceability

Each quality report links to:
- The **manufacturing step** it inspects
- The **machine** used
- The **operator** who performed the work
- The **material batch** consumed

Query for root cause analysis:

```bash
GET /api/v1/quality-reports/?machine=<id>&result=fail
GET /api/v1/quality-reports/?work_order_step=<id>
```

---

## 9. Customer Self-Service Portal

### Guest Order Lookup

Customers can track an order without logging in at `/portal/customer/`:

1. Enter the order number (e.g., `ORD-Q-2026-001`)
2. View work order status and progress

### Customer Dashboard

Logged-in customers with a linked profile see:

- **Quotes** — status, pricing, valid-until dates
- **Orders** — status, delivery deadlines
- **Documents** — attachments from their quotes

### Design Upload

Customers upload design files to request a quote at `/portal/customer/upload/`:

1. Enter a part title and description
2. Optionally attach a CAD/PDF/image file (up to 500 MB)
3. Submit — a draft quote is auto-created for the sales team to review

---

## 10. Notifications and Audit Trail

### In-App Notifications

Event-driven notifications are created automatically for:

- Quote state transitions
- Work order creation
- Step delays
- Inventory shortages (via low-stock checks)

View and manage: `GET /api/v1/notifications/`
Mark as read: `PATCH /api/v1/notifications/<id>/ { "read": true }`

### Audit Log

All state changes and user actions are recorded:

```bash
# View audit log
GET /api/v1/audit-log/?entity_type=Quote&action=quote_transition

# Export as CSV
GET /api/v1/audit-log/export/
```

Each entry includes: timestamp, user, action, entity type, entity ID, before/after state, and metadata.

---

## 11. API Reference

### Authentication

All API endpoints require authentication. Two methods:

1. **Session auth** — log in at `/accounts/login/`, then call the API from the same browser
2. **HTTP Basic** — pass `Authorization: Basic <base64(user:pass)>` header

### Pagination

List endpoints return paginated results:

```
GET /api/v1/quotes/?page=1&page_size=25
```

Max `page_size` is 100. Response includes `count`, `next`, `previous`, and `results`.

### Filtering and Search

Most endpoints support query parameter filters:

```
GET /api/v1/quotes/?state=draft&customer=<uuid>
GET /api/v1/quotes/?search=panel
GET /api/v1/quotes/?ordering=-created_at
```

### OpenAPI Documentation

- **Swagger UI**: `/api/v1/docs/`
- **OpenAPI schema** (JSON/YAML): `/api/v1/schema/`

### Complete Endpoint List

| Resource | Path | Methods |
|----------|------|---------|
| Customers | `/api/v1/customers/` | GET, POST, PUT, PATCH, DELETE |
| Parts | `/api/v1/parts/` | GET, POST, PUT, PATCH, DELETE |
| Quotes | `/api/v1/quotes/` | GET, POST, PUT, PATCH |
| Quote Lines | `/api/v1/quote-lines/` | GET, POST, PUT, PATCH, DELETE |
| Quote Transitions | `/api/v1/quote-transitions/` | GET |
| Quote Threads | `/api/v1/quote-threads/` | GET, POST, PUT, PATCH, DELETE |
| Quote Comments | `/api/v1/quote-comments/` | GET, POST, PUT, PATCH, DELETE |
| Quote Attachments | `/api/v1/quote-attachments/` | GET, POST, PUT, PATCH, DELETE |
| Quote Versions | `/api/v1/quote-versions/` | GET |
| Quote Costs | `/api/v1/quote-costs/` | GET |
| Design Support | `/api/v1/design-support/` | GET, POST, PUT, PATCH, DELETE |
| Design Support Files | `/api/v1/design-support-files/` | GET, POST, PUT, PATCH, DELETE |
| Manufacturing Plans | `/api/v1/manufacturing-plans/` | GET, POST, PUT, PATCH, DELETE |
| Manufacturing Steps | `/api/v1/manufacturing-steps/` | GET, POST, PUT, PATCH, DELETE |
| Step Inputs | `/api/v1/step-inputs/` | GET, POST, PUT, PATCH, DELETE |
| Step Outputs | `/api/v1/step-outputs/` | GET, POST, PUT, PATCH, DELETE |
| Step Artifacts | `/api/v1/step-artifacts/` | GET, POST, PUT, PATCH, DELETE |
| Design Blocks | `/api/v1/design-blocks/` | GET, POST, PUT, PATCH, DELETE |
| BOM Nodes | `/api/v1/bom-nodes/` | GET, POST, PUT, PATCH, DELETE |
| Machines | `/api/v1/machines/` | GET, POST, PUT, PATCH, DELETE |
| Machine Maintenance | `/api/v1/machine-maintenance/` | GET, POST, PUT, PATCH, DELETE |
| Warehouse Locations | `/api/v1/warehouse-locations/` | GET, POST, PUT, PATCH, DELETE |
| Inventory Items | `/api/v1/inventory-items/` | GET, POST, PUT, PATCH, DELETE |
| Orders | `/api/v1/orders/` | GET, POST, PUT, PATCH, DELETE |
| Work Orders | `/api/v1/work-orders/` | GET, POST, PATCH, PUT |
| Work Order Steps | `/api/v1/work-order-steps/` | GET, POST, PUT, PATCH, DELETE |
| Scheduled Steps | `/api/v1/scheduled-steps/` | GET, POST, PUT, PATCH, DELETE |
| Resource Estimates | `/api/v1/resource-estimates/` | GET, POST, PUT, PATCH, DELETE |
| Quality Reports | `/api/v1/quality-reports/` | GET, POST, PUT, PATCH, DELETE |
| Stored Files | `/api/v1/stored-files/` | GET, POST, PUT, PATCH, DELETE |
| Notifications | `/api/v1/notifications/` | GET, PATCH, PUT |
| Audit Log | `/api/v1/audit-log/` | GET |
| Permissions | `/api/v1/permissions/` | GET, POST, PUT, PATCH, DELETE |
| Pick Lists | `/api/v1/pick-lists/` | GET, POST, PUT, PATCH, DELETE |
| Pick List Lines | `/api/v1/pick-list-lines/` | GET, POST, PUT, PATCH, DELETE |
| Stock Movements | `/api/v1/stock-movements/` | GET, POST, PUT, PATCH, DELETE |
| User Profiles | `/api/v1/user-profiles/` | GET, PATCH, PUT |

### Custom Actions

| Action | Path | Method | Description |
|--------|------|--------|-------------|
| Transition quote | `/api/v1/quotes/<id>/transition/` | POST | State machine transition |
| Recalculate cost | `/api/v1/quotes/<id>/recalculate/` | POST | Re-run cost engine |
| Compare versions | `/api/v1/quotes/<id>/compare-versions/` | GET | Diff two version snapshots |
| Snapshot version | `/api/v1/quotes/<id>/snapshot-version/` | POST | Create version snapshot |
| Generate work order | `/api/v1/quotes/<id>/generate-work-order/` | POST | Create WO from approved quote |
| Estimate resources | `/api/v1/manufacturing-plans/<id>/estimate-resources/` | POST | Calculate resource needs |
| Set machine state | `/api/v1/machines/<id>/set-state/` | POST | Change machine availability |
| Machine utilization | `/api/v1/machines/<id>/utilization/` | GET | Utilization report |
| Auto-schedule | `/api/v1/work-orders/<id>/auto-schedule/` | POST | Assign steps to machines |
| Generate pick list | `/api/v1/work-orders/<id>/generate-pick-list/` | POST | Create pick list from BOM |
| Delay report | `/api/v1/work-orders/<id>/delays/` | GET | Planned vs actual timing |
| Start step | `/api/v1/work-order-steps/<id>/start/` | POST | Begin execution |
| Complete step | `/api/v1/work-order-steps/<id>/complete/` | POST | Mark finished |
| Block step | `/api/v1/work-order-steps/<id>/block/` | POST | Flag issue |
| Adjust stock | `/api/v1/inventory-items/<id>/adjust/` | POST | Record stock movement |
| Low stock check | `/api/v1/inventory-items/low-stock/` | GET | Items below threshold |
| Export audit log | `/api/v1/audit-log/export/` | GET | CSV download |

---

## 12. Administration

### Django Admin

Access at `/admin/` with a superuser account. All 37 core models are registered and manageable through the admin interface.

### Typical Setup Sequence

1. Create **Warehouse Locations** (zones, aisles, shelves)
2. Add **Inventory Items** (raw materials with SKU, quantity, cost)
3. Register **Machines** (identifier, type, capabilities, capacity)
4. Create **Design Block Templates** (reusable step templates)
5. Add **Customers** (company, email, address)
6. Create **User Profiles** for each system user with appropriate roles
7. Configure **Permission Grants** for each role/entity combination

### Data Model

Every entity uses:
- **UUID** primary keys (immutable)
- **Revision** numbers (auto-incremented on save)
- **Audit fields**: `created_at`, `updated_at`, `created_by`, `updated_by`
- **Explicit foreign keys** for all relationships
