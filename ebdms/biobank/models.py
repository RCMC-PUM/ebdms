import base64, qrcode
from io import BytesIO

from django.core.exceptions import ValidationError
from django.utils.safestring import mark_safe
from django.core.validators import MinValueValidator
from django.db.models import Q, UniqueConstraint

from django.db import models

from core.models import Model
from projects.models import Project, Participant
from ontologies.models import SampleType


# =============================================================================
# Storage
# =============================================================================


class Storage(Model):
    """
    A physical storage unit or location
    (e.g. freezer, LN2 tank, room, rack system).
    """

    name = models.CharField(
        max_length=255,
        unique=True,
        help_text="Unique storage identifier or name (e.g. Freezer A1).",
    )

    conditions = models.CharField(
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


class Box(Model):
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


class ProcessingProtocol(Model):
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


class Specimen(Model):
    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="specimens",
    )
    participant = models.ForeignKey(
        Participant,
        on_delete=models.PROTECT,
        related_name="specimens",
        null=True,
        blank=True,
    )

    identifier = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        blank=True,
        default="",
        help_text="System-generated unique specimen identifier.",
    )

    sample_type = models.ForeignKey(
        SampleType,
        on_delete=models.PROTECT,
        related_name="specimens",
    )

    note = models.TextField(blank=True, null=True)
    protocols = models.ForeignKey(
        ProcessingProtocol,
        on_delete=models.PROTECT,
        related_name="specimens",
        blank=True,
        null=True,
    )

    class Meta:
        ordering = ["-id"]

    def __str__(self) -> str:
        return self.identifier or f"Specimen #{self.pk or 'new'}"

    def clean(self):
        # participant must belong to same project
        if self.participant_id and self.project_id:
            if getattr(self.participant, "project_id", None) != self.project_id:
                raise ValidationError(
                    {
                        "participant": "Participant must belong to the same project as the specimen."
                    }
                )

    def save(self, *args, **kwargs):
        # optional but recommended for correctness when created outside admin/forms
        self.full_clean()

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


class Aliquot(Model):
    specimen = models.ForeignKey(
        Specimen,
        on_delete=models.CASCADE,
        related_name="aliquots",
    )

    sample_type = models.ForeignKey(
        SampleType,
        on_delete=models.PROTECT,
        related_name="aliquots",
        null=True,  # you can tighten to False after a data migration
        blank=True,  # allow defaulting from specimen
        help_text="Aliquot material type (defaults to specimen sample type).",
    )

    identifier = models.CharField(
        max_length=96,
        unique=True,
        editable=False,
        db_index=True,
        blank=True,
        default="",
        help_text="System-generated unique aliquot identifier.",
    )

    box = models.ForeignKey(
        Box,
        on_delete=models.PROTECT,
        related_name="aliquots",
        null=True,
        blank=True,
    )

    row = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Row position in the box (1-based).",
    )
    col = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        help_text="Column position in the box (1-based).",
    )

    class Meta:
        ordering = ["-id"]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(box__isnull=True, row__isnull=True, col__isnull=True)
                    | Q(box__isnull=False, row__isnull=False, col__isnull=False)
                ),
                name="aliquot_box_row_col_all_or_none",
            ),
        ]

        indexes = [
            models.Index(fields=["box", "row", "col"], name="aliquot_box_grid_idx"),
            models.Index(fields=["specimen"], name="aliquot_specimen_idx"),
        ]

    def __str__(self) -> str:
        if self.specimen.participant:
            return f"{self.identifier} from {self.specimen.participant}"

        return str(self.identifier)

    def clean(self):
        # Default sample_type from specimen (keeps admin/forms pleasant)
        if self.specimen_id and not self.sample_type_id:
            self.sample_type = self.specimen.sample_type

        # Validate box placement range (DB can't enforce rows/cols because it's on related Box)
        if self.box_id:
            if self.row is None or self.col is None:
                raise ValidationError(
                    "Row and column must be set when a box is assigned."
                )

            if self.row < 1 or self.row > self.box.rows:
                raise ValidationError(
                    {"row": f"Row must be between 1 and {self.box.rows}."}
                )

            if self.col < 1 or self.col > self.box.cols:
                raise ValidationError(
                    {"col": f"Column must be between 1 and {self.box.cols}."}
                )

    def save(self, *args, **kwargs):
        self.full_clean()

        creating = self.pk is None
        super().save(*args, **kwargs)

        if creating:
            identifier = f"{self.specimen.project.code}_{self.specimen.pk}_{self.pk}"
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

        return mark_safe(
            f'<img src="data:image/png;base64,{b64}" width=50px height=50px"/>'
        )
