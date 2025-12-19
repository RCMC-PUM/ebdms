from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import (
    SampleType,
    Unit,
    Diagnosis,
    SampleStorage,
    SamplePreparation,
)


@admin.register(Unit)
@admin.register(Diagnosis)
@admin.register(SampleType)
@admin.register(SampleStorage)
@admin.register(SamplePreparation)
class TermAdmin(ModelAdmin):
    list_display = ("name",)
    search_fields = ("name", "description")
