from django.contrib import admin
from core.admin import UnfoldReversionAdmin

from .models import (
    SampleType,
    Unit,
    ICDDiagnosis,
    RelationType,
    MaritalStatus,
    CollectionMethod,
    CommunicationLanguage,
)


@admin.register(Unit)
@admin.register(SampleType)
@admin.register(ICDDiagnosis)
@admin.register(RelationType)
@admin.register(MaritalStatus)
@admin.register(CollectionMethod)
@admin.register(CommunicationLanguage)
class TermAdmin(UnfoldReversionAdmin):
    list_display = ("code", "name")
    search_fields = ("code", "name")
