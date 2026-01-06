from django.urls import reverse
from django.contrib import admin
from django.utils.html import format_html

from unfold.contrib.inlines.admin import NonrelatedTabularInline
from unfold.admin import TabularInline, StackedInline
from unfold.decorators import display

from unfold.contrib.import_export.forms import ImportForm, SelectableFieldsExportForm
from import_export.admin import ImportExportModelAdmin

from ehr.models import Assignment
from ngs.models import OmicsArtifact

from core.qr import qr_img_tag
from core.admin import UnfoldReversionAdmin

from .models import (
    Participant,
    ParticipantRelation,
    Project,
    AssociatedFile,
    Institution,
    PrincipalInvestigator,
)


# =========================
# Inlines
# =========================
class ParticipantInline(TabularInline):
    model = Participant

    compressed_fields = True
    show_change_link = True
    per_page = 10
    tab = True
    extra = 0

    fields = (
        "identifier",
        "surname",
        "name",
        "gender",
        "birth_date",
        "active",
        "qr_code"
    )
    readonly_fields = (
        "identifier",
        "surname",
        "name",
        "gender",
        "birth_date",
        "active",
        "qr_code"
    )

    if fields != readonly_fields:
        raise ValueError(
            "For 'Participant' inline located in 'Project' admin view all fields have to be readonly!"
        )

    @display(
        description="QR",
        label=True
    )
    def qr_code(self, obj):
        return qr_img_tag(obj.identifier, width=50, height=50)

    def has_add_permission(self, request, obj):
        return None


class AssigmentInline(TabularInline):
    model = Assignment
    extra = 0
    per_page = 10

    tab = True
    fields = ("participant", "form", "is_active", "completed_at", "fill_link")
    readonly_fields = ("fill_link", "is_active", "completed_at")

    @display(description="Fill")
    def fill_link(self, obj: Assignment):
        if not obj.pk or not obj.form.is_active:
            return "—"
        url = reverse("admin:ehr_assignment_fill", args=[obj.pk])
        return format_html(
            '<a href="{}" >Fill ➡️</a>',
            url,
        )


class FilesInline(StackedInline):
    model = AssociatedFile
    extra = 0
    per_page = 10

    show_change_link = True
    tab = True

    fields = ("name", "category", "document", "created_at", "updated_at")
    readonly_fields = ("created_at", "updated_at")


class ParticipantRelationInline(TabularInline):
    model = ParticipantRelation
    fk_name = "from_participant"
    extra = 0
    tab = True
    per_page = 10

    autocomplete_fields = ("to_participant",)
    fields = ("relation_type", "to_participant", "note", "created_at")
    readonly_fields = ("created_at",)

    verbose_name = "Relation"
    verbose_name_plural = "Relations"


# =========================
# Non directly related inlines
# =========================
class OmicsParticipantInline(NonrelatedTabularInline):
    model = OmicsArtifact

    tab = True
    extra = 0
    per_page = 10
    show_change_link = True

    link_fields = ()
    fields = ("target", "device", "chemistry")
    readonly_fields = ("target", "device", "chemistry")

    def get_form_queryset(self, obj):
        """
        Gets all nonrelated objects needed for inlines. Method must be implemented.
        """
        return self.model.objects.filter(aliquot__specimen__participant=obj).all()

    def save_new_instance(self, parent, instance):
        """
        Extra save method which can for example update inline instances based on current
        main model object. Method must be implemented.
        """
        pass

    def has_add_permission(self, request, obj=None):
        return False


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
        "number_of_assigned_participants",
        "is_active",
    )
    readonly_fields = ("number_of_assigned_participants",)

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

    ordering = ("-start_date",)
    autocomplete_fields = ("principal_investigator",)
    list_select_related = ("principal_investigator",)

    @display(description="Assigned participants")
    def number_of_assigned_participants(self, obj: Participant) -> int:
        return obj.n_participants

    # Skip Sample inline (per your request)
    inlines = [FilesInline, ParticipantInline]


@admin.register(Participant)
class ParticipantAdmin(UnfoldReversionAdmin, ImportExportModelAdmin):
    import_form_class = ImportForm
    export_form_class = SelectableFieldsExportForm

    list_select_related = ("project", "institution", "marital_status", "communication")
    list_display = (
        "identifier",
        "project",
        "active",
        "surname",
        "name",
        "gender",
        "birth_date",
        "healthy_badge",
        "qr_code"
    )

    list_display_links = ("identifier", "project")
    list_filter = ("active", "gender", "project", "institution")
    search_fields = ("identifier", "name", "surname", "email")

    autocomplete_fields = (
        "project",
        "institution",
        "marital_status",
        "communication",
        "icd",
    )

    inlines = [AssigmentInline, ParticipantRelationInline, OmicsParticipantInline]
    readonly_fields = ("identifier", "created_at", "updated_at")

    @display(
        description="QR",
        image=True,
    )
    def qr_code(self, obj):
        return qr_img_tag(obj.identifier)

    @display(boolean=True, description="Healthy")
    def healthy_badge(self, obj: Participant) -> bool:
        return obj.is_healthy

    fieldsets = (
        (
            "Identity",
            {
                "fields": (
                    ("identifier",),
                    ("project", "institution"),
                    ("name", "surname"),
                    ("gender", "birth_date", "marital_status"),
                ),
            },
        ),
        (
            "Contact",
            {
                "fields": (
                    ("email",),
                    ("phone_number_prefix", "phone_number"),
                    ("communication",),
                ),
            },
        ),
        (
            "Address",
            {
                "fields": (
                    ("street", "street_number", "apartment"),
                    ("postal_code", "city"),
                    ("country",),
                ),
            },
        ),
        (
            "Clinical",
            {
                "fields": (
                    ("icd",),
                    ("deceased", "deceased_date_time"),
                ),
            },
        ),
        (
            "ICF",
            {
                "fields": ("consent_status", "consent_file", "consent_signed_at"),
            },
        ),
        (
            "Record status",
            {
                "fields": ("active", "created_at", "updated_at"),
            },
        ),
    )
