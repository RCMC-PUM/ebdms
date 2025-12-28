from django.contrib import admin
from accounts.admin import UnfoldReversionAdmin

from .models import (
    SampleType,
    Unit,
    ICDDiagnosis,
    MaritalStatus,
    SamplePreparation,
    CommunicationLanguage
)


@admin.register(Unit)
@admin.register(SampleType)
@admin.register(ICDDiagnosis)
@admin.register(MaritalStatus)
@admin.register(SamplePreparation)
@admin.register(CommunicationLanguage)
class TermAdmin(UnfoldReversionAdmin):
    list_display = ("code", "display")
    search_fields = ("code", "display")
