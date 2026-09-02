from rest_framework.permissions import BasePermission


def has_customer_profile(user):
    return hasattr(user, "customer")


class IsStaffOrCustomer(BasePermission):
    message = "A staff account or customer profile is required."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and (user.is_staff or has_customer_profile(user))
        )


class IsCustomerOnly(BasePermission):
    message = "This operation is available only to customer accounts."

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated and not user.is_staff and has_customer_profile(user)
        )
