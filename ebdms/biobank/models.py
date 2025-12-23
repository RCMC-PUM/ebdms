import base64, qrcode
from io import BytesIO

from django.db import models
from django.db.models import UniqueConstraint
from django.utils.safestring import mark_safe
from django.core.validators import MinValueValidator

from projects.models import Project, Participant
from ontologies.models import SampleType


# =============================================================================
# Storage
# =============================================================================

class Storage(models.Model):
    """
    A physical storage unit or location
    (e.g. freezer, LN2 tank, room, rack system).
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique storage identifier or name (e.g. Freezer A1).",
    )

    conditions = models.TextField(
        blank=True,
        help_text="Storage conditions (e.g. -80°C, LN2 vapor phase, humidity notes).",
    )

    location = models.CharField(
        max_length=512,
        blank=True,
        help_text="Human-readable physical location description.",
    )

    sensors = models.JSONField(
        default=dict,
        blank=True,
        editable=False,
        help_text="Read-only sensor metadata (temperature, alarms, door state, etc.).",
    )

    class Meta:
        verbose_name = "Storage"
        verbose_name_plural = "Storages"
        ordering = ["name", "id"]

    def __str__(self) -> str:
        return self.name


# =============================================================================
# Box
# =============================================================================

class Box(models.Model):
    """
    A box/container inside a storage unit with a defined grid capacity.
    """

    storage = models.ForeignKey(
        Storage,
        on_delete=models.PROTECT,
        related_name="boxes",
        help_text="Storage unit where this box is located.",
    )

    name = models.CharField(
        max_length=255,
        help_text="Box identifier within the storage (e.g. Box 01, Rack A / Box 3).",
    )

    rows = models.PositiveIntegerField(
        default=9,
        validators=[MinValueValidator(1)],
        help_text="Number of rows in the box grid.",
    )

    cols = models.PositiveIntegerField(
        default=9,
        validators=[MinValueValidator(1)],
        help_text="Number of columns in the box grid.",
    )

    class Meta:
        verbose_name = "Box"
        verbose_name_plural = "Boxes"
        ordering = ["storage__name", "name", "id"]
        constraints = [
            UniqueConstraint(
                fields=["storage", "name"],
                name="unique_box_name_per_storage",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.storage} / {self.name}"

    @property
    def n_total_samples(self) -> int:
        """Total capacity of the box."""
        return int(self.rows) * int(self.cols)

    @property
    def n_samples(self) -> int:
        """Number of occupied positions (aliquots)."""
        return self.aliquots.count()

    @property
    def occupation_percent(self) -> float:
        """Box occupancy percentage."""
        total = self.n_total_samples
        if total <= 0:
            return 0.0
        return round((self.n_samples / total) * 100.0, 2)


# =============================================================================
# Processing Protocol
# =============================================================================

class ProcessingProtocol(models.Model):
    """
    A reusable processing protocol applied to specimens.
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Short, unique protocol name.",
    )

    description = models.TextField(
        help_text="Detailed protocol description or steps.",
    )

    file = models.FileField(
        upload_to="protocols/",
        null=True,
        blank=True,
        help_text="Optional protocol document (PDF, DOCX, etc.).",
    )

    class Meta:
        verbose_name = "Processing protocol"
        verbose_name_plural = "Processing protocols"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


# =============================================================================
# Specimen
# =============================================================================

class Specimen(models.Model):
    """
    A top-level biological sample.

    Identifier format:
        PROJECTCODE_<specimen.pk>
    """

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="specimens",
        help_text="Project to which this specimen belongs.",
    )

    participant = models.ForeignKey(
        Participant,
        on_delete=models.PROTECT,
        related_name="specimens",
        null=True,
        blank=True,
        help_text="Participant from whom the specimen was collected (if applicable).",
    )

    identifier = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        help_text="System-generated unique specimen identifier.",
    )

    sample_type = models.ForeignKey(
        SampleType,
        on_delete=models.PROTECT,
        related_name="specimens",
        help_text="Type of biological material.",
    )

    note = models.TextField(
        blank=True,
        null=True,
        help_text="Optional free-text notes about the specimen.",
    )

    protocols = models.ForeignKey(
        ProcessingProtocol,
        on_delete=models.PROTECT,
        related_name="specimens",
        blank=True,
        null=True,
        help_text="Processing protocol applied to this specimen.",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        help_text="Creation timestamp.",
    )

    class Meta:
        verbose_name = "Specimen"
        verbose_name_plural = "Specimens"
        ordering = ["-id"]

    def __str__(self) -> str:
        return self.identifier

    def save(self, *args, **kwargs):
        """
        Two-phase save to generate identifier using primary key.
        """
        creating = self.pk is None
        super().save(*args, **kwargs)

        if creating:
            identifier = f"{self.project.code}_{self.pk}"
            if self.identifier != identifier:
                Specimen.objects.filter(pk=self.pk).update(identifier=identifier)
                self.identifier = identifier


# =============================================================================
# Aliquot
# =============================================================================

class Aliquot(models.Model):
    """
    An aliquot derived from a specimen.

    Identifier format:
        PROJECTCODE_<specimen.pk>_<aliquot.pk>
    """

    specimen = models.ForeignKey(
        Specimen,
        on_delete=models.CASCADE,
        related_name="aliquots",
        help_text="Parent specimen.",
    )

    identifier = models.CharField(
        max_length=96,
        unique=True,
        editable=False,
        db_index=True,
        help_text="System-generated unique aliquot identifier.",
    )

    box = models.ForeignKey(
        Box,
        on_delete=models.PROTECT,
        related_name="aliquots",
        null=True,
        blank=True,
        help_text="Box where this aliquot is stored.",
    )

    row = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Row position in the box (1-based).",
    )

    col = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Column position in the box (1-based).",
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        help_text="Creation timestamp.",
    )

    class Meta:
        verbose_name = "Aliquot"
        verbose_name_plural = "Aliquots"
        ordering = ["-id"]
        constraints = [
            UniqueConstraint(
                fields=["box", "row", "col"],
                name="unique_aliquot_position_in_box",
            ),
        ]

    def __str__(self) -> str:
        return self.identifier

    def clean(self):
        """
        Validate box placement.
        """
        if self.box_id:
            from django.core.exceptions import ValidationError

            if self.row is None or self.col is None:
                raise ValidationError(
                    "Row and column must be set when a box is assigned."
                )

            if not (1 <= self.row <= self.box.rows):
                raise ValidationError(
                    f"Row must be between 1 and {self.box.rows}."
                )

            if not (1 <= self.col <= self.box.cols):
                raise ValidationError(
                    f"Column must be between 1 and {self.box.cols}."
                )

    def save(self, *args, **kwargs):
        """
        Two-phase save to generate identifier using primary key.
        """
        creating = self.pk is None
        super().save(*args, **kwargs)

        if creating:
            identifier = (
                f"{self.specimen.project.code}_{self.specimen.pk}_{self.pk}"
            )
            if self.identifier != identifier:
                Aliquot.objects.filter(pk=self.pk).update(identifier=identifier)
                self.identifier = identifier

    @property
    def qr_code(self):
        if not self.identifier:
            return "—"

        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=6,
            border=2,
        )
        qr.add_data(self.identifier)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        buf = BytesIO()

        img.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return mark_safe(f'<img src="data:image/png;base64,{b64}" class="qr"/>')
