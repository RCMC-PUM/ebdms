from django.db import models
from simple_history.models import HistoricalRecords


class Model(models.Model):
    class Meta:
        ordering = ("created_at",)
        abstract = True

    # ------------------------------------------------------------------
    # Object history
    # ------------------------------------------------------------------
    # In case of M2M to ensure tracking, the class should overwrite default history field
    # E.g., history = HistoricalRecords(m2m_fields=[categories])
    history = HistoricalRecords(inherit=True, cascade_delete_history=True)

    # ------------------------------------------------------------------
    # Created at / updated at
    # ------------------------------------------------------------------
    created_at = models.DateTimeField(
        auto_now_add=True,
        editable=False,
        db_index=True,
        help_text="Object creation timestamp.",
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        editable=False,
        db_index=True,
        help_text="Last object update timestamp.",
    )
