import base64
from io import BytesIO

import qrcode
from django.urls import reverse
from django.contrib import admin
from django.utils.safestring import mark_safe
from django.utils.html import format_html

from unfold.admin import TabularInline, StackedInline
from unfold.decorators import display

from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from import_export.admin import ImportExportModelAdmin

from ehr.models import Assignment
from accounts.admin import UnfoldReversionAdmin

from .models import Participant, Project, ProjectDocuments, Institution, PrincipalInvestigator


# =========================
# Inlines
# =========================
class ParticipantInline(TabularInline):
    model = Participant
    extra = 0
    tab = True
    show_change_link = True

    fields = (
        "identifier",
        "active",
        "surname",
        "name",
        "gender",
        "birth_date",
    )
    readonly_fields = ("identifier",)
    autocomplete_fields = ("project",)  # harmless if you later move participant off project


class AssigmentInline(TabularInline):
    model = Assignment
    extra = 0
    tab = True
    fields = (
        "participant",
        "form",
        "is_active",
        "completed_at",
        "fill_link"
    )
    readonly_fields = ("fill_link", "is_active", "completed_at")

    @admin.display(description="Fill")
    def fill_link(self, obj: Assignment):
        if not obj.pk or not obj.form.is_active:
            return "—"
        url = reverse("admin:ehr_assignment_fill", args=[obj.pk])
        return format_html(
            '<a href="{}" >Fill ➡️</a>',
            url,
        )



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


@admin.register(Participant)
class ParticipantAdmin(UnfoldReversionAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm

    list_display = (
        "identifier",
        "project",
        "active",
        "surname",
        "name",
        "gender",
        "birth_date",
        "email",
    )

    ordering = ("pk",)
    inlines = [AssigmentInline]

    list_display_links = ("identifier",)
    list_filter = ("active", "gender", "project")
    search_fields = ("identifier", "name", "surname", "email")

    autocomplete_fields = ("project", "marital_status", "communication")
    list_select_related = ("project", "marital_status", "communication")
    readonly_fields = ("pk", "identifier", "qr_code")

    @display(description="QR code")
    def qr_code(self, obj):
        if not obj or not obj.identifier:
            return "—"

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(obj.identifier)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()

        img.save(buffer, format="PNG")
        b64 = base64.b64encode(buffer.getvalue()).decode("ascii")

        return mark_safe(f'<img src="data:image/png;base64,{b64}" class="qr"/>')

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    ("identifier",),
                    ("project", "institution"),
                    ("name", "surname"),
                    ("gender", "birth_date"),
                    ("active",)
                ),
                "classes": ("tab",),
            },
        ),
        ("Contact", {"fields": ("address", "email", "phone_number_prefix", "phone_number"), "classes": ("tab",)}),
        ("Status", {"fields": ("marital_status", "deceased", "deceased_date_time"), "classes": ("tab",)}),
        ("Communication", {"fields": ("communication",), "classes": ("tab",)}),
        ("QR", {"fields": ("qr_code",), "classes": ("tab",)})
    )
