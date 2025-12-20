from django.db import models
from django.contrib import admin

from unfold.contrib.forms.widgets import WysiwygWidget
from unfold.admin import TabularInline, StackedInline
from accounts.admin import UnfoldReversionAdmin

from .models import Participant, Project, ProjectDocuments, Institution, PrincipalInvestigator


# =========================
# Inlines
# =========================
class ParticipantInline(TabularInline):
    model = Participant
    extra = 0
    show_change_link = True
    tab = True

    fields = (
        "pk",
        "active",
        "surname",
        "name",
        "gender",
        "birth_date",
    )
    readonly_fields = ("pk",)
    autocomplete_fields = ("project",)  # harmless if you later move participant off project


class DocumentInline(StackedInline):
    model = ProjectDocuments
    extra = 0
    show_change_link = True
    tab = True
    fields = ("name", "document", "uploaded_at")
    readonly_fields = ("uploaded_at",)


# =========================
# Admins
# =========================
@admin.register(Institution)
class InstitutionAdmin(UnfoldReversionAdmin):
    list_display = ("name", "department", "code", "address")
    list_display_links = ("name",)
    search_fields = ("name", "department", "code", "address")
    ordering = ("name", "department", "code")


@admin.register(PrincipalInvestigator)
class PrincipalInvestigatorAdmin(UnfoldReversionAdmin):
    list_display = ("surname", "name", "institution", "email", "phone")
    list_display_links = ("surname", "name")
    search_fields = (
        "name",
        "surname",
        "email",
        "phone",
        "institution__name",
        "institution__code",
    )
    list_filter = ("institution",)
    ordering = ("surname", "name")
    autocomplete_fields = ("institution",)
    list_select_related = ("institution",)


@admin.register(Project)
class ProjectAdmin(UnfoldReversionAdmin):
    list_display = (
        "name",
        "code",
        "principal_investigator",
        "start_date",
        "end_date",
        "status",
        "is_active",
    )
    list_filter = (
        "status",
        "principal_investigator",
        "start_date",
        "end_date",
    )
    search_fields = (
        "name",
        "code",
        "principal_investigator__name",
        "principal_investigator__surname",
        "principal_investigator__email",
    )
    ordering = ("-start_date", "code")
    date_hierarchy = "start_date"
    autocomplete_fields = ("principal_investigator",)
    list_select_related = ("principal_investigator",)

    # Skip Sample inline (per your request)
    inlines = [DocumentInline, ParticipantInline]

    formfield_overrides = {
        models.TextField: {
            "widget": WysiwygWidget,
        }
    }


@admin.register(Participant)
class ParticipantAdmin(UnfoldReversionAdmin):
    # Make list view useful
    list_display = (
        "pk",
        "project",
        "active",
        "surname",
        "name",
        "gender",
        "birth_date",
        "email",
    )
    list_display_links = ("pk",)
    list_filter = ("active", "gender", "project")
    search_fields = (
        "name",
        "surname",
        "email",
        "project__name",
        "project__code",
    )
    ordering = ("pk",)
    autocomplete_fields = ("project", "marital_status", "communication")
    list_select_related = ("project", "marital_status", "communication")

    # Nice readonly rendering of generated FHIR JSON
    readonly_fields = ("pk", "fhir_object")

    fieldsets = (
        ("Core", {"fields": ("project", "pk", "active"), "classes": ("tab",)}),
        ("Identity", {"fields": ("name", "surname", "gender", "birth_date"), "classes": ("tab",)}),
        ("Contact", {"fields": ("email", "phone_number_prefix", "phone_number"), "classes": ("tab",)}),
        ("Address", {"fields": ("address",), "classes": ("tab",)}),
        ("Status", {"fields": ("marital_status", "deceased", "deceased_date_time"), "classes": ("tab",)}),
        ("Communication", {"fields": ("communication",), "classes": ("tab",)}),
        ("FHIR", {"fields": ("fhir_object",), "classes": ("tab",)}),
    )
