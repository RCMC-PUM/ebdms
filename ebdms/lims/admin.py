from datetime import timedelta

from django.contrib import admin
from django.utils import timezone

from unfold.admin import TabularInline
from unfold.decorators import display
from unfold.paginator import InfinitePaginator

from accounts.admin import UnfoldReversionAdmin
from .models import Order, StockItem


# ======================================================================================
# Inline: Stock items inside Order
# ======================================================================================
class StockItemInline(TabularInline):
    model = StockItem
    extra = 0
    tab = True
    per_page = 10

    ordering = ("expiration_date", "id")

    fields = (
        "item_type",
        "name",
        "catalog_number",
        "unit_price_gross",
        "expiration_date",
        "available",
        "lot"
    )


# ======================================================================================
# Order admin
# ======================================================================================
@admin.register(Order)
class OrderAdmin(UnfoldReversionAdmin):
    paginator = InfinitePaginator
    show_full_result_count = False

    list_display = (
        "project",
        "person_responsible",
        "items_count",
    )

    search_fields = ("project", "order_internal_id", "person_responsible")
    readonly_fields = ("created_at", "total_price")
    inlines = [StockItemInline]

    fieldsets = (
        (
            "Order information",
            {
                "fields": (
                    "order_internal_id",
                    "person_responsible",
                    "project",
                    "description"
                )
            },
        ),
        (
            "Order import",
            {
                "fields": ("order_list",),
                "description": "Upload order sheet (*.xlsx)",
            },
        ),
        (
            "System",
            {
                "fields": ("created_at", "total_price"),
            },
        ),
    )

    @display(description="Items")
    def items_count(self, obj: Order) -> int:
        return obj.stock_items.count()


# ======================================================================================
# StockItem admin
# ======================================================================================
@admin.register(StockItem)
class StockItemAdmin(UnfoldReversionAdmin):
    list_display = (
        "name",
        "order",
        "expiration_colored",
        "unit_price_gross",
    )

    list_filter = ("expiration_date", "item_type")
    search_fields = ("name", "catalog_number")
    ordering = ("expiration_date", "id")

    # -----------------------
    # Expiration highlighting
    # -----------------------
    @display(
        description="Expiration",
        ordering="expiration_date",
        label={
            "OK": "success",
            "SOON": "warning",
            "EXPIRED": "danger",
            "NA": "info",
        },
    )
    def expiration_colored(self, obj: StockItem):
        if not obj.expiration_date:
            return "—"

        if obj.item_type != StockItem.ItemType.CHEMISTRY:
            return "NA", "N/A"

        today = timezone.now().date()
        warning_date = today + timedelta(days=obj.expiration_waring_date)

        if obj.expiration_date < today:
            return "EXPIRED", f"{obj.expiration_date}"

        if obj.expiration_date <= warning_date:
            return "SOON", f"{obj.expiration_date}"

        return "OK", f"{obj.expiration_date}"
