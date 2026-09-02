from datetime import timedelta

import pytest
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

pytestmark = pytest.mark.django_db


def test_email_login_returns_short_lived_access_and_refresh_tokens(api_client, customer_user):
    response = api_client.post(
        "/api/v1/auth/token/",
        {"email": "BUYER@EXAMPLE.COM", "password": "CustomerPass!2026"},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert set(response.data) >= {"access", "refresh"}
    access = RefreshToken(response.data["refresh"]).access_token
    assert timedelta(seconds=access["exp"] - access["iat"]) == timedelta(minutes=15)
    refresh = RefreshToken(response.data["refresh"])
    assert timedelta(seconds=refresh["exp"] - refresh["iat"]) == timedelta(days=1)


def test_login_contract_requires_email_not_username(api_client, customer_user):
    response = api_client.post(
        "/api/v1/auth/token/",
        {"username": "buyer@example.com", "password": "CustomerPass!2026"},
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in response.data["errors"]


def test_rotated_refresh_token_can_be_blacklisted(api_client, customer_user):
    login = api_client.post(
        "/api/v1/auth/token/",
        {"email": customer_user.email, "password": "CustomerPass!2026"},
        format="json",
    )
    refreshed = api_client.post(
        "/api/v1/auth/token/refresh/",
        {"refresh": login.data["refresh"]},
        format="json",
    )
    assert refreshed.status_code == status.HTTP_200_OK
    assert "refresh" in refreshed.data

    blacklisted = api_client.post(
        "/api/v1/auth/token/blacklist/",
        {"refresh": refreshed.data["refresh"]},
        format="json",
    )
    assert blacklisted.status_code == status.HTTP_200_OK

    rejected = api_client.post(
        "/api/v1/auth/token/refresh/",
        {"refresh": refreshed.data["refresh"]},
        format="json",
    )
    assert rejected.status_code == status.HTTP_401_UNAUTHORIZED
