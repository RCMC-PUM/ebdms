# omics/models.py
from __future__ import annotations

import hashlib
from django.core.files.storage import default_storage
from django.db import models

from biobank.models import Sample


class Device(models.Model):
    """
    Sequencing / measurement device, e.g. NovaSeq, NextSeq, ONT PromethION, etc.
    """
    name = models.CharField(max_length=200, unique=True)
    vendor = models.CharField(max_length=200, blank=True)
    model = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = "Device"
        verbose_name_plural = "Devices"

    def __str__(self) -> str:
        return f"{self.name} ({self.model})"


class Target(models.Model):
    """
    Domain/assay target, e.g. genome, epigenome, metagenome, transcriptome...
    """
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name


class Chemistry(models.Model):
    """
    Library prep / chemistry, e.g. no-PCR library prep, bisulfite, amplicon PCR, etc.
    """
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)

    def __str__(self) -> str:
        return self.name


class OmicsFile(models.Model):
    sample = models.ForeignKey(
        Sample,
        on_delete=models.PROTECT,
        related_name="omics_files",
    )

    chemistry = models.ForeignKey(
        Chemistry,
        on_delete=models.PROTECT,
        related_name="omics_files",
    )

    device = models.ForeignKey(
        Device,
        on_delete=models.PROTECT,
        related_name="omics_files",
    )

    target = models.ForeignKey(
        Target,
        on_delete=models.PROTECT,
        related_name="omics_files",
    )

    file = models.FileField(upload_to="omics/%Y/%m/%d/")

    fastqc_metrics = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    md5 = models.CharField(max_length=32, blank=True, editable=False, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "NGS"
        verbose_name_plural = "NGS"

        indexes = [
            models.Index(fields=["sample", "target"]),
            models.Index(fields=["device"]),
            models.Index(fields=["chemistry"]),
        ]

    def __str__(self) -> str:
        return f"OmicsFile(sample={self.sample_id}, file={self.file.name})"

    @staticmethod
    def _md5_for_storage_path(path: str, chunk_size: int = 1024 * 1024) -> str:
        h = hashlib.md5()
        with default_storage.open(path, "rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()

    def save(self, *args, **kwargs):
        # Best-effort "file changed" detection
        file_changed = False
        if self.pk:
            old = type(self).objects.filter(pk=self.pk).only("file").first()
            if old and old.file and self.file:
                file_changed = old.file.name != self.file.name
            elif old and old.file and not self.file:
                file_changed = True
            elif (not old or not old.file) and self.file:
                file_changed = True
        else:
            file_changed = bool(self.file)

        super().save(*args, **kwargs)  # ensures file is stored and path exists

        if self.file and (not self.md5 or file_changed):
            new_md5 = self._md5_for_storage_path(self.file.name)
            if new_md5 != self.md5:
                type(self).objects.filter(pk=self.pk).update(md5=new_md5)
                self.md5 = new_md5
