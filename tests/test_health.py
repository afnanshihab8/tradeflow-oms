import pytest
from rest_framework import status

pytestmark = pytest.mark.django_db


def test_health_check_is_public_and_checks_the_database(api_client):
    response = api_client.get("/api/v1/health/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"status": "ok", "database": "ok"}
