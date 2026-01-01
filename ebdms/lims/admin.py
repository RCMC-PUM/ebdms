from datetime import timedelta

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from unfold.admin import TabularInline
from unfold.decorators import display
from unfold.paginator import InfinitePaginator

from core.admin import UnfoldReversionAdmin
from .models import Order, StockItem, LNotebook, Tag, LNotebookTag, Document


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
        "lot",
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
                    "description",
                ),
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


##################################################
# Lab notebook
##################################################
class DocumentInline(TabularInline):
    model = Document
    extra = 0
    tab = True
    per_page = 10
    fields = ("name", "file", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Tag)
class TagAdmin(UnfoldReversionAdmin):
    search_fields = ("name",)


class NotebookTagInline(TabularInline):
    """
    Inline for the through table.
    This lets you add/remove tags from within the notebook admin page.
    """

    model = LNotebookTag
    extra = 0
    tab = True
    autocomplete_fields = ("tag",)


@admin.register(LNotebook)
class LNotebookAdmin(UnfoldReversionAdmin):
    inlines = [NotebookTagInline, DocumentInline]

    list_display = ("name", "tags_badge", "created_at", "updated_at")
    search_fields = ("name", "tags__name")
    ordering = ("-updated_at",)
    readonly_fields = ("created_at", "updated_at")
    list_filter = ("tags",)

    tabs = [
        ("General", {"fields": ("name",)}),
        ("Content", {"fields": ("content",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
        # Tag + Document appear as their own tabs because inline.tab=True
    ]

    @display(description="Tags")
    def tags_badge(self, obj: "LNotebook"):
        tags = list(obj.tags.all().only("name", "color"))
        if not tags:
            return "—"

        color_map = {
            "green": ("#16a34a", "#dcfce7"),
            "blue": ("#2563eb", "#dbeafe"),
            "yellow": ("#ca8a04", "#fef9c3"),
            "red": ("#dc2626", "#fee2e2"),
        }

        def chip(t):
            fg, bg = color_map.get(getattr(t, "color", ""), ("#334155", "#e2e8f0"))
            icon = "flag"

            return format_html(
                '<span style="display:inline-flex;align-items:center;gap:.35rem;'
                "padding:.125rem .5rem;border-radius:999px;"
                "color:{};background:{};font-weight:600;"
                'border:1px solid rgba(0,0,0,.08);margin-right:.35rem;">'
                '<span class="material-symbols-outlined" '
                'style="font-size:16px;line-height:1;">{}</span>'
                '<span style="white-space:nowrap;">{}</span>'
                "</span>",
                fg,
                bg,
                icon,
                t.name,
            )

        # join chips into one HTML output
        return format_html_join("", "{}", ((chip(t),) for t in tags))
