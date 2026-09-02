from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower

from accounts.managers import UserManager


class User(AbstractUser):
    username = None
    email = models.EmailField(unique=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(Lower("email"), name="accounts_user_email_ci_unique")
        ]

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class Customer(models.Model):
    class Tier(models.TextChoices):
        STANDARD = "STANDARD", "Standard"
        WHOLESALE = "WHOLESALE", "Wholesale"

    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.PROTECT,
        related_name="customer",
    )
    company_name = models.CharField(max_length=255)
    tier = models.CharField(max_length=16, choices=Tier.choices, default=Tier.STANDARD)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_name", "id"]

    def __str__(self):
        return self.company_name
