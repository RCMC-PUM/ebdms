from typing import Any, Dict, List, Optional

from django.core.exceptions import ValidationError
from django.db import models

from ontologies.models import SampleType


# -----------------------------
# Tiny helpers (minimal FHIR shapes)
# -----------------------------
def _strip_empty(d: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in d.items() if v not in (None, [], {}, "")}


def _fhir_identifier(value: str, system: Optional[str] = "https://ebmds.pum.edu.pl") -> Dict[str, Any]:
    """
    Minimal FHIR Identifier:
      {"system": "<uri>", "value": "<string>"}
    """
    out: Dict[str, Any] = {"value": value}
    if system:
        out["system"] = system
    return out


# =============================================================================
# Specimen (FHIR: Specimen)
# =============================================================================

class Specimen(models.Model):
    """
    FHIR resource: Specimen

    This model holds the top-level Specimen fields.
    Nested components are modeled as separate tables:
      - Feature (feature[*])
      - Collection (collection)
      - Processing (processing[*])
      - Container (container[*])
    """

    # local id (also exported as identifier.value)
    identifier = models.CharField(
        max_length=50,
        unique=True,
        editable=False,
        help_text="Specimen identifier.",
    )

    external_identifiers = models.JSONField(
        null=True,
        blank=True,
        unique=True,
        help_text="External specimen identifier(s) (Optional). E.g [{'source_a': 'id_a'}, {'source_b': 'id_b'}]",
    )

    class Status(models.TextChoices):
        AVAILABLE = "available", "available"
        UNAVAILABLE = "unavailable", "unavailable"
        UNSATISFACTORY = "unsatisfactory", "unsatisfactory"
        ENTERED_IN_ERROR = "entered-in-error", "entered-in-error"

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
        help_text="FHIR Specimen.status — available | unavailable | unsatisfactory | entered-in-error.",
    )

    type = models.ForeignKey(
        SampleType,
        on_delete=models.PROTECT,
        help_text="Specimen Type."
    )

    subject = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.subject (Reference). Typically a Patient reference.",
    )

    receivedTime = models.DateTimeField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.receivedTime — time received by testing lab.",
    )

    parent = models.ManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="derived",
        help_text="FHIR Specimen.parent[*] — references to parent Specimen resources.",
    )

    request = models.JSONField(
        default=list,
        blank=True,
        help_text="FHIR Specimen.request[*] — Reference(ServiceRequest) list.",
    )

    class Combined(models.TextChoices):
        GROUPED = "grouped", "grouped"
        POOLED = "pooled", "pooled"

    combined = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        choices=Combined.choices,
        help_text="FHIR Specimen.combined — grouped | pooled.",
    )

    role = models.JSONField(
        default=list,
        blank=True,
        help_text="FHIR Specimen.role[*] — CodeableConcept list.",
    )

    condition = models.JSONField(
        default=list,
        blank=True,
        help_text="FHIR Specimen.condition[*] — CodeableConcept list.",
    )

    note = models.JSONField(
        default=list,
        blank=True,
        help_text="FHIR Specimen.note[*] — Annotation list.",
    )

    history = HistoricalRecords()

    class Meta:
        ordering = ["specimen_id"]
        verbose_name = "Specimen"
        verbose_name_plural = "Specimens"

    def __str__(self) -> str:
        return self.specimen_id

    # -----------------------------
    # Assembly to FHIR JSON
    # -----------------------------
    def to_fhir(self, system: str = "urn:PUM-RCMC-EBDMS:specimen") -> Dict[str, Any]:
        """
        Produce a FHIR-shaped Specimen dict matching the schema you pasted.
        """
        identifiers: List[Dict[str, Any]] = list(self.identifier or [])
        if self.specimen_id and not any(i.get("value") == self.specimen_id for i in identifiers):
            identifiers.insert(0, _fhir_identifier(self.specimen_id, system=system))

        # parent references
        parents = [{"reference": f"Specimen/{p.specimen_id}", "display": str(p)} for p in self.parent.all()]

        data: Dict[str, Any] = {
            "resourceType": "Specimen",
            "identifier": identifiers,
            "accessionIdentifier": self.accessionIdentifier,
            "status": self.status,
            "type": self.type,
            "subject": self.subject,
            "receivedTime": self.receivedTime.isoformat() if self.receivedTime else None,
            "parent": parents,
            "request": list(self.request or []),
            "combined": self.combined,
            "role": list(self.role or []),
            "feature": [f.to_fhir() for f in self.features.all()],
            "collection": self.collection.to_fhir() if hasattr(self, "collection") and self.collection else None,
            "processing": [p.to_fhir() for p in self.processings.all()],
            "container": [c.to_fhir() for c in self.containers.all()],
            "condition": list(self.condition or []),
            "note": list(self.note or []),
        }
        return _strip_empty(data)


# =============================================================================
# Feature (FHIR: Specimen.feature[*])
# =============================================================================

class Feature(models.Model):
    """
    FHIR backbone element: Specimen.feature[*]

    FHIR:
      feature[*].type: CodeableConcept (required in FHIR excerpt)
      feature[*].description: string (required in FHIR excerpt)
    """

    specimen = models.ForeignKey(
        Specimen,
        on_delete=models.CASCADE,
        related_name="features",
        help_text="Owning Specimen (FHIR Specimen.feature belongs to Specimen).",
    )

    type = models.JSONField(
        null=False,
        blank=False,
        help_text="FHIR Specimen.feature.type (CodeableConcept).",
    )
    description = models.CharField(
        max_length=2048,
        help_text="FHIR Specimen.feature.description (string).",
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "Specimen feature"
        verbose_name_plural = "Specimen features"

    def __str__(self) -> str:
        return f"Feature({self.specimen.specimen_id})"

    def to_fhir(self) -> Dict[str, Any]:
        return _strip_empty(
            {
                "type": self.type,
                "description": self.description,
            }
        )


# =============================================================================
# Collection (FHIR: Specimen.collection)
# =============================================================================

class Collection(models.Model):
    """
    FHIR backbone element: Specimen.collection

    Implements choice fields:
      - collected[x] -> collectedDateTime OR collectedPeriod
      - fastingStatus[x] -> fastingStatusCodeableConcept OR fastingStatusDuration
    """

    specimen = models.OneToOneField(
        Specimen,
        on_delete=models.CASCADE,
        related_name="collection",
        help_text="Owning Specimen (FHIR Specimen.collection).",
    )

    collector = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.collection.collector (Reference).",
    )

    # collected[x] choice
    collectedDateTime = models.DateTimeField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.collection.collectedDateTime.",
    )
    collectedPeriod = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.collection.collectedPeriod (Period).",
    )

    duration = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.collection.duration (Duration).",
    )

    quantity = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.collection.quantity (Quantity(SimpleQuantity)).",
    )

    method = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.collection.method (CodeableConcept).",
    )

    device = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.collection.device (CodeableReference(Device)).",
    )

    procedure = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.collection.procedure (Reference(Procedure)).",
    )

    bodySite = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.collection.bodySite (CodeableReference(BodyStructure)).",
    )

    # fastingStatus[x] choice
    fastingStatusCodeableConcept = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.collection.fastingStatusCodeableConcept (CodeableConcept).",
    )
    fastingStatusDuration = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.collection.fastingStatusDuration (Duration).",
    )

    class Meta:
        verbose_name = "Specimen collection"
        verbose_name_plural = "Specimen collections"

    def clean(self):
        # collected[x] mutual exclusivity
        if self.collectedDateTime and self.collectedPeriod:
            raise ValidationError("FHIR collected[x]: set either collectedDateTime OR collectedPeriod, not both.")

        # fastingStatus[x] mutual exclusivity
        if self.fastingStatusCodeableConcept and self.fastingStatusDuration:
            raise ValidationError("FHIR fastingStatus[x]: set either fastingStatusCodeableConcept OR fastingStatusDuration, not both.")

    def to_fhir(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "collector": self.collector,
            # collected[x]
            "collectedDateTime": self.collectedDateTime.isoformat() if self.collectedDateTime else None,
            "collectedPeriod": self.collectedPeriod if (not self.collectedDateTime) else None,
            "duration": self.duration,
            "quantity": self.quantity,
            "method": self.method,
            "device": self.device,
            "procedure": self.procedure,
            "bodySite": self.bodySite,
            # fastingStatus[x]
            "fastingStatusCodeableConcept": self.fastingStatusCodeableConcept,
            "fastingStatusDuration": self.fastingStatusDuration if (not self.fastingStatusCodeableConcept) else None,
        }
        return _strip_empty(data)


# =============================================================================
# Processing (FHIR: Specimen.processing[*])
# =============================================================================

class Processing(models.Model):
    """
    FHIR backbone element: Specimen.processing[*]

    Implements choice field:
      - time[x] -> timeDateTime OR timePeriod
    """

    specimen = models.ForeignKey(
        Specimen,
        on_delete=models.CASCADE,
        related_name="processings",
        help_text="Owning Specimen (FHIR Specimen.processing belongs to Specimen).",
    )

    description = models.CharField(
        max_length=2048,
        blank=True,
        help_text="FHIR Specimen.processing.description (string).",
    )

    method = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.processing.method (CodeableConcept).",
    )

    additive = models.JSONField(
        default=list,
        blank=True,
        help_text="FHIR Specimen.processing.additive[*] (Reference(Substance)) list.",
    )

    # time[x] choice
    timeDateTime = models.DateTimeField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.processing.timeDateTime.",
    )
    timePeriod = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.processing.timePeriod (Period).",
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "Specimen processing"
        verbose_name_plural = "Specimen processing steps"

    def clean(self):
        if self.timeDateTime and self.timePeriod:
            raise ValidationError("FHIR processing.time[x]: set either timeDateTime OR timePeriod, not both.")

    def to_fhir(self) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "description": self.description or None,
            "method": self.method,
            "additive": list(self.additive or []),
            "timeDateTime": self.timeDateTime.isoformat() if self.timeDateTime else None,
            "timePeriod": self.timePeriod if (not self.timeDateTime) else None,
        }
        return _strip_empty(data)


# =============================================================================
# Container (FHIR: Specimen.container[*])
# =============================================================================

class Container(models.Model):
    """
    FHIR backbone element: Specimen.container[*]

    FHIR:
      - device (required in excerpt): Reference(Device)
      - location: Reference(Location)
      - specimenQuantity: Quantity(SimpleQuantity)
    """

    specimen = models.ForeignKey(
        Specimen,
        on_delete=models.CASCADE,
        related_name="containers",
        help_text="Owning Specimen (FHIR Specimen.container belongs to Specimen).",
    )

    device = models.JSONField(
        null=False,
        blank=False,
        help_text="FHIR Specimen.container.device (Reference(Device)). Required.",
    )

    location = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.container.location (Reference(Location)).",
    )

    specimenQuantity = models.JSONField(
        null=True,
        blank=True,
        help_text="FHIR Specimen.container.specimenQuantity (Quantity(SimpleQuantity)).",
    )

    class Meta:
        ordering = ["id"]
        verbose_name = "Specimen container"
        verbose_name_plural = "Specimen containers"

    def __str__(self) -> str:
        return f"Container({self.specimen.specimen_id})"

    def to_fhir(self) -> Dict[str, Any]:
        return _strip_empty(
            {
                "device": self.device,
                "location": self.location,
                "specimenQuantity": self.specimenQuantity,
            }
        )
