from django.contrib import admin
from accounts.admin import UnfoldReversionAdmin

from .models import (
    SampleType,
    Unit,
    Diagnosis,
    SampleStorage,
    MaritalStatus,
    SamplePreparation,
    CommunicationLanguage
)


@admin.register(Unit)
@admin.register(Diagnosis)
@admin.register(SampleType)
@admin.register(SampleStorage)
@admin.register(MaritalStatus)
@admin.register(SamplePreparation)
@admin.register(CommunicationLanguage)
class TermAdmin(UnfoldReversionAdmin):
    list_display = ("code", "display")
    search_fields = ("code", "display")
