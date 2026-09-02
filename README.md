# TradeFlow Warehouse OMS

A Django REST Framework API for a wholesale product catalog and order-management workflow. Customers
can browse products, place and cancel orders, view their order history, and see a purchasing summary.
Staff can review and cancel orders across customers.

## Requirements

The recommended setup only requires:

- Docker Desktop or Docker Engine
- Docker Compose

For a native setup, use Python 3.12 and PostgreSQL 16 or newer.

## Setup

```bash
git clone https://github.com/afnanshihab8/tradeflow-oms.git
cd tradeflow-oms
cp .env.docker.example .env.docker
docker compose --env-file .env.docker up --build --detach
```

If port `8000` is already in use, set `TF_WEB_PORT=8001` in `.env.docker` before starting Compose and
use `http://127.0.0.1:8001` below.

The first start creates PostgreSQL, applies migrations, loads demo data, and starts the API. Check it
with:

```bash
curl http://127.0.0.1:8000/api/v1/health/
```

Swagger UI is available at <http://127.0.0.1:8000/api/docs/>.

For broader runnable API checks covering the assignment scenarios:

```bash
bash ./api_review_checks.sh
```

When using another host port, pass its base URL:

```bash
BASE_URL=http://127.0.0.1:8001 bash ./api_review_checks.sh
```

The review script creates isolated local users and products for each run.

### Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Staff | `admin@tradeflow.local` | `LocalAdmin!2026` |
| Standard customer | `standard@tradeflow.local` | `LocalCustomer!2026` |
| Wholesale customer | `wholesale@tradeflow.local` | `LocalCustomer!2026` |

Demo products are seeded automatically. To seed them manually:

```bash
docker compose --env-file .env.docker exec web python manage.py seed_demo
```

Run the test suite:

```bash
docker compose --env-file .env.docker --profile test run --rm test
```

Stop the project:

```bash
docker compose --env-file .env.docker down
```

Local environment files are ignored by Git. Values in `.env.docker.example` are intended only for
local review.

## Linux setup without Docker

On Ubuntu 24.04, install Python and PostgreSQL:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3-pip postgresql postgresql-contrib
sudo systemctl enable --now postgresql
sudo -u postgres createuser --createdb "$(id -un)"
createdb tradeflow_oms
```

Then prepare the application:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

Before continuing, edit `.env`:

- Set `DJANGO_SECRET_KEY` to any non-empty local value.
- Set `POSTGRES_USER` to the local PostgreSQL role, normally the output of `id -un`.
- Set `POSTGRES_PASSWORD` if that role requires one.

Apply migrations, seed demo data, and start the development server:

```bash
python manage.py migrate
DEMO_ADMIN_PASSWORD='choose-an-admin-password' \
DEMO_CUSTOMER_PASSWORD='choose-a-customer-password' \
python manage.py seed_demo
python manage.py runserver
```

Run tests natively with:

```bash
python -m pytest
```

## Implementation notes

- Orders are atomic and use PostgreSQL row locks to prevent partial orders and overselling.
- Order items retain product and price snapshots; duplicate submissions and cancellations are
  idempotent.
- Wholesale customers receive a 10% discount when an order contains at least 50 total units.
- Products are managed through Django admin and are deactivated instead of deleted.
- Confirmation email is simulated with Django's console email backend.

## Links

- [API test sheet](API.md)
- [Runnable API review checks](api_review_checks.sh)
- [AI usage notes](AI.md)
- [OpenAPI schema](http://127.0.0.1:8000/api/schema/)
- [Swagger UI](http://127.0.0.1:8000/api/docs/)
