#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
COMPOSE_ENV="${COMPOSE_ENV:-.env.docker}"
RUN_ID="${RUN_ID:-$(date +%Y%m%d%H%M%S)}"
PASSWORD="${PASSWORD:-ReviewPass!2026}"

STANDARD_EMAIL="review-standard-${RUN_ID}@tradeflow.local"
WHOLESALE_EMAIL="review-wholesale-${RUN_ID}@tradeflow.local"
OTHER_EMAIL="review-other-${RUN_ID}@tradeflow.local"
STAFF_EMAIL="review-staff-${RUN_ID}@tradeflow.local"

PRODUCT_A_SKU="REVIEW-A-${RUN_ID}"
PRODUCT_B_SKU="REVIEW-B-${RUN_ID}"
PRODUCT_C_SKU="REVIEW-C-${RUN_ID}"

COMPOSE=(docker compose --env-file "$COMPOSE_ENV")
TMP_FILES=()
LAST_BODY=""
LAST_HEADERS=""

cleanup() {
  if [ "${#TMP_FILES[@]}" -gt 0 ]; then
    rm -f "${TMP_FILES[@]}"
  fi
}
trap cleanup EXIT

fail() {
  printf "\nFAIL: %s\n" "$1" >&2
  if [ -n "${LAST_BODY:-}" ] && [ -f "$LAST_BODY" ]; then
    printf "Last response body:\n" >&2
    sed -n '1,120p' "$LAST_BODY" >&2
  fi
  exit 1
}

tmpfile() {
  local file
  file="$(mktemp)"
  TMP_FILES+=("$file")
  printf "%s" "$file"
}

section() {
  printf "\n== %s ==\n" "$1"
}

request() {
  local label="$1"
  local expected_status="$2"
  local method="$3"
  local path="$4"
  local token="${5:-}"
  local body="${6:-}"
  local idempotency_key="${7:-}"
  local response_file headers_file status

  response_file="$(tmpfile)"
  headers_file="$(tmpfile)"

  local curl_args=(
    -sS
    -X "$method"
    -D "$headers_file"
    -o "$response_file"
    -w "%{http_code}"
    "$BASE_URL$path"
  )

  if [ -n "$token" ]; then
    curl_args+=(-H "Authorization: Bearer $token")
  fi
  if [ -n "$body" ]; then
    curl_args+=(-H "Content-Type: application/json" -d "$body")
  fi
  if [ -n "$idempotency_key" ]; then
    curl_args+=(-H "Idempotency-Key: $idempotency_key")
  fi

  if ! status="$(curl "${curl_args[@]}")"; then
    LAST_BODY="$response_file"
    LAST_HEADERS="$headers_file"
    fail "$label request failed"
  fi

  LAST_BODY="$response_file"
  LAST_HEADERS="$headers_file"

  if [ "$status" != "$expected_status" ]; then
    fail "$label expected HTTP $expected_status but got HTTP $status"
  fi

  printf "OK  %-58s %s\n" "$label" "$status"
}

json_get() {
  local path="$1"
  local file="${2:-$LAST_BODY}"
  "${COMPOSE[@]}" exec -T web python -c '
import json
import re
import sys

data = json.load(sys.stdin)
path = sys.argv[1]
if path:
    for segment in path.split("."):
        while segment:
            key = re.match(r"[^\[\]]+", segment)
            if key:
                data = data[key.group(0)]
                segment = segment[key.end():]
                continue
            if segment.startswith("["):
                end = segment.index("]")
                data = data[int(segment[1:end])]
                segment = segment[end + 1:]
                continue
            raise SystemExit(f"Unsupported JSON path segment: {segment}")

if data is None:
    print("")
elif isinstance(data, (dict, list)):
    print(json.dumps(data, sort_keys=True))
else:
    print(data)
' "$path" < "$file"
}

assert_json_equals() {
  local path="$1"
  local expected="$2"
  local actual
  actual="$(json_get "$path")"
  if [ "$actual" != "$expected" ]; then
    fail "expected JSON $path to be '$expected' but got '$actual'"
  fi
}

assert_header_equals() {
  local name="$1"
  local expected="$2"
  local actual
  actual="$(
    awk -F ': *' -v name="$name" 'tolower($1) == tolower(name) {print $2; exit}' "$LAST_HEADERS" |
      tr -d '\r'
  )"
  if [ "$actual" != "$expected" ]; then
    fail "expected header $name to be '$expected' but got '$actual'"
  fi
}

prepare_review_data() {
  section "Prepare isolated review data"
  "${COMPOSE[@]}" exec -T \
    -e REVIEW_RUN_ID="$RUN_ID" \
    -e REVIEW_PASSWORD="$PASSWORD" \
    web python <<'PY'
import os
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.contrib.auth import get_user_model

from accounts.models import Customer
from catalog.models import Product

run_id = os.environ["REVIEW_RUN_ID"]
password = os.environ["REVIEW_PASSWORD"]
User = get_user_model()


def create_user(email, *, is_staff=False, is_superuser=False):
    user, _created = User.objects.update_or_create(
        email=email,
        defaults={
            "is_active": True,
            "is_staff": is_staff,
            "is_superuser": is_superuser,
        },
    )
    user.set_password(password)
    user.save(update_fields=["password", "is_active", "is_staff", "is_superuser"])
    return user


def create_customer(email, company_name, tier):
    user = create_user(email)
    Customer.objects.update_or_create(
        user=user,
        defaults={"company_name": company_name, "tier": tier},
    )


create_customer(f"review-standard-{run_id}@tradeflow.local", "Review Standard", Customer.Tier.STANDARD)
create_customer(f"review-wholesale-{run_id}@tradeflow.local", "Review Wholesale", Customer.Tier.WHOLESALE)
create_customer(f"review-other-{run_id}@tradeflow.local", "Review Other", Customer.Tier.STANDARD)
create_user(f"review-staff-{run_id}@tradeflow.local", is_staff=True, is_superuser=True)

products = (
    (f"REVIEW-A-{run_id}", "Review Product A", Decimal("100.00"), 200),
    (f"REVIEW-B-{run_id}", "Review Product B", Decimal("250.00"), 75),
    (f"REVIEW-C-{run_id}", "Review Product C", Decimal("499.99"), 25),
)
for sku, name, price, stock_quantity in products:
    Product.objects.update_or_create(
        sku=sku,
        defaults={
            "name": name,
            "description": f"Isolated API review item {name}.",
            "price": price,
            "stock_quantity": stock_quantity,
            "is_active": True,
        },
    )

print(f"Prepared review data for run {run_id}")
PY
}

change_product_b_price() {
  section "Simulate product price change"
  "${COMPOSE[@]}" exec -T -e REVIEW_RUN_ID="$RUN_ID" web python <<'PY'
import os
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from catalog.models import Product

sku = f"REVIEW-B-{os.environ['REVIEW_RUN_ID']}"
Product.objects.filter(sku=sku).update(price=Decimal("275.00"))
print(f"Updated {sku} current catalog price to 275.00")
PY
}

if [ ! -f "$COMPOSE_ENV" ]; then
  fail "missing $COMPOSE_ENV; run 'cp .env.docker.example .env.docker' first"
fi

section "Configuration"
printf "BASE_URL=%s\n" "$BASE_URL"
printf "RUN_ID=%s\n" "$RUN_ID"

prepare_review_data

section "Health and authentication"
request "health endpoint" 200 GET "/api/v1/health/"
request "products require authentication" 401 GET "/api/v1/products/"
request "wrong login is rejected" 401 POST "/api/v1/auth/token/" "" \
  "{\"email\":\"$STANDARD_EMAIL\",\"password\":\"WrongPass!2026\"}"

request "login standard customer" 200 POST "/api/v1/auth/token/" "" \
  "{\"email\":\"$STANDARD_EMAIL\",\"password\":\"$PASSWORD\"}"
STANDARD_TOKEN="$(json_get access)"
STANDARD_REFRESH="$(json_get refresh)"

request "refresh standard token" 200 POST "/api/v1/auth/token/refresh/" "" \
  "{\"refresh\":\"$STANDARD_REFRESH\"}"
ROTATED_REFRESH="$(json_get refresh)"

request "blacklist rotated refresh token" 200 POST "/api/v1/auth/token/blacklist/" "" \
  "{\"refresh\":\"$ROTATED_REFRESH\"}"
request "blacklisted refresh token is rejected" 401 POST "/api/v1/auth/token/refresh/" "" \
  "{\"refresh\":\"$ROTATED_REFRESH\"}"

request "login wholesale customer" 200 POST "/api/v1/auth/token/" "" \
  "{\"email\":\"$WHOLESALE_EMAIL\",\"password\":\"$PASSWORD\"}"
WHOLESALE_TOKEN="$(json_get access)"

request "login other customer" 200 POST "/api/v1/auth/token/" "" \
  "{\"email\":\"$OTHER_EMAIL\",\"password\":\"$PASSWORD\"}"
OTHER_TOKEN="$(json_get access)"

request "login staff user" 200 POST "/api/v1/auth/token/" "" \
  "{\"email\":\"$STAFF_EMAIL\",\"password\":\"$PASSWORD\"}"
STAFF_TOKEN="$(json_get access)"

section "Product catalog"
request "search product A" 200 GET "/api/v1/products/?search=$PRODUCT_A_SKU&page_size=1" "$STANDARD_TOKEN"
assert_json_equals "results[0].sku" "$PRODUCT_A_SKU"
PRODUCT_A_ID="$(json_get "results[0].id")"

request "search product B" 200 GET "/api/v1/products/?search=$PRODUCT_B_SKU&page_size=1" "$STANDARD_TOKEN"
PRODUCT_B_ID="$(json_get "results[0].id")"

request "search product C" 200 GET "/api/v1/products/?search=$PRODUCT_C_SKU&page_size=1" "$STANDARD_TOKEN"
PRODUCT_C_ID="$(json_get "results[0].id")"

request "retrieve product detail" 200 GET "/api/v1/products/$PRODUCT_A_ID/" "$STANDARD_TOKEN"
assert_json_equals sku "$PRODUCT_A_SKU"
A_STOCK_BEFORE="$(json_get stock_quantity)"

request "list products with ordering and pagination" 200 GET \
  "/api/v1/products/?ordering=-price&page=1&page_size=5" "$STANDARD_TOKEN"

section "Customer order behavior"
request "summary works for a customer with no orders" 200 GET "/api/v1/orders/summary/" "$STANDARD_TOKEN"
assert_json_equals order_count 0
assert_json_equals total_spent "0.00"

request "missing idempotency key is rejected" 400 POST "/api/v1/orders/" "$STANDARD_TOKEN" \
  "{\"items\":[{\"product_id\":$PRODUCT_A_ID,\"quantity\":1}]}"
assert_json_equals code "missing_idempotency_key"

request "unknown product is rejected" 400 POST "/api/v1/orders/" "$STANDARD_TOKEN" \
  '{"items":[{"product_id":999999999,"quantity":1}]}' "review-unknown-${RUN_ID}"
assert_json_equals code "product_not_found"

request "insufficient stock rejects the whole order" 409 POST "/api/v1/orders/" "$STANDARD_TOKEN" \
  "{\"items\":[{\"product_id\":$PRODUCT_A_ID,\"quantity\":1},{\"product_id\":$PRODUCT_C_ID,\"quantity\":26}]}" \
  "review-insufficient-${RUN_ID}"
assert_json_equals code "insufficient_stock"

request "stock is unchanged after failed order" 200 GET "/api/v1/products/$PRODUCT_A_ID/" "$STANDARD_TOKEN"
assert_json_equals stock_quantity "$A_STOCK_BEFORE"

request "customer creates multi-product order" 201 POST "/api/v1/orders/" "$STANDARD_TOKEN" \
  "{\"items\":[{\"product_id\":$PRODUCT_A_ID,\"quantity\":2},{\"product_id\":$PRODUCT_B_ID,\"quantity\":1}]}" \
  "review-standard-${RUN_ID}"
STANDARD_ORDER_ID="$(json_get id)"
STANDARD_CUSTOMER_ID="$(json_get customer.id)"
assert_json_equals status "PLACED"
assert_json_equals total "450.00"

request "stock decreases after successful order" 200 GET "/api/v1/products/$PRODUCT_A_ID/" "$STANDARD_TOKEN"
assert_json_equals stock_quantity "$((A_STOCK_BEFORE - 2))"

request "same idempotency key replays without a second order" 200 POST "/api/v1/orders/" "$STANDARD_TOKEN" \
  "{\"items\":[{\"product_id\":$PRODUCT_A_ID,\"quantity\":2},{\"product_id\":$PRODUCT_B_ID,\"quantity\":1}]}" \
  "review-standard-${RUN_ID}"
assert_header_equals "Idempotent-Replayed" "true"
assert_json_equals id "$STANDARD_ORDER_ID"

request "same idempotency key with different payload conflicts" 409 POST "/api/v1/orders/" "$STANDARD_TOKEN" \
  "{\"items\":[{\"product_id\":$PRODUCT_A_ID,\"quantity\":3}]}" \
  "review-standard-${RUN_ID}"
assert_json_equals code "idempotency_conflict"

request "customer lists own orders" 200 GET "/api/v1/orders/?page_size=10" "$STANDARD_TOKEN"
assert_json_equals count 1

request "customer retrieves own order detail" 200 GET "/api/v1/orders/$STANDARD_ORDER_ID/" "$STANDARD_TOKEN"
assert_json_equals id "$STANDARD_ORDER_ID"

request "another customer cannot access the order" 404 GET "/api/v1/orders/$STANDARD_ORDER_ID/" "$OTHER_TOKEN"

section "Staff order review and cancellation"
request "staff lists placed orders" 200 GET "/api/v1/orders/?status=PLACED&page_size=10" "$STAFF_TOKEN"

request "staff filters orders by customer" 200 GET \
  "/api/v1/orders/?customer_id=$STANDARD_CUSTOMER_ID&status=PLACED&page_size=10" "$STAFF_TOKEN"
assert_json_equals count 1

request "staff retrieves customer order detail" 200 GET "/api/v1/orders/$STANDARD_ORDER_ID/" "$STAFF_TOKEN"
assert_json_equals id "$STANDARD_ORDER_ID"

request "staff invalid customer filter is rejected" 400 GET \
  "/api/v1/orders/?customer_id=not-an-integer" "$STAFF_TOKEN"

request "staff cannot create customer orders" 403 POST "/api/v1/orders/" "$STAFF_TOKEN" \
  "{\"items\":[{\"product_id\":$PRODUCT_A_ID,\"quantity\":1}]}" "review-staff-create-${RUN_ID}"

request "staff cannot view customer summary endpoint" 403 GET "/api/v1/orders/summary/" "$STAFF_TOKEN"

request "staff cancels customer order" 200 POST "/api/v1/orders/$STANDARD_ORDER_ID/cancel/" "$STAFF_TOKEN"
assert_json_equals status "CANCELLED"

request "double cancellation is idempotent" 200 POST "/api/v1/orders/$STANDARD_ORDER_ID/cancel/" "$STAFF_TOKEN"
assert_header_equals "Idempotent-Replayed" "true"
assert_json_equals status "CANCELLED"

request "stock is restored after cancellation" 200 GET "/api/v1/products/$PRODUCT_A_ID/" "$STANDARD_TOKEN"
assert_json_equals stock_quantity "$A_STOCK_BEFORE"

request "summary excludes cancelled orders" 200 GET "/api/v1/orders/summary/" "$STANDARD_TOKEN"
assert_json_equals order_count 0

section "Price snapshots and wholesale discount"
request "customer creates order before a price change" 201 POST "/api/v1/orders/" "$STANDARD_TOKEN" \
  "{\"items\":[{\"product_id\":$PRODUCT_B_ID,\"quantity\":1}]}" "review-snapshot-${RUN_ID}"
SNAPSHOT_ORDER_ID="$(json_get id)"
assert_json_equals "items[0].unit_price" "250.00"

change_product_b_price

request "order keeps original unit price after product price changes" 200 GET \
  "/api/v1/orders/$SNAPSHOT_ORDER_ID/" "$STANDARD_TOKEN"
assert_json_equals "items[0].unit_price" "250.00"

request "customer cancels snapshot order" 200 POST "/api/v1/orders/$SNAPSHOT_ORDER_ID/cancel/" "$STANDARD_TOKEN"
assert_json_equals status "CANCELLED"

request "wholesale customer gets quantity discount" 201 POST "/api/v1/orders/" "$WHOLESALE_TOKEN" \
  "{\"items\":[{\"product_id\":$PRODUCT_A_ID,\"quantity\":50}]}" "review-wholesale-${RUN_ID}"
WHOLESALE_ORDER_ID="$(json_get id)"
assert_json_equals discount_rate "0.1000"
assert_json_equals discount_amount "500.00"
assert_json_equals total "4500.00"

request "wholesale customer can cancel discounted order" 200 POST \
  "/api/v1/orders/$WHOLESALE_ORDER_ID/cancel/" "$WHOLESALE_TOKEN"
assert_json_equals status "CANCELLED"

section "Done"
printf "All API review checks passed for RUN_ID=%s\n" "$RUN_ID"
printf "Successful order creation also exercises the console email backend; inspect web logs if needed.\n"
