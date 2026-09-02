# TradeFlow API Test Sheet

Base URL: `http://127.0.0.1:8000`  
Swagger UI: <http://127.0.0.1:8000/api/docs/>

## Demo data

| Role | Email | Password | Customer ID |
| --- | --- | --- | --- |
| Standard customer | `standard@tradeflow.local` | `LocalCustomer!2026` | `1` |
| Wholesale customer | `wholesale@tradeflow.local` | `LocalCustomer!2026` | `2` |
| Staff/admin | `admin@tradeflow.local` | `LocalAdmin!2026` | N/A |

A fresh database contains `SKU-A` (₹100, stock 100), `SKU-B` (₹250, stock 75), and `SKU-C`
(₹499.99, stock 25). Their initial IDs are normally `1`, `2`, and `3`; confirm them with the product
list before creating an order.

## Common request rules

Protected endpoints require:

```http
Authorization: Bearer <access-token>
```

JSON requests require `Content-Type: application/json`. JWT endpoints do not require an
`X-CSRFTOKEN` header. In Swagger's **Authorize** dialog, paste only the access token. Access tokens
last 15 minutes; refresh tokens last one day and rotate when refreshed.

## Endpoint reference

| Method | Path | Access | Parameters | Success |
| --- | --- | --- | --- | --- |
| `GET` | `/api/v1/health/` | Public | None | `200` |
| `POST` | `/api/v1/auth/token/` | Public | JSON: `email`, `password` | `200` |
| `POST` | `/api/v1/auth/token/refresh/` | Public | JSON: `refresh` | `200` |
| `POST` | `/api/v1/auth/token/blacklist/` | Public | JSON: `refresh` | `200` |
| `GET` | `/api/v1/products/` | Authenticated | Query: `search`, `ordering`, `page`, `page_size` | `200` |
| `GET` | `/api/v1/products/{id}/` | Authenticated | Path: integer product `id` | `200` |
| `GET` | `/api/v1/orders/` | Customer/staff | Query: `page`, `page_size`; staff: `customer_id`, `status` | `200` |
| `POST` | `/api/v1/orders/` | Customer only | Header: `Idempotency-Key`; JSON: `items` | `201`/`200` |
| `GET` | `/api/v1/orders/{id}/` | Owner/staff | Path: order UUID `id` | `200` |
| `POST` | `/api/v1/orders/{id}/cancel/` | Owner/staff | Path: order UUID `id`; no body | `200` |
| `GET` | `/api/v1/orders/summary/` | Customer only | None | `200` |

## Authentication bodies

Login:

```json
{
  "email": "standard@tradeflow.local",
  "password": "LocalCustomer!2026"
}
```

The response contains `access` and `refresh`. Refresh a token with:

```json
{
  "refresh": "<refresh-token>"
}
```

The refresh response contains a new `access` and `refresh`; use the newest refresh token afterward.
Send that same body to `/auth/token/blacklist/` to log out. A blacklisted refresh token returns `401`
if used again.

## Product parameters

`GET /products/` supports:

| Parameter | Rule | Example |
| --- | --- | --- |
| `search` | Searches SKU, name, and description | `?search=Product A` |
| `ordering` | `name`, `price`, or `stock_quantity`; prefix `-` for descending | `?ordering=-price` |
| `page` | Positive integer | `?page=1` |
| `page_size` | 1–100; default 20 | `?page_size=10` |

Example: `/api/v1/products/?search=Product&ordering=-price&page=1&page_size=10`.

Lists use the pagination shape `count`, `next`, `previous`, and `results`. Product fields are `id`,
`sku`, `name`, `description`, `price`, `currency`, `stock_quantity`, `is_available`, and `updated_at`.
Only active products are exposed.

## Order parameters

### Create an order

`Idempotency-Key` is required, cannot be blank, and has a maximum length of 128 characters.

```http
Idempotency-Key: standard-order-001
```

```json
{
  "items": [
    {"product_id": 1, "quantity": 2},
    {"product_id": 2, "quantity": 1}
  ]
}
```

`items` must be a non-empty array. Both fields are required positive integers, and a product may
appear only once. The first successful submission returns `201`. Repeating the same key and payload
returns the same order with `200` and `Idempotent-Replayed: true`. Reusing the key with a different
payload returns `409`.

Order responses contain the UUID `id`, customer, status, item snapshots, subtotal, discount rate,
discount amount, total, currency, idempotency key, and timestamps. Save the UUID for detail and
cancellation requests.

### List orders

All users may supply `page` and `page_size` (maximum 100). Staff may additionally supply:

| Parameter | Values | Example |
| --- | --- | --- |
| `customer_id` | Positive integer | `?customer_id=1` |
| `status` | `PLACED` or `CANCELLED` | `?status=PLACED` |

Example: `/api/v1/orders/?customer_id=1&status=PLACED&page_size=10`. Customers always receive only
their own orders; customer-supplied staff filters cannot expose another account.

### Cancel and summary

`POST /orders/{order-uuid}/cancel/` takes no body. The first call restores stock and marks the order
`CANCELLED`. Repeating it returns `200` with `Idempotent-Replayed: true` and does not restore stock
again.

`GET /orders/summary/` returns:

```json
{
  "order_count": 0,
  "total_spent": "0.00",
  "average_order_value": "0.00",
  "currency": "INR"
}
```

Cancelled orders are excluded. Staff cannot call the summary endpoint.

## Important test cases

| Test | Request | Expected result |
| --- | --- | --- |
| Missing authentication | Call products/orders without Bearer token | `401` |
| Wrong login | Use an incorrect password | `401` |
| Missing idempotency key | Create an order without the header | `400` |
| Unknown product | Use `product_id: 999999` | `400 product_not_found` |
| Insufficient stock | Order 26 units of product 3 | `409 insufficient_stock` |
| Atomic rollback | Order product 1 plus 26 units of product 3 | `409`; neither stock changes |
| Duplicate request | Repeat the same key and body | `200`; no second stock deduction |
| Key conflict | Repeat a key with a different body | `409 idempotency_conflict` |
| Ownership | Wholesale user requests a standard user's order UUID | `404` |
| Staff permissions | Staff lists/details/cancels orders | Allowed |
| Staff order creation/summary | Staff calls create or summary | `403` |
| Double cancellation | Cancel the same order twice | Both `200`; stock restored once |
| Wholesale discount | Wholesale user orders 50 total units | 10% discount |

Errors use the shape `code`, `detail`, and `errors`. Product and order write operations other than
order creation/cancellation are intentionally unavailable; catalog and account provisioning use
Django admin.

## Documentation URLs

- `GET /api/docs/` — Swagger UI.
- `GET /api/schema/` — OpenAPI schema.
