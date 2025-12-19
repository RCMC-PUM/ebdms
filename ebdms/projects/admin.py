from django.contrib import admin

from unfold.admin import ModelAdmin, TabularInline
from simple_history.admin import SimpleHistoryAdmin

from biobank.models import Donor, Sample
from .models import Project, Institution, PrincipalInvestigator


# Inline(s)
class DonorInline(TabularInline):
    model = Donor
    extra = 0
    readonly_fields = ("donor_id",)
    show_change_link = True
    tab = True


class SampleInline(TabularInline):
    model = Sample
    extra = 0
    readonly_fields = ("sample_id",)
    show_change_link = True
    tab = True


# =====================================================
# Versioned Models
# =====================================================
@admin.register(Institution)
class InstitutionAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ("name", "department", "code")
    list_display_links = ("name",)
    search_fields = ("name", "department", "code")
    ordering = ("name",)


@admin.register(PrincipalInvestigator)
class PrincipalInvestigatorAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = ("name", "surname", "institution", "email")
    list_display_links = ("name", "surname")
    search_fields = ("name", "surname", "email", "institution__name", "institution__code")
    list_filter = ("institution",)
    ordering = ("surname", "name")
    autocomplete_fields = ("institution",)

@admin.register(Project)
class ProjectAdmin(SimpleHistoryAdmin, ModelAdmin):
    list_display = (
        "name",
        "code",
        "principal_investigator",
        "start_date",
        "end_date",
        "status",
    )
    list_filter = (
        "status",
        "principal_investigator",
        "start_date",
        "end_date",
    )
    search_fields = ("name", "code", "principal_investigator")
    inlines = [DonorInline, SampleInline]
