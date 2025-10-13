import qrcode
import base64
from io import BytesIO
from django.db import models
from django.utils.html import mark_safe
from django.core.validators import FileExtensionValidator


class Project(models.Model):
    project_id = models.CharField(max_length=50, unique=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.project_id} - {self.title}"


class Term(models.Model):
    CATEGORY_CHOICES = [
        ("sex", "Sex"),
        ("diagnosis", "Diagnosis"),
        ("consent_status", "Consent Status"),
        ("sample_type", "Sample Type"),
        ("collection_method", "Collection Method"),
        ("storage_condition", "Storage Condition"),
        ("preparation_method", "Preparation Method"),
        ("storage_type", "Storage Type"),
        ("units", "Units"),
        ("device", "Device"),
    ]

    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ("category", "name")

    def __str__(self):
        return f"{self.name}"


class Patient(models.Model):
    patient_id = models.CharField(max_length=20, unique=True, editable=False)
    project = models.ForeignKey(Project, on_delete=models.PROTECT, null=True, blank=True)

    sex = models.ForeignKey(
        Term,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"category": "sex"},
        related_name="patients_sex",
    )
    date_of_birth = models.DateField(null=True, blank=True)

    diagnosis = models.ForeignKey(
        Term,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"category": "diagnosis"},
        related_name="patients_diagnosis",
    )
    consent_status = models.ForeignKey(
        Term,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"category": "consent_status"},
        related_name="patients_consent",
    )
    notes = models.TextField(blank=True, null=True)
    consent_document = models.FileField(
        upload_to="consent_forms/",
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
    )

    def save(self, *args, **kwargs):
        if not self.patient_id:
            last = Patient.objects.order_by("-id").first()
            num = int(last.patient_id[3:]) if last else 0
            self.patient_id = f"PAT{num+1:04d}"
        super().save(*args, **kwargs)

    def qr_code(self):
        qr = qrcode.make(self.patient_id)
        buf = BytesIO()
        qr.save(buf, format="PNG")
        image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return mark_safe(f'<img src="data:image/png;base64,{image_b64}" width="100" height="100" />')

    qr_code.short_description = "2D QR Code"

    def __str__(self):
        return self.patient_id


class Sample(models.Model):
    sample_id = models.CharField(max_length=50, unique=True, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.PROTECT, null=True, blank=True)

    sample_type = models.ForeignKey(
        Term,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"category": "sample_type"},
        related_name="samples_type",
    )

    collection_date = models.DateTimeField()
    collection_method = models.ForeignKey(
        Term,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"category": "collection_method"},
        related_name="samples_collection_method",
    )

    volume_or_mass = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    volume_or_mass_units = models.ForeignKey(
        Term,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"category": "units"},
        related_name="samples_volume_units",
    )
    storage_condition = models.ForeignKey(
        Term,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"category": "storage_condition"},
        related_name="samples_storage",
    )

    notes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.sample_id:
            last = Sample.objects.order_by("-id").first()
            num = int(last.sample_id[3:]) if last else 0
            self.sample_id = f"SAM{num+1:04d}"
        super().save(*args, **kwargs)

    def qr_code(self):
        qr = qrcode.make(self.sample_id)
        buf = BytesIO()
        qr.save(buf, format="PNG")
        image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return mark_safe(f'<img src="data:image/png;base64,{image_b64}" width="100" height="100" />')

    qr_code.short_description = "2D QR Code"

    def __str__(self):
        return self.sample_id


class Aliquot(models.Model):
    aliquot_id = models.CharField(max_length=50, unique=True, editable=False)
    sample = models.ForeignKey(Sample, on_delete=models.CASCADE)

    volume_or_mass = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    volume_or_mass_units = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        limit_choices_to={"category": "units"},
        related_name="aliquots_volume_units",
    )

    concentration = models.DecimalField(max_digits=8, decimal_places=3, null=True, blank=True)
    concentration_units = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        limit_choices_to={"category": "units"},
        related_name="aliquots_concentration_units",
    )

    prepared_date = models.DateField()
    preparation_method = models.ForeignKey(
        Term,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        limit_choices_to={"category": "preparation_method"},
        related_name="aliquots_preparation_method",
    )
    notes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.aliquot_id:
            last = Aliquot.objects.order_by("-id").first()
            num = int(last.aliquot_id[3:]) if last else 0
            self.aliquot_id = f"ALQ{num+1:04d}"
        super().save(*args, **kwargs)

    def qr_code(self):
        qr = qrcode.make(self.aliquot_id)
        buf = BytesIO()
        qr.save(buf, format="PNG")
        image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return mark_safe(f'<img src="data:image/png;base64,{image_b64}" width="100" height="100" />')

    qr_code.short_description = "2D QR Code"

    def __str__(self):
        return self.aliquot_id


class Storage(models.Model):
    device_id = models.CharField(max_length=50, unique=True)
    location = models.CharField(max_length=1024)

    temperature = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    storage_type = models.ForeignKey(
        Term,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"category": "storage_type"},
        related_name="storages",
    )

    notes = models.TextField(blank=True, null=True)
    sensors = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"Storage {self.device_id} ({self.location})"
