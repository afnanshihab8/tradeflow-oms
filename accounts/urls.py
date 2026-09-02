from django.urls import path

from accounts.views import BlacklistTokenView, EmailTokenObtainPairView, RefreshTokenView

urlpatterns = [
    path("token/", EmailTokenObtainPairView.as_view(), name="token-obtain"),
    path("token/refresh/", RefreshTokenView.as_view(), name="token-refresh"),
    path("token/blacklist/", BlacklistTokenView.as_view(), name="token-blacklist"),
]
