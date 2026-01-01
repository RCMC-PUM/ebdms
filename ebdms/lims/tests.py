import os
import tempfile
from decimal import Decimal

import pandas as pd

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from lims.models import Order, StockItem
import lims.signals  # noqa --> ensures receivers are registered


def make_xlsx_upload(
    df: pd.DataFrame, filename: str = "order.xlsx"
) -> SimpleUploadedFile:
    """
    Build an XLSX binary in a temp dir and return it as an uploaded file.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        path = os.path.join(tmp_dir, filename)
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            df.to_excel(writer, index=False)

        with open(path, "rb") as f:
            content = f.read()

    return SimpleUploadedFile(
        name=filename,
        content=content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


class OrderSignalsTests(TestCase):
    def test_parse_xlsx_creates_stock_items_on_create_only(self):
        df = pd.DataFrame(
            [
                {
                    "product": "  Test Tube  ",
                    "category": "PLASTICS",
                    "provider": " XYZ ",
                    "id": " TT-001 ",
                    "quantity": 3,
                    "unit price": 12.50,
                    "": None,
                },
                {
                    "product": "Buffer",
                    "category": "CHEMISTRY",
                    "provider": "ABC",
                    "id": " BUF-9 ",
                    "quantity": 1,
                    "unit price": 5.00,
                },
            ]
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                upload = make_xlsx_upload(df)

                order = Order.objects.create(
                    person_responsible="Jan",
                    order_list=upload,
                )

                self.assertEqual(StockItem.objects.filter(order=order).count(), 4)

                # sanity check one created record
                item = StockItem.objects.filter(order=order, name="Test Tube").first()
                self.assertIsNotNone(item)
                self.assertEqual(item.item_type, "PLASTICS")
                self.assertEqual(item.provider, "XYZ")
                self.assertEqual(item.catalog_number, "TT-001")
                self.assertEqual(item.unit_price_gross, Decimal("12.50"))

                # Updating the order should NOT parse again (created=False)
                order.description = "updated"
                order.save()
                self.assertEqual(StockItem.objects.filter(order=order).count(), 4)

    def test_parse_xlsx_raises_validation_error_on_bad_row(self):
        df = pd.DataFrame(
            [
                {
                    "PRODUCT": "Test",
                    "CATEGORY": "PLASTICS",
                    "PROVIDER": "XYZ",
                    "ID": "X",
                    "QUANTITY": "not_an_int",  # will fail int()
                    "UNIT PRICE": 1.23,
                }
            ]
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                upload = make_xlsx_upload(df)

                with self.assertRaises(ValidationError):
                    Order.objects.create(
                        person_responsible="Jan",
                        order_list=upload,
                    )

    def test_calculate_total_price_updates_on_order_save(self):
        order = Order.objects.create(person_responsible="Jan")

        StockItem.objects.create(
            order=order,
            name="A",
            item_type=StockItem.ItemType.PLASTICS,
            unit_price_gross=Decimal("10.00"),
        )
        StockItem.objects.create(
            order=order,
            name="B",
            item_type=StockItem.ItemType.CHEMISTRY,
            unit_price_gross=Decimal("2.50"),
        )

        # In your model total_price defaults to 0.00 (not None)
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal("0.00"))

        # Your signal recalculates total when the ORDER is saved
        order.save()
        order.refresh_from_db()
        self.assertEqual(order.total_price, Decimal("12.50"))

    def test_create_with_xlsx_does_not_auto_set_total_until_order_saved(self):
        df = pd.DataFrame(
            [
                {
                    "PRODUCT": "Item",
                    "CATEGORY": "PLASTICS",
                    "PROVIDER": "XYZ",
                    "ID": "X",
                    "QUANTITY": 2,
                    "UNIT PRICE": 3.00,
                }
            ]
        )

        with tempfile.TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                upload = make_xlsx_upload(df)

                order = Order.objects.create(
                    person_responsible="Jan",
                    order_list=upload,
                )

                order.refresh_from_db()
                # bulk_create inserted items, but order wasn't re-saved after that
                self.assertEqual(order.total_price, Decimal("0.00"))

                # After explicit save, total updates
                order.save()
                order.refresh_from_db()
                self.assertEqual(order.total_price, Decimal("6.00"))
