from django.contrib import admin

from unfold.decorators import display
from unfold.admin import TabularInline
from unfold.sections import TableSection
from unfold.paginator import InfinitePaginator

from core.admin import UnfoldReversionAdmin
from core.qr import qr_img_tag

from .models import (
    Storage,
    Box,
    ProcessingProtocol,
    Specimen,
    Aliquot,
)


# =============================================================================
# Inlines
# =============================================================================


class BoxInline(TabularInline):
    model = Box
    extra = 0
    tab = True
    per_page = 10
    show_change_link = True

    fields = (
        "name",
        "rows",
        "cols",
        "n_samples",
        "n_total_samples",
        "occupation_percent",
    )
    readonly_fields = ("n_samples", "n_total_samples", "occupation_percent")


class AliquotInline(TabularInline):
    model = Aliquot
    extra = 0
    tab = True
    per_page = 10
    show_change_link = True

    fields = (
        "identifier",
        "sample_type",
        "box",
        "row",
        "col",
        "created_at",
        "updated_at",
    )
    readonly_fields = (
        "identifier",
        "sample_type",
        "box",
        "row",
        "col",
        "created_at",
        "updated_at",
    )


# =============================================================================
# Sections (list view expandable tables)
# =============================================================================
class AliquotTableSection(TableSection):
    verbose_name = "Aliquots"
    related_name = "aliquots"
    height = 300

    # Keep it simple + fast
    show_change_link = True
    fields = ["identifier", "sample_type", "box", "row", "col", "created_at"]


# =============================================================================
# Storage
# =============================================================================


@admin.register(Storage)
class StorageAdmin(UnfoldReversionAdmin):
    paginator = InfinitePaginator
    show_full_result_count = False

    list_display = ("name", "location", "conditions")
    list_display_links = ("name",)

    search_fields = ("name", "location", "conditions")
    ordering = ("name",)
    list_per_page = 50

    fieldsets = (
        ("Core", {"fields": ("name", "location")}),
        ("Conditions", {"fields": ("conditions",)}),
        ("Sensors", {"fields": ("sensors",)}),
    )

    readonly_fields = ("sensors",)
    inlines = [BoxInline]


# =============================================================================
# Box
# =============================================================================


@admin.register(Box)
class BoxAdmin(UnfoldReversionAdmin):
    list_display = (
        "name",
        "storage",
        "rack_level",
        "rack_row",
        "rack_col",
        "n_samples",
        "n_total_samples",
        "occupation_percent",
    )
    list_per_page = 50

    list_display_links = ("name",)
    list_filter = ("storage",)

    search_fields = ("name", "storage__name", "storage__location")
    ordering = ("updated_at",)

    list_select_related = ("storage",)
    autocomplete_fields = ("storage",)

    fieldsets = (
        (
            "Location",
            {"fields": ("name", "storage", "rack_level", "rack_row", "rack_col")},
        ),
        (
            "Box dimensions",
            {
                "fields": (
                    "rows",
                    "cols",
                )
            },
        ),
        (
            "Box capacity",
            {"fields": ("n_samples", "n_total_samples", "occupation_percent")},
        ),
    )

    readonly_fields = ("n_samples", "n_total_samples", "occupation_percent")
    inlines = [AliquotInline]

    def n_samples(self, obj):
        return getattr(obj, "_aliquots_count", obj.n_samples)

    n_samples.short_description = "Occupied"

    def n_total_samples(self, obj):
        return obj.n_total_samples

    n_total_samples.short_description = "Capacity"

    def occupation_percent(self, obj):
        return obj.occupation_percent

    occupation_percent.short_description = "Occupancy %"


# =============================================================================
# Processing Protocol
# =============================================================================


@admin.register(ProcessingProtocol)
class ProcessingProtocolAdmin(UnfoldReversionAdmin):
    list_display = ("name",)
    list_display_links = ("name",)
    search_fields = ("name", "description")

    ordering = ("name",)
    list_per_page = 50

    fieldsets = (
        (None, {"fields": ("name",)}),
        ("Description", {"fields": ("description",)}),
        ("Attachment", {"fields": ("file",)}),
    )


# =============================================================================
# Specimen
# =============================================================================


@admin.register(Specimen)
class SpecimenAdmin(UnfoldReversionAdmin):
    list_display = (
        "identifier",
        "project",
        "participant",
        "sample_type",
        "created_at",
    )

    list_display_links = ("identifier",)
    list_filter = ("sample_type",)

    search_fields = (
        "identifier",
        "project__name",
        "project__code",
        "participant__identifier",
        "participant__name",
        "participant__surname",
    )

    readonly_fields = ("identifier", "created_at", "updated_at")
    autocomplete_fields = ("project", "participant", "sample_type")

    ordering = ("-id",)
    list_per_page = 50
    show_full_result_count = False

    list_sections = [AliquotTableSection]

    fieldsets = (
        (
            "Specimen",
            {
                "fields": ("identifier", "project", "participant", "sample_type"),
                "classes": ("tab",),
            },
        ),
        ("Notes", {"fields": ("note",), "classes": ("tab",)}),
        ("Metadata", {"fields": ("created_at", "updated_at"), "classes": ("tab",)}),
    )

    inlines = [AliquotInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Prevent N+1 for list_display
        return qs.select_related("project", "participant", "sample_type")


# =============================================================================
# Aliquot
# =============================================================================


@admin.register(Aliquot)
class AliquotAdmin(UnfoldReversionAdmin):
    list_display = (
        "identifier",
        "specimen",
        "sample_type",
        "box",
        "row",
        "col",
        "created_at",
    )
    list_display_links = ("identifier",)

    show_full_result_count = False
    list_per_page = 50
    ordering = ("-id",)

    list_filter = ("created_at", "sample_type", "box__storage")

    search_fields = (
        "identifier",
        "specimen__identifier",
        "specimen__participant__name",
        "specimen__participant__surname",
    )

    readonly_fields = ("identifier", "created_at", "updated_at")
    autocomplete_fields = ("specimen", "box")

    fieldsets = (
        ("Source", {"fields": ("identifier", "specimen")}),
        ("Placement", {"fields": ("box", "row", "col")}),
        ("Metadata", {"fields": ("created_at", "updated_at")}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        return qs.select_related(
            "specimen",
            "box",
            "specimen__participant",
            "specimen__project",
        )


# =============================================================================
# AdminSite app ordering (Unfold compatible)
# =============================================================================


def get_app_list(self, request, app_label=None):
    """
    Ensure proper app listing with Unfold + Guardian.
    """
    app_dict = self._build_app_dict(request, app_label)
    return sorted(app_dict.values(), key=lambda x: x["name"].lower())


admin.AdminSite.get_app_list = get_app_list
