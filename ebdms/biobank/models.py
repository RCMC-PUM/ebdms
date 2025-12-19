import qrcode
import base64
from io import BytesIO

from django.db import models
from django.utils.html import mark_safe
from django.core.validators import FileExtensionValidator

from simple_history.models import HistoricalRecords

from projects.models import Project, PrincipalInvestigator, Institution  # noqa
from ontologies.models import SampleType, CollectionMethod, SampleStorage, SamplePreparation, Unit, Diagnosis


class Donor(models.Model):
    class ConsentStatus(models.TextChoices):
        SIGNED = "SIGNED", "Signed"
        UNSIGNED = "UNSIGNED", "Unsigned"
        UNKNOWN = "UNKNOWN", "Unknown"

    class Sex(models.TextChoices):
        MALE = "MALE", "Male"
        FEMALE = "FEMALE", "Female"
        UNKNOWN = "UNKNOWN", "Unknown"

    donor_id = models.CharField(max_length=20, unique=True, editable=False)
    name = models.CharField(blank=True, null=True)
    surname = models.CharField(blank=True, null=True)

    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)

    sex = models.CharField(
        max_length=7,
        choices=Sex.choices,
        default=Sex.UNKNOWN,
    )
    date_of_birth = models.DateField(null=True, blank=True)
    diagnosis = models.ForeignKey(Diagnosis, on_delete=models.PROTECT, null=True, blank=True)

    consent_status = models.CharField(
        max_length=8,
        choices=ConsentStatus.choices,
        default=ConsentStatus.UNKNOWN,
    )

    notes = models.TextField(blank=True, null=True)
    consent_document = models.FileField(
        upload_to=f"consent_forms/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])]
    )

    history = HistoricalRecords()

    class Meta:
        ordering = ["donor_id", "project"]
        verbose_name = "Donor"
        verbose_name_plural = "Donors"

    def save(self, *args, **kwargs):
        if not self.donor_id:
            self.donor_id = f"{self.pk}"  # noqa
        super().save(*args, **kwargs)

    def __str__(self):
        return self.donor_id


class Storage(models.Model):
    device_id = models.CharField(max_length=50, unique=True)
    location = models.CharField(max_length=1024)

    temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    notes = models.TextField(blank=True, null=True)
    sensors = models.JSONField(null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Storage"
        verbose_name_plural = "Storage"

    def __str__(self):
        return f"Storage {self.device_id} ({self.location})"


class Sample(models.Model):
    sample_id = models.CharField(max_length=50, unique=True, editable=False)
    donor = models.ForeignKey(Donor, on_delete=models.PROTECT, null=True, blank=True)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)

    sample_type = models.ForeignKey(
        SampleType,
        on_delete=models.PROTECT,
        null=True, blank=True
    )

    collection_method = models.ForeignKey(
        CollectionMethod,
        on_delete=models.PROTECT,
        blank=True,
        null=True
    )

    volume_or_mass = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    volume_or_mass_units = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        blank=True,
        null=True
    )
    storage_storage_condition = models.ForeignKey(
        SampleStorage,
        on_delete=models.PROTECT,
        blank=True,
        null=True
    )

    collection_date = models.DateTimeField()
    notes = models.TextField(blank=True, null=True)

    n_aliquots = models.IntegerField(default=5)
    history = HistoricalRecords()

    def save(self, *args, **kwargs):
        creating = self.pk is None
        super().save(*args, **kwargs)  # first save to get pk

        # set sample_id after pk exists
        if not self.sample_id:
            self.sample_id = f"{self.project.code}_{self.pk}"
            super().save(update_fields=["sample_id"])  # avoid rewriting everything

    class Meta:
        ordering = ["collection_date"]
        verbose_name = "Sample"
        verbose_name_plural = "Samples"

    def qr_code(self):
        if self.sample_id:
            qr = qrcode.make(self.sample_id)
            buf = BytesIO()
            qr.save(buf, format="PNG")
            image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")

            return mark_safe(f'<img src="data:image/png;base64,{image_b64}" width="100" height="100" />')
        return "-"

    qr_code.short_description = "2D QR Code"

    def __str__(self):
        return self.sample_id


class Aliquot(models.Model):
    aliquot_id = models.CharField(max_length=50, unique=True, editable=False)
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE, related_name="aliquots")

    volume_or_mass = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    volume_or_mass_units = models.ForeignKey(
        Unit,
        on_delete=models.PROTECT,
        blank=True,
        null=True
    )

    preparation_method = models.ForeignKey(
        SamplePreparation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    prepared_date = models.DateField()
    storage = models.ForeignKey(Storage, null=True, blank=True, on_delete=models.PROTECT)

    notes = models.TextField(blank=True, null=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["aliquot_id"]
        verbose_name = "Aliquot"
        verbose_name_plural = "Aliquots"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # first save to get pk

        if not self.aliquot_id:
            self.aliquot_id = f"{self.sample.sample_id}.{self.pk}"
            super().save(update_fields=["aliquot_id"])

    def qr_code(self):
        qr = qrcode.make(self.aliquot_id)
        buf = BytesIO()
        qr.save(buf, format="PNG")
        image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return mark_safe(f'<img src="data:image/png;base64,{image_b64}" width="100" height="100" />')

    qr_code.short_description = "2D QR Code"

    def __str__(self):
        return self.aliquot_id
