import os.path

from django.db.models import Q, F
from django.utils import timezone
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator

from core.models import Model
from ontologies.models import (
    MaritalStatus,
    CommunicationLanguage,
    ICDDiagnosis,
    RelationType,
)


class Institution(Model):
    name = models.CharField(
        max_length=1024,
        help_text="Official name of the institution (e.g. university, hospital, research center).",
    )

    department = models.CharField(
        max_length=1024,
        null=True,
        blank=True,
        help_text="Optional department, faculty, or unit within the institution.",
    )

    address = models.CharField(
        max_length=1024,
        unique=True,
        blank=True,
        null=True,
        help_text="Official postal address of the institution (must be unique if provided).",
    )

    code = models.CharField(
        max_length=12,
        unique=True,
        help_text="Short unique institutional code used internally or in integrations.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "department"],
                name="unique_institution_name_department",
            )
        ]
        verbose_name = "Institution"
        verbose_name_plural = "Institutions"

    def __str__(self):
        return f"{self.department} ({self.name})" if self.department else self.name


class PrincipalInvestigator(Model):
    name = models.CharField(
        max_length=512,
        help_text="First name of the principal investigator.",
    )

    surname = models.CharField(
        max_length=512,
        help_text="Last name of the principal investigator.",
    )

    email = models.EmailField(
        help_text="Primary contact email address of the principal investigator.",
    )

    phone = models.CharField(
        max_length=22,
        blank=True,
        null=True,
        help_text="Optional contact phone number (international format recommended).",
    )

    institution = models.ForeignKey(
        Institution,
        on_delete=models.PROTECT,
        help_text="Institution the principal investigator is affiliated with.",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "surname"],
                name="unique_PI",
            )
        ]
        verbose_name = "Principal Investigator"
        verbose_name_plural = "Principal Investigators"

    def __str__(self):
        return f"{self.name} {self.surname} ({self.institution})"


class Project(Model):
    name = models.CharField(max_length=512, unique=True, help_text="Project name.")

    code = models.CharField(max_length=8, unique=True, help_text="Project code.")

    description = models.TextField(
        max_length=2048, blank=True, default="", help_text="Project description."
    )

    principal_investigator = models.ForeignKey(
        PrincipalInvestigator,
        on_delete=models.PROTECT,
        help_text="Project principal investigator (PI).",
    )

    status = models.BooleanField(
        default=True, help_text="Project status (active / inactive)."
    )

    start_date = models.DateField(help_text="Project start date.")

    end_date = models.DateField(blank=True, null=True, help_text="Project end date.")

    class Meta:
        ordering = ["start_date"]

    def clean(self):
        if not self.status and not self.end_date:
            raise ValidationError(
                {"status": "If project is inactive please provide end date."}
            )

    @property
    def is_active(self):
        if not self.status:
            return False
        if self.end_date is None:
            return True
        return self.end_date > timezone.now()

    @property
    def n_participants(self) -> int:
        return self.participants.count()

    def __str__(self):
        return self.name


def project_document_path(instance, filename):
    return os.path.join("projects", str(instance.project.code), "documents", filename)


def project_consent_path(instance, filename):
    return os.path.join("projects", str(instance.project.code), "consents", filename)


class ProjectDocuments(Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="documents",
        help_text="Select the project this document belongs to.",
    )

    name = models.CharField(
        max_length=255, unique=True, help_text="Provide document (unique) name."
    )

    description = models.TextField(
        null=True, blank=True, help_text="Provide document description."
    )

    document = models.FileField(
        upload_to=project_document_path,
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "xlsx", "csv"])],
        help_text="Upload file (PDF, XLSX, CSV).",
    )

    class Meta:
        verbose_name = "Project's Document"
        verbose_name_plural = "Project's Documents"

    def __str__(self):
        return self.name


class Participant(Model):
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
        blank=True,  # generated later
        help_text="System-generated participant identifier (read-only).",
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="participants",
        help_text="Project this participant belongs to.",
    )

    institution = models.ForeignKey(
        Institution,
        on_delete=models.CASCADE,
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

    gender = models.CharField(
        max_length=7,
        choices=Gender.choices,
        help_text="Gender — male | female.",
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
    icd = models.ManyToManyField(
        ICDDiagnosis,
        blank=True,
        verbose_name="ICD11",
        help_text="ICD11 classifications for this participant (optional).",
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

    # ------------------------------------------------------------------
    # Consent
    # ------------------------------------------------------------------

    class ConsentStatus(models.TextChoices):
        GIVEN = "given", "Given"
        WITHDRAWN = "withdrawn", "Withdrawn"
        PENDING = "pending", "Pending"
        EXPIRED = "expired", "Expired"

    consent_status = models.CharField(
        max_length=16,
        choices=ConsentStatus.choices,
        default=ConsentStatus.PENDING,
        help_text="Current legal consent status.",
    )

    consent_file = models.FileField(
        upload_to=project_consent_path,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
        help_text="Signed consent document (PDF).",
    )

    consent_signed_at = models.DateField(
        blank=True, null=True, help_text="Timestamp when consent was signed."
    )

    class Meta:
        ordering = ["pk", "project"]
        verbose_name = "Participant"
        verbose_name_plural = "Participants"

    def __str__(self) -> str:
        return f"{self.name} {self.surname} ({self.identifier or 'no-id'})"

    @property
    def is_healthy(self) -> bool:
        """
        Derived: healthy if no ICD diagnoses linked.
        """
        return not self.icd.exists()  # noqa

    @property
    def has_relations(self):
        """
        All ParticipantRelation rows where this participant is either side (bidirectional).
        """
        if self.pk:
            return ParticipantRelation.objects.filter(
                Q(from_participant=self) | Q(to_participant=self)
            )

    @property
    def related_monozygotic_twin(self):
        """
        This is a special property implemented for model validation only.
        """
        relations = self.has_relations

        try:
            mt = RelationType.objects.get(code="twin_monozygotic")
        except RelationType.DoesNotExist:
            raise Exception(
                f"RelationType model expects to have an instance with code='twin_monozygotic'!"
            )

        if relations:
            return relations.filter(relation_type=mt)

    def clean(self):
        """
        Cross-field validation.
        """
        super().clean()  # Run clean()
        # Add custom cross-field validation.
        # If a death date is provided, deceased must be True
        if self.deceased_date_time and not self.deceased:
            raise ValidationError(
                {"deceased": "Cannot be False when deceased date/time is provided."}
            )

        if self.deceased and not self.deceased_date_time:
            raise ValidationError(
                {
                    "deceased_date_time": "Provide deceased date/time when deceased is True."
                }
            )

        if not self.birth_date:
            return

        if self.birth_date and self.birth_date > timezone.localdate():
            raise ValidationError({"birth_date": "Birth date cannot be in the future."})

    def save(self, *args, **kwargs):
        """
        Save participant and generate identifier exactly once.

        - Validate model before saving --> self.full_clean().
        - Generate identifier only after first save --> needs PK.
        """
        self.full_clean()

        is_new = self.pk is None
        needs_identifier = is_new and not self.identifier

        if needs_identifier:
            # Don't create a row if we can't generate the identifier
            if not self.project_id or not self.institution_id:
                raise ValidationError(
                    "Project and Institution are required to generate identifier."
                )

        with transaction.atomic():
            super().save(*args, **kwargs)

            if needs_identifier:
                self.identifier = (
                    f"{self.institution.code}-{self.project.code}-{self.pk}"
                )
                super().save(update_fields=["identifier"])


class ParticipantRelation(Model):
    """
    Typed relation between two Participants.

    Direction matters:
    - parent -> child
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
        ]
        verbose_name = "Participant relation"
        verbose_name_plural = "Participant relations"

    def clean(self):
        """
        Cross-field validation.
        """
        super().clean()  # Run clean()
        if not self.relation_type:
            return

        if self.relation_type == RelationType.objects.get(code="twin_monozygotic"):
            if self.from_participant.birth_date and self.to_participant.birth_date:  # noqa
                if self.from_participant.birth_date != self.to_participant.birth_date:  # noqa
                    raise ValidationError(
                        {
                            "relation_type": "Monozygotic twins can not differ in terms of birth date!"
                        }
                    )

            if self.from_participant.gender and self.to_participant.gender:  # noqa
                if self.from_participant.gender != self.to_participant.gender:  # noqa
                    raise ValidationError(
                        {
                            "gender": "Monozygotic twins can not differ in terms of gender!"
                        }
                    )

    def __str__(self):
        return f"{self.from_participant} → {self.relation_type} → {self.to_participant}"
