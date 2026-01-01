from django.core.validators import FileExtensionValidator
from django.db import models

from core.models import Model


class BaseTerm(Model):
    """
    Abstract ontology-like base term.

    - system: URI / namespace of the terminology (e.g. HL7, local, WHO, UCUM)
    - code: stable machine-readable code within a system
    - display: preferred human readable label
    """

    system = models.CharField(
        max_length=255,
        help_text="System / namespace (e.g. 'http://terminology.hl7.org/CodeSystem/v3-MaritalStatus').",
    )

    code = models.CharField(
        max_length=64,
        db_index=True,
        help_text="Code — stable machine-readable code (within the system).",
    )

    name = models.CharField(
        max_length=255,
        help_text="Human-readable preferred label.",
        db_index=True,
    )

    description = models.TextField(
        blank=True,
        help_text="Local description / definition of the term.",
    )

    class Meta:
        abstract = True
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(
                fields=("system", "code"), name="uniq_%(class)s_system_code"
            ),
        ]

    def __str__(self) -> str:
        if self.code:
            return f"{self.name} ({self.code})"
        return str(self.name)


class CommunicationLanguage(BaseTerm):
    """Language used for communication (not necessarily ethnicity)."""

    class Meta(BaseTerm.Meta):
        verbose_name = "Communication language"
        verbose_name_plural = "Communication languages"


class MaritalStatus(BaseTerm):
    """FHIR/HL7 v3 MaritalStatus codes."""

    class Meta(BaseTerm.Meta):
        verbose_name = "Marital status"
        verbose_name_plural = "Marital statuses"


class SampleType(BaseTerm):
    """Standardized biological sample type."""

    class Meta(BaseTerm.Meta):
        verbose_name = "Sample type"
        verbose_name_plural = "Sample types"

    def __str__(self) -> str:
        return str(self.name)


class Unit(BaseTerm):
    """Unit of measure (prefer UCUM when possible)."""

    class Meta(BaseTerm.Meta):
        verbose_name = "Unit"
        verbose_name_plural = "Units"


class ICDDiagnosis(BaseTerm):
    """
    ICD diagnosis term stored locally.
    NOTE: populating full ICD lists is subject to licensing / API terms.
    """

    class ICDVersion(models.TextChoices):
        ICD11 = "icd11", "ICD-11"

    version = models.CharField(
        max_length=8,
        choices=ICDVersion.choices,
        help_text="Which ICD revision this code belongs to.",
    )

    class Meta:
        verbose_name = "ICD diagnosis"
        verbose_name_plural = "ICD diagnoses"
        constraints = [
            models.UniqueConstraint(
                fields=("version", "system", "code"),
                name="uniq_icd_version_system_code",
            ),
        ]


class SOPTermMixin(models.Model):
    sop = models.FileField(
        upload_to="sops/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
        help_text="Optional PDF SOP attached to this term.",
    )

    class Meta:
        abstract = True


class CollectionMethod(SOPTermMixin, BaseTerm):
    class Meta(BaseTerm.Meta):
        verbose_name = "Collection method"
        verbose_name_plural = "Collection methods"


class RelationType(BaseTerm):
    """
    Relation type (family / legal / partner etc.)
    Seeded from a fixed list.
    """

    class Meta(BaseTerm.Meta):
        verbose_name = "Relation type"
        verbose_name_plural = "Relation types"
