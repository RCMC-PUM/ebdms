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

    @property
    def to_fhir_reference(self) -> dict:
        """
        Minimal FHIR Reference(Organization) shape.
        """
        return {
            "reference": f"Organization/{self.code}",
            "display": str(self),
        }

    @property
    def fhir_identifier(self) -> dict:
        return {"system": "https://ebmds.pum.edu.pl", "value": self.code}


class PrincipalInvestigator(models.Model):
    name = models.CharField(max_length=512)
    surname = models.CharField(max_length=512)

    email = models.EmailField()
    phone = models.CharField(max_length=22, blank=True, null=True)

    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.name} {self.surname} from ({self.institution})"

    @property
    def to_fhir_reference(self) -> dict:
        """
        Minimal FHIR Reference(Practitioner) shape.
        """
        return {
            "reference": f"Practitioner/{self.pk}",
            "display": f"{self}",
        }


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
    )

    name = models.CharField(max_length=255, unique=True, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        editable=False
    )

    document = models.FileField(
        upload_to=f"documents/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "xlsx", "csv", "html"])]
    )

    class Meta:
        verbose_name = "Project's Document"
        verbose_name_plural = "Project's Documents"


class Participant(models.Model):
    """
    Participant = FHIR Patient.

    Uses JSONField for FHIR complex datatypes:
      - Identifier, HumanName, ContactPoint, Address, CodeableConcept, Attachment,
        Period, Reference, Annotation.

    Field names match your pasted Patient schema.
    """
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        help_text="Local governance linkage.",
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

    address = models.JSONField(
        default=list,
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

    fhir_object = models.JSONField(editable=False, blank=True, null=True)

    class Meta:
        ordering = ["pk", "project"]
        verbose_name = "Participant"
        verbose_name_plural = "Participants"

    def __str__(self) -> str:
        return str(self.pk) # noqa

    # -------------------------
    # Validation for FHIR choice fields
    # -------------------------
    def clean(self):
        # deceased logic validation[x]
        if self.deceased is not None and self.deceased_date_time is not None:
            raise ValidationError("Deceased cannot be False when deceased date time is provided.")

    # -------------------------
    # FHIR export
    # -------------------------
    def to_fhir(self, system: str = "https://ebmds.pum.edu.pl/identifier/participant") -> Dict[str, Any]:
        identifiers: List[Dict[str, Any]] = list(self.pk or [])
        if self.pk and not any(i.get("value") == self.pk for i in identifiers):
            identifiers.insert(0, _fhir_identifier(self.pk, system=system))

        data: Dict[str, Any] = {
            "resourceType": "Patient",
            "identifier": identifiers,
            "active": self.active,
            "name": self.name,
            # "telecom": list(self.telecom if  or []), # TODO fix this form ...
            "gender": self.gender,
            "birthDate": self.birth_date.isoformat() if self.birth_date else None,
            # deceased[x] (emit whichever is set)
            "deceasedBoolean": self.deceased if self.deceased is None else None,
            "deceasedDateTime": self.deceased_date_time.isoformat() if self.deceased_date_time else None,
            "address": list(self.address or []),
            "maritalStatus": self.marital_status,
            # multipleBirth[x] (emit whichever is set)
            # "multipleBirthBoolean": self.multipleBirthBoolean if self.multipleBirthInteger is None else None,
            # "multipleBirthInteger": self.multipleBirthInteger,
            "contact": [self.email if self.email else "", self.phone_number if self.phone_number else ""],
            "communication": self.communication.code if self.communication else "",
            # "generalPractitioner": gps,
            # "managingOrganization": managing_org,
            # "link": list(self.link or []),
        }
        return _strip_empty(data)

    def save(self, *args, **kwargs):
        self.full_clean()
        self.fhir_object = self.to_fhir()

        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add("fhir")
            kwargs["update_fields"] = list(update_fields)

        super().save(*args, **kwargs)
