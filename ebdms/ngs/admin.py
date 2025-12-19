# omics/admin.py
import json
from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from unfold.admin import ModelAdmin

from .models import Device, Target, Chemistry, OmicsFile


@admin.register(Device)
class DeviceAdmin(ModelAdmin):
    list_display = ("name", "vendor", "model")
    search_fields = ("name", "vendor", "model")
    list_filter = ("vendor",)
    ordering = ("name",)


@admin.register(Target)
class TargetAdmin(ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(Chemistry)
class ChemistryAdmin(ModelAdmin):
    list_display = ("name",)
    search_fields = ("name", "description")
    ordering = ("name",)


@admin.register(OmicsFile)
class OmicsFileAdmin(ModelAdmin):
    date_hierarchy = "created_at"

    list_display = (
        "id",
        "sample",
        "target",
        "device",
        "chemistry",
        "file_name",
        "md5",
        "created_at",
        "updated_at",
    )
    list_select_related = ("sample", "target", "device", "chemistry")
    list_filter = ("target", "device", "chemistry", "created_at")
    search_fields = (
        "sample__sample_id",
        "target",
        "device",
        "chemistry"
    )
    ordering = ("-created_at",)

    readonly_fields = (
        "md5",
        "created_at",
        "updated_at",
        "file_link",
        # Optional: pretty, read-only JSON views:
        "fastqc_metrics_pretty",
        "metadata_pretty",
    )

    fieldsets = (
        (None, {
            "fields": (
                ("sample", "target"),
                ("device", "chemistry"),
                "file",
                "file_link",
                "md5",
            )
        }),
        ("QC & Metadata", {
            "fields": (
                "fastqc_metrics",
                "fastqc_metrics_pretty",
                "metadata",
                "metadata_pretty",
            )
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )

    @admin.display(description="File")
    def file_name(self, obj: OmicsFile) -> str:
        return obj.file.name if obj.file else ""

    @admin.display(description="File link")
    def file_link(self, obj: OmicsFile):
        if not obj.file:
            return "-"
        try:
            url = obj.file.url
        except Exception:
            return obj.file.name
        return format_html('<a href="{}" target="_blank" rel="noopener">Open</a>', url)

    @admin.display(description="FastQC metrics (pretty)")
    def fastqc_metrics_pretty(self, obj: OmicsFile):
        return self._pretty_json(obj.fastqc_metrics)

    @admin.display(description="Metadata (pretty)")
    def metadata_pretty(self, obj: OmicsFile):
        return self._pretty_json(obj.metadata)

    def _pretty_json(self, value):
        if value in (None, "", {}):
            return "-"
        pretty = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False)
        # Unfold also supports JSON formatting/highlighting for readonly JSONFields
        # (with Pygments installed), but this method works regardless. :contentReference[oaicite:1]{index=1}
        return mark_safe(f"<pre style='white-space:pre-wrap;margin:0'>{pretty}</pre>")
