from django.db import models
from django.utils import timezone
from django.utils.crypto import get_random_string

from projects.models import Participant


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        abstract = True


class Form(TimeStampedModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class FormField(TimeStampedModel):
    class FieldType(models.TextChoices):
        TEXT = "text", "Text"
        INTEGER = "integer", "Integer"
        DECIMAL = "decimal", "Decimal"
        BOOLEAN = "boolean", "Boolean"
        DATE = "date", "Date"
        DATETIME = "datetime", "Datetime"
        CHOICE = "choice", "Choice"
        MULTICHOICE = "multichoice", "Multi-choice"

    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="fields")

    key = models.SlugField(max_length=100)  # TODO slug name by def! (autocomplete)
    label = models.CharField(max_length=255)
    help_text = models.TextField(blank=True, default="")
    field_type = models.CharField(max_length=20, choices=FieldType.choices, default=FieldType.TEXT)
    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    # Only for CHOICE / MULTICHOICE
    choices = models.CharField(blank=True, null=True, max_length=1024, help_text="Comma-separated values, e.g. a,b,c,d")

    class Meta:
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(fields=["form", "key"], name="uniq_form_field_key"),
        ]

    def __str__(self) -> str:
        return f"{self.form_id}:{self.key}"


class Response(TimeStampedModel):
    participant = models.ForeignKey(Participant, on_delete=models.PROTECT)
    form = models.ForeignKey(Form, on_delete=models.PROTECT)
    result = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["participant", "form"], name="uniq_response_participant_form"),
        ]

    def __str__(self) -> str:
        return f"Response(form={self.form_id}, participant={self.participant_id})"


class Assignment(TimeStampedModel):
    """
    Links a Form to a Participant and generates an unguessable token
    used to build a fill URL.
    """
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name="ehr_assignments")
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="assignments")
    # TODO add nullable, and on_delete=CASCADE relation to Response or NOT ? 

    # optional workflow flags
    is_active = models.BooleanField(default=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["participant", "form"], name="uniq_assignment_participant_form"),
        ]

    def mark_completed(self):
        self.completed_at = timezone.now()
        self.save(update_fields=["completed_at", "updated_at"])

    def __str__(self) -> str:
        return f"Form {self.form.name} for {self.participant}"
