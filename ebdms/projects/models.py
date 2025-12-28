from typing import Any, Dict

from django.db.models import Q, F
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from ontologies.models import MaritalStatus, CommunicationLanguage, ICDDiagnosis, RelationType


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
    principal_investigator = models.ForeignKey(PrincipalInvestigator, on_delete=models.PROTECT,
                                               help_text="Project principal investigator (PI).")
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
    Participant = FHIR Patient (simplified).

    Notes:
    - `identifier` is generated once after the first save (needs PK).
    - Address is stored as simple flat fields (street/city/etc.).
    - ICD is M2M (can be empty).
    """

    # ---------------------------------------------------------------------
    # Core identity / ownership
    # ---------------------------------------------------------------------
    identifier = models.CharField(
        max_length=128,
        unique=True,
        editable=False,
        blank=True,   # generated later
        help_text="System-generated participant identifier (read-only).",
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        help_text="Project this participant belongs to.",
    )

    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
        null=True,  # TODO: change to null=False when you enforce it
        blank=True,
        help_text="Institution this participant is associated with (required to generate identifier).",
    )

    active = models.BooleanField(
        default=True,
        help_text="FHIR Patient.active — whether this participant record is in active use.",
    )

    # ---------------------------------------------------------------------
    # Demographics
    # ---------------------------------------------------------------------
    name = models.CharField(
        max_length=255,
        help_text="Given name.",
    )

    surname = models.CharField(
        max_length=255,
        help_text="Family name / surname.",
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
        help_text="FHIR Patient.gender — male | female | other | unknown.",
    )

    birth_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of birth (optional).",
    )

    # ---------------------------------------------------------------------
    # Contact
    # ---------------------------------------------------------------------
    email = models.EmailField(
        null=True,
        blank=True,
        help_text="Email address (optional).",
    )

    phone_number_prefix = models.CharField(
        max_length=8,
        null=True,
        blank=True,
        help_text="Phone prefix (optional). Example: +48",
    )

    phone_number = models.IntegerField(
        null=True,
        blank=True,
        help_text="Phone number (optional). Example: 123456789",
    )

    # ---------------------------------------------------------------------
    # Address (flat)
    # ---------------------------------------------------------------------
    street = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Street name (optional).",
    )
    street_number = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        help_text="Building number (optional).",
    )
    apartment = models.CharField(
        max_length=32,
        null=True,
        blank=True,
        help_text="Apartment/unit (optional).",
    )

    city = models.CharField(
        max_length=128,
        null=True,
        blank=True,
        help_text="City (optional).",
    )
    postal_code = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="Postal/ZIP code (optional).",
    )
    country = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        help_text="Country (optional). Example: Poland",
    )

    # ---------------------------------------------------------------------
    # Social / status
    # ---------------------------------------------------------------------
    marital_status = models.ForeignKey(
        MaritalStatus,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Marital status (optional).",
    )

    deceased = models.BooleanField(
        default=False,
        help_text="FHIR Patient.deceasedBoolean — whether the participant is deceased.",
    )

    deceased_date_time = models.DateField(
        null=True,
        blank=True,
        help_text="Deceased date — when the participant died (optional).",
    )

    communication = models.ForeignKey(
        CommunicationLanguage,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Preferred communication language (optional).",
    )

    # ---------------------------------------------------------------------
    # Clinical classification
    # ---------------------------------------------------------------------
    healthy = models.BooleanField(
        default=True,
        help_text="Indicator if patients is/was healthy at the time of recruitment."
    )
    icd = models.ManyToManyField(
        ICDDiagnosis,
        blank=True,
        help_text="ICD classifications for this participant (optional).",
    )

    # ---------------------------------------------------------------------
    # Relations
    # ---------------------------------------------------------------------
    relations = models.ManyToManyField(
        "self",
        through="ParticipantRelation",
        symmetrical=False,
        related_name="related_to",
        blank=True,
        help_text="Biological, legal or social relations to other participants.",
    )

    class Meta:
        ordering = ["pk", "project"]
        verbose_name = "Participant"
        verbose_name_plural = "Participants"

    def __str__(self) -> str:
        return f"{self.name} {self.surname} ({self.identifier or 'no-id'})"

    def clean(self):
        """
        Cross-field validation.
        """
        super().clean()

        # If a death date is provided, deceased must be True
        if self.deceased_date_time and not self.deceased:
            raise ValidationError(
                {"deceased": "Cannot be False when deceased date/time is provided."}
            )

        if self.deceased and not self.deceased_date_time:
            raise ValidationError({"deceased_date_time": "Provide deceased date/time when deceased is True."})

        if not self.healthy and not self.icd:
            raise ValidationError({"healthy": "If participant is not healthy please provide an appropriate ICD11 code."})

    def save(self, *args, **kwargs):
        """
        Save participant and generate identifier exactly once.

        - We validate BEFORE saving.
        - We generate identifier only after first save (needs PK).
        """
        self.full_clean()

        is_new = self.pk is None
        needs_identifier = is_new and not self.identifier

        if needs_identifier:
            # Don't create a row if we can't generate the identifier
            if not self.project_id or not self.institution_id:
                raise ValidationError("Project and Institution are required to generate identifier.")

        with transaction.atomic():
            super().save(*args, **kwargs)

            if needs_identifier:
                self.identifier = f"{self.institution.code}-{self.project.code}-{self.pk}"
                super().save(update_fields=["identifier"])


class ParticipantRelation(models.Model):
    """
    Typed relation between two Participants.

    Direction matters:
    - parent -> child
    - sibling -> sibling (must be stored twice if bidirectional)
    """

    # ------------------------------------------------------------------
    # Fields
    # ------------------------------------------------------------------
    from_participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="relations_from",
        help_text="Source participant (relation direction start).",
    )

    to_participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name="relations_to",
        help_text="Target participant (relation direction end).",
    )

    relation_type = models.ForeignKey(
        RelationType,
        on_delete=models.PROTECT,
        help_text="Type of biological / legal relationship.",
    )

    note = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Optional free-text note (e.g. uncertain, reported by patient).",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    # ------------------------------------------------------------------
    # DB-level constraints
    # ------------------------------------------------------------------
    class Meta:
        # Prevent self-to-self relation
        constraints = [
            models.CheckConstraint(
                condition=~Q(from_participant=F("to_participant")),
                name="no_self_relation",
            ),
            models.UniqueConstraint(
                fields=["from_participant", "to_participant", "relation_type"],
                name="unique_relation_per_type",
            ),
        ]
        verbose_name = "Participant relation"
        verbose_name_plural = "Participant relations"

    # ------------------------------------------------------------------
    # Validation logic
    # ------------------------------------------------------------------
    def clean(self):
        super().clean()

        if self.from_participant_id == self.to_participant_id:
            raise ValidationError("Participant cannot have a relation to themselves.")

        # Twin-specific biological sanity checks
        if self.relation_type in {
            self.RelationType.TWIN_MONOZYGOTIC,
            self.RelationType.TWIN_DIZYGOTIC,
        }:
            if (
                self.from_participant.birth_date
                and self.to_participant.birth_date
                and self.from_participant.birth_date != self.to_participant.birth_date
            ):
                raise ValidationError(
                    "Twins must have the same birth date."
                )

    def __str__(self):
        return (
            f"{self.from_participant} → "
            f"{self.relation_type} → "
            f"{self.to_participant}"
        )


