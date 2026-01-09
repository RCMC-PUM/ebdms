from django.contrib import admin
from core.admin import UnfoldReversionAdmin

from .models import (
    Device,
    Target,
    Chemistry,
    Repository,
    OmicsArtifact,
)


@admin.register(Device)
class DeviceAdmin(UnfoldReversionAdmin):
    list_display = ("name", "vendor", "model")
    search_fields = ("name", "vendor", "model")
    list_filter = ("vendor",)
    ordering = ("name",)


@admin.register(Repository)
class TargetAdmin(UnfoldReversionAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Target)
class TargetAdmin(UnfoldReversionAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Chemistry)
class ChemistryAdmin(UnfoldReversionAdmin):
    list_display = ("name",)
    search_fields = ("name", "description")
    ordering = ("name",)


@admin.register(OmicsArtifact)
class OmicsArtifactAdmin(UnfoldReversionAdmin):
    list_display = (
        "id",
        "project",
        "specimen",
        "target",
        "device",
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)
    list_per_page = 50
    show_full_result_count = False

    list_filter = ("chemistry", "target", "device")
    autocomplete_fields = ("project", "specimen", "target", "device", "chemistry")
    readonly_fields = ("metadata", "created_at", "updated_at")

    fieldsets = (
        (
            "Data",
            {
                "fields": (
                    ("project",),
                    ("specimen",),
                    ("device", "target", "chemistry"),
                    ("file", "index", "qc_metrics"),
                    ("created_at", "updated_at"),
                )
            },
        ),
        ("Data external storage", {"fields": ("repository_name", "repository_id")}),
        ("Metadata", {"fields": ("metadata",)}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related("project", "specimen", "target", "device", "chemistry")
