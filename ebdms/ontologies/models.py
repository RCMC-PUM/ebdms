from django.db import models
from simple_history.models import HistoricalRecords
from django.core.validators import FileExtensionValidator


class BaseTerm(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    history = HistoricalRecords(inherit=True)

    class Meta:
        abstract = True
        ordering = ("name",)

    def __str__(self):
        return self.name


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
