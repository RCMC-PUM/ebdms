import pandas as pd

from django.db import transaction
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.core.exceptions import ValidationError


from .models import Order, StockItem  # adjust import


@receiver(post_save, sender=Order)
def calculate_order_total_price(sender, instance: Order, **kwargs):
    with transaction.atomic():
        # related_name="stock_items"
        total = sum([ins.unit_price_gross for ins in instance.stock_items.all()])

        # prevent useless write by using query set
        if instance.total_price != total:
            Order.objects.filter(pk=instance.pk).update(total_price=total)


@receiver(post_save, sender=Order)
def parse_xlsx_after_order_create(sender, instance, created, **kwargs):
    # Only parse on creation
    if not created:
        return

    if not instance.order_list:
        return

    with transaction.atomic():
        # Read XLSX
        df = pd.read_excel(instance.order_list)

        df = df.dropna(axis=1, how="all")
        df.columns = [str(c).strip().upper() for c in df.columns]
        df = df[["PRODUCT", "CATEGORY", "PROVIDER", "ID", "QUANTITY", "UNIT PRICE"]]

        items = []
        for idx, row in df.iterrows():
            try:
                product = str(row["PRODUCT"])
                category = str(row["CATEGORY"].upper())
                provider = str(row["PROVIDER"])
                catalog_number = str(row["ID"])
                quantity = int(row["QUANTITY"])
                unit_price_gross = float(row["UNIT PRICE"])

            except Exception as e:  # noqa
                raise ValidationError(f"Can not parse row {idx} - {row}: {e}")

            for _ in range(quantity):
                items.append(
                    StockItem(
                        order=instance,
                        name=product.strip(),
                        item_type=category.strip(),
                        provider=provider.strip(),
                        catalog_number=catalog_number.strip(),
                        unit_price_gross=unit_price_gross,
                    )
                )

        StockItem.objects.bulk_create(items)
