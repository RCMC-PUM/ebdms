from django.db import models
from django_jsonform.models.fields import JSONField
from biobank.models import Patient


class EHRModel(models.Model):
    """Defines a dynamic form schema for Electronic Health Records."""
    ITEMS = {
            "type": "array",
            "items": {
                "type": "object",
                "title": "Field",
                "properties": {
                    "name": {"type": "string", "title": "Field Name"},
                    "type": {
                        "type": "string",
                        "title": "Field Type",
                        "enum": [
                            "text", "int", "float", "bool",
                            "choice", "multichoice",
                            "date", "datetime", "time",
                            "email", "url", "phone",
                        ],
                    },
                    "label": {"type": "string", "title": "Label"},
                    "required": {"type": "boolean", "title": "Required"},
                    "choices": {
                        "type": "array",
                        "title": "Choices (if type=choice/multichoice)",
                        "items": {"type": "string"},
                    },
                },
                "required": ["name", "type"],
            },
        }
    name = models.CharField(max_length=255)
    schema = JSONField(
        schema=ITEMS,
        default=list
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "EHR Form"
        verbose_name_plural = "EHR Forms"  # shows as “EHR Forms” in admin


class EHRRecord(models.Model):
    """Stores filled data for a given EHRForm."""
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, null=True, blank=True)
    form = models.ForeignKey(EHRModel, on_delete=models.CASCADE, null=True, blank=True)
    data = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Record for {self.form.name}"

    class Meta:
        verbose_name = "EHR Record"
        verbose_name_plural = "EHR Records"  # shows as “EHR Records” in admin
