from decimal import Decimal

import pytest
from rest_framework import status

from catalog.models import Product

pytestmark = pytest.mark.django_db


def test_product_catalog_requires_authentication(api_client):
    response = api_client.get("/api/v1/products/")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_catalog_supports_search_and_hides_inactive_products(
    authenticated_client,
    customer_user,
    product,
):
    Product.objects.create(
        sku="HIDDEN-1",
        name="Hidden product",
        price=Decimal("1.00"),
        stock_quantity=1,
        is_active=False,
    )
    Product.objects.create(
        sku="ZERO-1",
        name="Visible but out of stock",
        price=Decimal("25.00"),
        stock_quantity=0,
    )
    client = authenticated_client(customer_user)

    response = client.get("/api/v1/products/?search=widget")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 1
    assert response.data["results"][0]["sku"] == product.sku

    all_products = client.get("/api/v1/products/")
    skus = {entry["sku"] for entry in all_products.data["results"]}
    assert "HIDDEN-1" not in skus
    assert "ZERO-1" in skus
    zero = next(entry for entry in all_products.data["results"] if entry["sku"] == "ZERO-1")
    assert zero["is_available"] is False


def test_inactive_product_detail_is_not_exposed(authenticated_client, customer_user, product):
    product.deactivate()
    response = authenticated_client(customer_user).get(f"/api/v1/products/{product.id}/")
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_catalog_pagination_honors_bounded_page_size(authenticated_client, customer_user):
    Product.objects.bulk_create(
        [
            Product(
                sku=f"PAGE-{index:03d}",
                name=f"Product {index:03d}",
                price=Decimal("10.00"),
                stock_quantity=1,
            )
            for index in range(25)
        ]
    )
    response = authenticated_client(customer_user).get("/api/v1/products/?page_size=10")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["count"] == 25
    assert len(response.data["results"]) == 10
