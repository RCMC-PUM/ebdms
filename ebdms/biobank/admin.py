from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from unfold.sections import TableSection
from unfold.paginator import InfinitePaginator
from unfold.admin import TabularInline

from accounts.admin import UnfoldReversionAdmin
from projects.models import Project  # noqa
from .models import (
    Storage,
    Patient,
    Sample,
    Aliquot,
)


# =====================================================
# Base registrations (simple models)
# =====================================================
@admin.register(Storage)
class StorageAdmin(UnfoldReversionAdmin):
    list_display = ("device_id", "location", "temperature")
    list_display_links = ("device_id",)
    search_fields = ("device_id", "location")
    ordering = ("device_id",)
    # list_filter = ("storage_type",)


# =====================================================
# Inline definitions
# =====================================================
class AliquotInline(TabularInline):
    model = Aliquot
    extra = 0
    readonly_fields = ("aliquot_id",)
    show_change_link = True
    exclude = ("notes",)
    tab = True


class SampleInline(TabularInline):
    model = Sample
    extra = 0
    readonly_fields = ("sample_id",)
    show_change_link = True
    exclude = ("notes",)
    tab = True


# =====================================================
# Sections definitions
# =====================================================
class AliquotTableSection(TableSection):
    fields = ["aliquot_id", "prepared_date", "preparation_method", "qr_code"]
    verbose_name = "Aliquots"
    related_name = "aliquots"
    height = 300


@admin.register(Patient)
class DonorAdmin(UnfoldReversionAdmin):
    paginator = InfinitePaginator
    show_full_result_count = False

    list_display = (
        "patient_id",
        "project",
        "institution",
        "sex",
        "consent_status",
    )
    list_display_links = ("patient_id",)
    list_filter = ("sex", "consent_status", "project", "institution")
    search_fields = ("patient_id", "project__name", "institution__name", "institution__code")
    readonly_fields = ("patient_id",)

    # Perf + UX
    list_select_related = ("project", "institution")
    autocomplete_fields = ("project", "institution")
    ordering = ("patient_id",)
    list_per_page = 50

    # Nicer change-form layout using Unfold fieldset tabs :contentReference[oaicite:3]{index=3}
    fieldsets = (
        ("Donor", {"fields": ("patient_id", "name", "surname", "sex", "date_of_birth", "diagnosis"), "classes": ("tab",)}),
        ("Information", {"fields": ("project", "institution", "consent_document", "consent_status"), "classes": ("tab",)}),
    )

    inlines = [SampleInline]


@admin.register(Sample)
class SampleAdmin(UnfoldReversionAdmin):
    paginator = InfinitePaginator
    show_full_result_count = False

    list_display = (
        "sample_id",
        "project",
        "donor",
        "collection_date",
        "qr_code",
    )
    list_display_links = ("sample_id",)
    list_filter = ("project", "collection_date")
    search_fields = ("sample_id", "donor__patient_id", "project__name")
    readonly_fields = ("sample_id", "qr_code")

    # Perf + UX
    list_select_related = ("project", "donor")
    autocomplete_fields = ("project", "donor")
    date_hierarchy = "collection_date"
    ordering = ("-collection_date", "sample_id")
    list_per_page = 10

    # Unfold expandable related table section :contentReference[oaicite:4]{index=4}
    list_sections = [AliquotTableSection]

    fieldsets = (
        ("Core", {"fields": ("sample_id", "project", "donor"), "classes": ("tab",)}),
        ("Collection", {"fields": ("collection_date",), "classes": ("tab",)}),
        ("Codes", {"fields": ("qr_code",), "classes": ("tab",)}),
    )


@admin.register(Aliquot)
class AliquotAdmin(UnfoldReversionAdmin):
    paginator = InfinitePaginator
    show_full_result_count = False

    list_display = (
        "aliquot_id",
        "sample",
        "prepared_date",
    )
    list_display_links = ("aliquot_id",)
    list_filter = ("prepared_date",)
    search_fields = ("aliquot_id", "sample__sample_id")
    readonly_fields = ("aliquot_id", "qr_code")

    # Perf + UX
    list_select_related = ("sample",)
    autocomplete_fields = ("sample",)
    date_hierarchy = "prepared_date"
    ordering = ("-prepared_date", "aliquot_id")
    list_per_page = 50

    fieldsets = (
        ("Core", {"fields": ("aliquot_id", "sample"), "classes": ("tab",)}),
        ("Preparation", {"fields": ("prepared_date", "preparation_method"), "classes": ("tab",)}),
        ("Codes", {"fields": ("qr_code",), "classes": ("tab",)}),
    )


# =====================================================
# AdminSite app ordering (Unfold compatible)
# =====================================================
def get_app_list(self, request, app_label=None):
    """
    Ensure proper app listing with Unfold + Guardian
    """
    app_dict = self._build_app_dict(request, app_label)
    return sorted(app_dict.values(), key=lambda x: x["name"].lower())


admin.AdminSite.get_app_list = get_app_list
