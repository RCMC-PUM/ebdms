from django.core.validators import FileExtensionValidator
from django.db import models


class BaseTerm(models.Model):
    """
    Abstract ontology base for FHIR CodeableConcept.

    Maps to FHIR CodeableConcept:
      - coding[0].system  -> system
      - coding[0].code    -> code
      - coding[0].display -> display
      - text              -> text
    """

    # FHIR: Coding.system (URI namespace)
    system = models.CharField(
        max_length=255,
        help_text="FHIR Coding.system — URI identifying the terminology system "
                  "(e.g. SNOMED, LOINC, or internal namespace).",
    )

    # FHIR: Coding.code (machine-stable identifier)
    code = models.CharField(
        max_length=64,
        help_text="FHIR Coding.code — stable machine-readable code.",
    )

    # FHIR: Coding.display (human label)
    display = models.CharField(
        max_length=255,
        help_text="FHIR Coding.display — human-readable term.",
    )

    # FHIR: CodeableConcept.text (free text)
    text = models.CharField(
        max_length=255,
        blank=True,
        help_text="FHIR CodeableConcept.text — free text representation.",
    )

    description = models.TextField(
        blank=True,
        help_text="Local description / definition of the term.",
    )

    class Meta:
        abstract = True
        ordering = ("display",)
        unique_together = ("system", "code")

    def __str__(self) -> str:
        return self.display

    @property
    def to_codeable_concept(self) -> dict:
        """
        Export as a FHIR CodeableConcept.
        """
        return {
            "coding": [
                {
                    "system": self.system,
                    "code": self.code,
                    "display": self.display,
                }
            ],
            "text": self.text or self.display,
        }


class CommunicationLanguage(BaseTerm):
    """
    FHIR Patient.communication.language

    Represents a language used to communicate with the patient.

    Bound to (recommended):
      - IETF BCP 47 language tags
      - or ISO 639-1 / ISO 639-3 via HL7 CodeSystem

    Example:
      system = urn:ietf:bcp:47
      code   = en
      display = English
    """

    class Meta:
        verbose_name = "Communication language"
        verbose_name_plural = "Communication languages"


class MaritalStatus(BaseTerm):
    """
    FHIR Patient.maritalStatus

    Bound to HL7 v3 MaritalStatus:
      system = http://terminology.hl7.org/CodeSystem/v3-MaritalStatus

    Examples:
      code = M, display = Married
      code = S, display = Never Married
    """

    class Meta:
        verbose_name = "Marital status"
        verbose_name_plural = "Marital statuses"


class SampleType(BaseTerm):
    pass


class Unit(BaseTerm):
    pass


class Diagnosis(BaseTerm):
    pass


class CollectionMethod(BaseTerm):
    sop = models.FileField(
        upload_to=f"sops/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])]
    )


class SamplePreparation(BaseTerm):
    sop = models.FileField(
        upload_to=f"sops/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])]
    )


class SampleStorage(BaseTerm):
    sop = models.FileField(
        upload_to=f"sops/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])]
    )
