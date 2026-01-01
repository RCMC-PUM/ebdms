from django.db import models
from django.utils import timezone

from core.models import Model
from projects.models import Participant


class Form(Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return self.name


class FormField(Model):
    class FieldType(models.TextChoices):
        TEXT = "text", "Text"
        INTEGER = "integer", "Integer"
        DECIMAL = "decimal", "Decimal"
        BOOLEAN = "boolean", "Boolean"
        DATE = "date", "Date"
        DATETIME = "datetime", "Datetime"
        CHOICE = "choice", "Choice"
        MULTICHOICE = "multichoice", "Multi-choice"

    order = models.PositiveIntegerField(default=0, db_index=True)
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="fields")

    label = models.CharField(max_length=255)
    help_text = models.TextField(blank=True, default="")

    field_type = models.CharField(
        max_length=20, choices=FieldType.choices, default=FieldType.TEXT
    )
    required = models.BooleanField(default=False)

    # Only for CHOICE / MULTICHOICE
    choices = models.CharField(
        blank=True,
        null=True,
        max_length=1024,
        help_text="Comma-separated values, e.g. a,b,c,d",
    )

    class Meta:
        ordering = ("order",)
        constraints = [
            models.UniqueConstraint(
                fields=["form", "label"], name="uniq_form_field_label"
            ),
            models.UniqueConstraint(
                fields=["form", "order"], name="uniq_form_field_order"
            ),
        ]

    def __str__(self) -> str:
        return str(self.label)


class Response(Model):
    participant = models.ForeignKey(Participant, on_delete=models.PROTECT)
    form = models.ForeignKey(Form, on_delete=models.PROTECT)
    result = models.JSONField(default=dict)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["participant", "form"], name="uniq_response_participant_form"
            ),
        ]

    def __str__(self) -> str:
        return f"Response(form={self.form_id}, participant={self.participant_id})"


class Assignment(Model):
    """
    Links a Form to a Participant and generates an unguessable token
    used to build a fill URL.
    """

    participant = models.ForeignKey(
        Participant, on_delete=models.CASCADE, related_name="ehr_assignments"
    )
    form = models.ForeignKey(Form, on_delete=models.CASCADE, related_name="assignments")
    # TODO add nullable, and on_delete=CASCADE relation to Response or NOT ?

    # optional workflow flags
    is_active = models.BooleanField(default=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["participant", "form"], name="uniq_assignment_participant_form"
            ),
        ]

    def mark_completed(self):
        self.completed_at = timezone.now()
        self.save(update_fields=["completed_at", "updated_at"])

    def __str__(self) -> str:
        return f"Form {self.form.name} for {self.participant}"
