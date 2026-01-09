import os
import hashlib

from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.validators import FileExtensionValidator
from django.db import models

from core.models import Model
from biobank.models import Specimen
from projects.models import Project


# -----------------------------------------------------------------------------
# Upload path
# -----------------------------------------------------------------------------
def data_path(instance, filename):
    return os.path.join(
        "projects",
        str(instance.project.code),
        "omics",
        str(instance.specimen.identifier),
        filename,
    )


def qc_data_path(instance, filename):
    return os.path.join(
        "projects",
        str(instance.project.code),
        "omics",
        str(instance.specimen.identifier),
        "qc",
        filename,
    )


# -----------------------------------------------------------------------------
# Dictionary tables
# -----------------------------------------------------------------------------
class Device(Model):
    """
    Sequencing / measurement device, e.g. NovaSeq, NextSeq, ONT PromethION.
    """

    name = models.CharField(max_length=200, unique=True)
    vendor = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Device"
        verbose_name_plural = "Devices"
        ordering = ("name",)

    def __str__(self):
        return f"{self.name}"


class Target(Model):
    """
    Biological domain/assay target, e.g. genome, transcriptome, metagenome.
    """

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Target"
        verbose_name_plural = "Targets"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Chemistry(Model):
    """
    Library prep / chemistry, e.g. WGS PCR-free, amplicon PCR, bisulfite.
    """

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Chemistry"
        verbose_name_plural = "Chemistries"
        ordering = ("name",)

    def __str__(self):
        return self.name


class Repository(Model):
    """
    Public data repository / data holder.
    """

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, null=True)

    url = models.URLField(blank=True, null=True)

    class Meta:
        verbose_name = "Repository"
        verbose_name_plural = "Repositories"
        ordering = ("name",)

    def __str__(self):
        return self.name


# -----------------------------------------------------------------------------
# Generic omics artifact
# -----------------------------------------------------------------------------
class OmicsArtifact(Model):
    """
    Generic omics data artifact (file). One row = one stored file.
    Supports: .vcf, .vcf.gz, .bcf, .parquet, .tbi
    """

    project = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        related_name="omics_artifacts",
    )

    specimen = models.ForeignKey(
        Specimen,
        on_delete=models.PROTECT,
        related_name="omics_artifacts",
        help_text="Specific specimen / sample used to generate this artifact.",
    )

    target = models.ForeignKey(
        Target,
        on_delete=models.PROTECT,
        related_name="omics_artifacts",
        null=True,
        blank=True,
    )

    device = models.ForeignKey(
        Device,
        on_delete=models.PROTECT,
        related_name="omics_artifacts",
        null=True,
        blank=True,
    )

    chemistry = models.ForeignKey(
        Chemistry,
        on_delete=models.PROTECT,
        related_name="omics_artifacts",
        null=True,
        blank=True,
    )

    # Data
    file = models.FileField(
        upload_to=data_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["vcf", "vcf.gz", "bcf", "bcf.gz", "parquet"],
                message="Unsupported file type. Allowed: .vcf, .vcf.gz, .bcf, .parquet",
            )
        ],
    )

    index = models.FileField(
        upload_to=data_path,
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["tbi" ,"csi"],
                message="Unsupported file type. Allowed: .tbi, .csi",
            )
        ],
    )

    qc_metrics = models.FileField(
        upload_to=qc_data_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=["csv", "json"],
                message="Unsupported file type. Allowed: .csv, .json",
            )
        ],
        verbose_name="QC metrics",
    )

    # External data holder
    repository_name = models.ForeignKey(
        Repository,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        help_text="Data repository e.g. EGA, SRA, GEO.",
    )

    repository_id = models.CharField(
        null=True, blank=True, verbose_name="Repository ID", help_text="Record ID e.g. GSE number."
    )

    # Metadata
    metadata = models.JSONField(default=dict, null=True, blank=True, editable=False)

    class Meta:
        verbose_name = "Omics artifact"
        verbose_name_plural = "Omics artifacts"

    def __str__(self):
        return f"OmicsArtifact(project={self.project_id}, file={self.file.name})"

    @staticmethod
    def _md5_for_storage_path(path: str, chunk_size: int = 1024 * 1024) -> str:
        h = hashlib.md5()
        with default_storage.open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()

    def clean(self):
        super().clean()
        if self.repository_name and not self.repository_id:
            raise ValidationError({self.repository_id: "Please provide record ID."})

        if self.repository_id and not self.repository_name:
            raise ValidationError({self.repository_id: "Please provide repository name."})

        if (
            self.file
            and str(self.file.name).endswith(("vcf", "vcf.gz", "bcf", "bcf.gz"))
            and not self.index
        ):
            raise ValidationError(
                {
                    "index": "VCF/BCF files must be provided together with an index (.tbi or .csi) file."
                }
            )

    def save(self, *args, **kwargs):
        creating = self._state.adding

        # 1) First save: ensures files are uploaded to storage (MinIO)
        super().save(*args, **kwargs)

        # 2) Compute checksums only when we have actual keys
        updates = {}

        def add_checksum(field: models.FileField, key_name: str):
            ff = getattr(self, key_name)
            if not ff or not ff.name:
                return
            updates[f"{key_name}_checksum"] = self._md5_for_storage_path(ff.name)

        add_checksum(self.file, "file")
        add_checksum(self.index, "index")
        add_checksum(self.qc_metrics, "qc_metrics")

        if updates:
            md = dict(self.metadata or {})
            md.update(updates)

            # Avoid recursion: update only metadata column
            OmicsArtifact.objects.filter(pk=self.pk).update(metadata=md)
            self.metadata = md
