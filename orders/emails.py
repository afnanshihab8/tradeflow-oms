from django.conf import settings
from django.core.mail import send_mail

from orders.models import Order


def send_order_confirmation(order_id):
    order = (
        Order.objects.select_related("customer__user").prefetch_related("items").get(pk=order_id)
    )
    item_lines = [
        f"- {item.product_name} ({item.product_sku}): "
        f"{item.quantity} × ₹{item.unit_price} = ₹{item.line_subtotal}"
        for item in order.items.all()
    ]
    body = "\n".join(
        [
            f"Sales order confirmation: {order.id}",
            f"Customer: {order.customer.company_name}",
            "",
            *item_lines,
            "",
            f"Subtotal: ₹{order.subtotal}",
            f"Discount: ₹{order.discount_amount}",
            f"Total: ₹{order.total}",
        ]
    )
    send_mail(
        subject=f"TradeFlow order confirmation {order.id}",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.customer.user.email],
        fail_silently=False,
    )
