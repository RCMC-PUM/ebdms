from typing import Any, Dict, List

from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from ontologies.models import MaritalStatus, CommunicationLanguage


# Helpers
def _strip_empty(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v not in (None, [], {}, "")}


def _fhir_identifier(value: str, system: str | None = None) -> Dict[str, Any]:
    out: Dict[str, Any] = {"value": value}
    if system:
        out["system"] = system
    return out


class Institution(models.Model):
    name = models.CharField(max_length=1024)
    department = models.CharField(max_length=1024, null=True, blank=True)

    address = models.CharField(max_length=1024, unique=True, blank=True, null=True)
    code = models.CharField(max_length=12, unique=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "department"],
                name="unique_institution_name_department",
            )
        ]

    def __str__(self):
        return f"{self.department} ({self.name})"


class PrincipalInvestigator(models.Model):
    name = models.CharField(max_length=512)
    surname = models.CharField(max_length=512)

    email = models.EmailField()
    phone = models.CharField(max_length=22, blank=True, null=True)

    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.name} {self.surname} from ({self.institution})"


class Project(models.Model):
    name = models.CharField(max_length=512, unique=True, help_text="Project name.")
    code = models.CharField(max_length=6, unique=True, help_text="Project code.")

    description = models.TextField(max_length=2048, blank=True, default="", help_text="Project description.")
    principal_investigator = models.ForeignKey(PrincipalInvestigator, on_delete=models.PROTECT, help_text="Project principal investigator (PI).")
    status = models.BooleanField(default=True, help_text="Project status (active / inactive).")

    start_date = models.DateField(help_text="Project start date.")
    end_date = models.DateField(blank=True, null=True, help_text="Project end date.")

    class Meta:
        ordering = ["start_date"]

    def clean(self):
        # deceased logic validation[x]
        if not self.status and not self.end_date:
            raise ValidationError("If project is inactive please provide end date.")

    @property
    def is_active(self):
        if not self.status:
            return False
        if self.end_date is None:
            return True
        return self.end_date > timezone.now()

    def __str__(self):
        return self.name


class ProjectDocuments(models.Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="documents",
        help_text="Select the project this document belongs to."
    )

    name = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Provide document (unique) name."
    )

    description = models.TextField(
        null=True,
        blank=True,
        help_text="Provide document description."
    )

    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        help_text="Document creation date."
    )

    document = models.FileField(
        upload_to=f"documents/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "xlsx", "csv", "html"])],
        help_text="Upload file."
    )

    class Meta:
        verbose_name = "Project's Document"
        verbose_name_plural = "Project's Documents"

    def __str__(self):
        return self.name


class Participant(models.Model):
    """
    Participant = FHIR Patient.

    Uses JSONField for FHIR complex datatypes:
      - Identifier, HumanName, ContactPoint, Address, CodeableConcept, Attachment,
        Period, Reference, Annotation.

    Field names match your pasted Patient schema.
    """
    identifier = models.CharField(unique=True, editable=False)

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        help_text="Select the project this participant belongs to.",
    )

    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        null=True,  # TODO: null = False
        help_text="Institution this participant is associated with."
    )

    active = models.BooleanField(
        default=True,
        help_text="FHIR Patient.active — whether this patient's record is in active use.",
    )

    name = models.CharField(
        help_text="Participant name",
    )

    surname = models.CharField(
        help_text="Participant surname",
    )

    email = models.EmailField(
        null=True,
        blank=True,
        help_text="Participant email address (Optional)."
    )

    phone_number_prefix = models.CharField(
        max_length=3,
        null=True,
        blank=True,
        help_text="Participant phone number prefix (Optional). E.g +48"
    )
    phone_number = models.IntegerField(
        null=True,
        blank=True,
        help_text="Participant phone number (Optional). E.g. 123456789"
    )

    class Gender(models.TextChoices):
        MALE = "male", "male"
        FEMALE = "female", "female"
        OTHER = "other", "other"
        UNKNOWN = "unknown", "unknown"

    gender = models.CharField(
        max_length=7,
        choices=Gender.choices,
        default=Gender.UNKNOWN,
        help_text="Participant gender — male | female | other | unknown.",
    )

    birth_date = models.DateField(
        null=True,
        blank=True,
        help_text="Participant birth date.",
    )

    address = models.TextField(
        null=True,
        blank=True,
        help_text="FHIR Patient.address[*] (Address list).",
    )

    marital_status = models.ForeignKey(
        MaritalStatus,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Participant marital status.",
    )

    # deceased[x] choice
    deceased = models.BooleanField(
        null=True,
        blank=True,
        help_text="Deceased?",
    )
    deceased_date_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Deceased date.",
    )

    communication = models.ForeignKey(
        CommunicationLanguage,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Preferred communication language.",
    )

    class Meta:
        ordering = ["pk", "project"]
        verbose_name = "Participant"
        verbose_name_plural = "Participants"

    def __str__(self) -> str:
        return f"{self.name} {self.surname} ({self.identifier})"

    def clean(self):
        # deceased logic validation[x]
        if self.deceased is not None and self.deceased_date_time is not None:
            raise ValidationError("Deceased cannot be False when deceased date time is provided.")

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # First save to get PK
        super().save(*args, **kwargs)

        # Generate identifier only once
        if is_new and not self.identifier:
            if not self.project or not self.institution:
                raise ValidationError("Project and Institution are required to generate identifier.")

            self.identifier = f"{self.institution.code}-{self.project.code}-{self.pk}" # noqa
            super().save(update_fields=["identifier"])
