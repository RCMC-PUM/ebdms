import pandas as pd

from django.db import transaction
from django.dispatch import receiver
from django.db.models.signals import post_save
from django.core.exceptions import ValidationError

from .models import Order, StockItem


@receiver(post_save, sender=Order)
def parse_xlsx_after_order_create(sender, instance, created, **kwargs):
    # Only parse on creation
    if not created:
        return

    if not instance.items_xlsx:
        return

    with transaction.atomic():
        # Read XLSX
        df = pd.read_excel(instance.items_xlsx.path, header=None, index_col=0)
        df = df.dropna(axis=1)

        # Normalize / rename columns (adapt if headers differ)
        df.columns = [
            "product",
            "catalog_number",
            "quantity",
            "unit_price_gross",
            "total_price_gross",
        ]

        items = []
        for idx, row in df.iterrows():
            try:
                product = str(row["product"])
                catalog_number = str(row["catalog_number"])
                quantity = int(row["quantity"])
                unit_price_gross = float(row["unit_price_gross"])

            except Exception as e: # noqa
                raise ValidationError(f"Can not parse row {idx}: {e}")

            items.append(
                StockItem(
                    order=instance,
                    item_type=StockItem.ItemType.GOODS,
                    description=product.strip(),
                    catalog_number=catalog_number.strip(),
                    quantity=quantity,
                    unit_price_gross=unit_price_gross,
                    estimated_total_gross=unit_price_gross*quantity
                )
            )

        StockItem.objects.bulk_create(items)
