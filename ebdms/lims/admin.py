from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from datetime import timedelta

from unfold.admin import TabularInline
from unfold.paginator import InfinitePaginator

from accounts.admin import UnfoldReversionAdmin
from .models import Order, StockItem


class StockItemInline(TabularInline):
    model = StockItem
    extra = 0
    tab = True
    per_page = 5

    ordering = ("expiration_date", "id")

    fields = (
        "item_type",
        "description",
        "catalog_number",
        "quantity_badge",
        "unit_price_gross",
        "estimated_total_gross",
        "expiration_date",
        "available"
    )

    readonly_fields = ("quantity_badge", "estimated_total_gross")

    def quantity_badge(self, obj):
        # Unsaved inline rows
        if obj.pk is None or obj.quantity is None:
            return "—"

        # Services: no warning
        if obj.item_type == obj.ItemType.SERVICE:
            return obj.quantity

        if obj.quantity < 1:
            return format_html(
                '<span style="color:#dc2626;font-weight:700;">{} ⚠</span>',
                obj.quantity
            )
        return obj.quantity

    quantity_badge.short_description = "Quantity"


@admin.register(Order)
class OrderAdmin(UnfoldReversionAdmin):
    paginator = InfinitePaginator
    show_full_result_count = False

    list_display = (
        "project_name",
        "person_responsible",
        "order_date",
        "items_count",
    )

    search_fields = ("project_name", "person_responsible")
    list_filter = ("order_date",)

    readonly_fields = ("created_at",)
    inlines = [StockItemInline]

    fieldsets = (
        ("Order information", {
            "fields": (
                "project_name",
                "person_responsible",
                "order_date",
            )
        }),
        ("XLSX import", {
            "fields": ("items_xlsx",),
            "description": "Upload order sheet",
        }),
        ("System", {
            "fields": ("created_at",),
        }),
    )

    def items_count(self, obj):
        return obj.stock_items.count()

    items_count.short_description = "Items"


@admin.register(StockItem)
class StockItemAdmin(UnfoldReversionAdmin):
    list_display = (
        "description",
        "order",
        "quantity_colored",
        "expiration_colored",
        "estimated_total_gross",
    )

    list_filter = ("expiration_date", "item_type")
    search_fields = ("description", "catalog_number")
    ordering = ("expiration_date", "id")

    # -----------------------
    # Quantity highlighting
    # -----------------------
    def quantity_colored(self, obj):
        if obj.quantity is None:
            return "—"

        if obj.item_type == StockItem.ItemType.SERVICE:
            return obj.quantity

        if obj.quantity < 1:
            return format_html(
                '<span style="color:#dc2626;font-weight:700;">{} ⚠</span>',
                obj.quantity,
            )

        return obj.quantity

    quantity_colored.short_description = "Quantity"
    quantity_colored.admin_order_field = "quantity"

    # -----------------------
    # Expiration highlighting
    # -----------------------
    def expiration_colored(self, obj):
        if not obj.expiration_date:
            return "—"

        if obj.item_type == StockItem.ItemType.SERVICE:
            return "N/A"

        today = timezone.now().date()
        warning_date = today + timedelta(days=30)

        if obj.expiration_date < today:
            return format_html(
                '<span style="color:#991b1b;font-weight:700;">{} ⛔</span>',
                obj.expiration_date,
            )

        if obj.expiration_date <= warning_date:
            return format_html(
                '<span style="color:#dc2626;font-weight:700;">{} ⚠</span>',
                obj.expiration_date,
            )

        return obj.expiration_date

    expiration_colored.short_description = "Expiration"
    expiration_colored.admin_order_field = "expiration_date"
