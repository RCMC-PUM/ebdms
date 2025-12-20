from decimal import Decimal
from pathlib import Path

from django.core.validators import FileExtensionValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def order_upload_to(instance, filename):
    ext = Path(filename).suffix.lower()
    return f"orders/{timezone.now():%Y/%m}/order_{instance.pk or 'new'}{ext}"


class Order(models.Model):
    project_name = models.CharField(max_length=255)
    person_responsible = models.CharField(max_length=255)

    order_date = models.DateField(default=timezone.localdate)
    items_xlsx = models.FileField(
        upload_to=order_upload_to,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["xlsx"])]
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-order_date"]
        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self):
        return f"{self.project_name} | {self.person_responsible}"


class StockItem(models.Model):
    class ItemType(models.TextChoices):
        GOODS = "GOODS", "Goods (delivery)"
        SERVICE = "SERVICE", "Service"

    order = models.ForeignKey(
        Order,
        related_name="stock_items",
        on_delete=models.CASCADE,
    )

    item_type = models.CharField(
        max_length=10,
        choices=ItemType.choices,
        default=ItemType.GOODS,
    )

    description = models.TextField()
    catalog_number = models.CharField(max_length=128, blank=True, null=True)

    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(0)],
    )

    unit_price_gross = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    estimated_total_gross = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        editable=False,
    )

    available = models.BooleanField(default=False)
    expiration_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["expiration_date"]
        verbose_name = "Stock items"
        verbose_name_plural = "Stock items"

    def save(self, *args, **kwargs):
        self.estimated_total_gross = (
            self.quantity * self.unit_price_gross
            if self.quantity and self.unit_price_gross
            else Decimal("0")
        )
        super().save(*args, **kwargs)
