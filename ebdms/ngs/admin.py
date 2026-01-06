# omics/admin.py
import json
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from unfold.decorators import display
from core.admin import UnfoldReversionAdmin

from .models import (
    Device,
    Target,
    Chemistry,
    OmicsArtifact,
)  # <- rename to your actual model


@admin.register(Device)
class DeviceAdmin(UnfoldReversionAdmin):
    list_display = ("name", "vendor", "model")
    search_fields = ("name", "vendor", "model")
    list_filter = ("vendor",)
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
    ordering = ("-created_at",)

    list_display = (
        "id",
        "project",
        "specimen",
        "target",
        "device",
        "created_at",
        "updated_at",
    )

    # Important: select_related deep joins to avoid N+1 when rendering participant
    list_select_related = (
        "project",
        "specimen",
        "target",
        "device",
        "chemistry",
    )

    list_filter = ("project", "target", "device", "chemistry", "created_at")
    autocomplete_fields = ("project", "specimen", "target", "device", "chemistry")
    readonly_fields = (
        "metadata",
        "created_at",
        "updated_at",
    )

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
                ),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("metadata",),
            },
        ),
    )
