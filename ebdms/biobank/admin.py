import nested_admin
from django.contrib import admin
from reversion.admin import VersionAdmin
from django import forms
from django.contrib.admin.widgets import AdminSplitDateTime

from ehr.models import EHRRecord
from .models import Patient, Sample, Aliquot, Storage, Project, Term


class EHRRecordInline(nested_admin.NestedTabularInline):
    model = EHRRecord
    extra = 0

    exclude = ("data", )
    verbose_name = "Electronic health record"
    verbose_name_plural = "Electronic health records"
    show_change_link = True


class AliquotInline(nested_admin.NestedTabularInline):
    model = Aliquot
    extra = 0
    exclude = ("notes",)
    readonly_fields = ("aliquot_id",)
    show_change_link = True


class SampleInline(nested_admin.NestedStackedInline):
    model = Sample
    extra = 0
    exclude = ("notes",)
    readonly_fields = ("sample_id",)
    inlines = [AliquotInline]
    show_change_link = True


@admin.register(Patient)
class PatientAdmin(VersionAdmin, nested_admin.NestedModelAdmin):
    list_display = ("patient_id", "project", "sex", "date_of_birth", "diagnosis", "consent_status", "qr_code")
    search_fields = ("patient_id", "project__title", "diagnosis__name")
    list_filter = ("sex", "diagnosis", "consent_status", "project")
    readonly_fields = ("patient_id",)
    inlines = [EHRRecordInline, SampleInline]


@admin.register(Project)
class ProjectAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ("project_id", "title", "start_date", "end_date")
    search_fields = ("project_id", "title")


@admin.register(Storage)
class StorageAdmin(VersionAdmin, nested_admin.NestedModelAdmin):
    list_display = ("device_id", "location", "temperature", "storage_type")
    search_fields = ("device_id", "location")
    list_filter = ("storage_type",)


@admin.register(Sample)
class SampleAdmin(VersionAdmin, admin.ModelAdmin):
    search_fields = ("sample_id", "sample_type__name")
    inlines = [AliquotInline]


@admin.register(Aliquot)
class AliquotAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ("aliquot_id", "sample", "prepared_date")
    search_fields = ("aliquot_id", "sample__sample_id")


@admin.register(Term)
class TermAdmin(VersionAdmin, admin.ModelAdmin):
    list_display = ("category", "name", "description")
    list_filter = ("category",)
    search_fields = ("name", "description")
