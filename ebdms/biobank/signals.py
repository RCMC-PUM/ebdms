from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Specimen, Aliquot


@receiver(post_save, sender=Specimen)
def create_aliquots_for_new_specimen(
    sender,
    instance: Specimen,
    created: bool,
    **kwargs,
):
    """
    Automatically create aliquots when a new specimen is created.
    """

    if not created:
        return

    # Safety: do not create twice
    if instance.aliquots.exists():
        return

    # Optional: only if you keep n_aliquots on Specimen
    n = getattr(instance, "n_aliquots", 0) or 0
    n = max(0, int(n))

    if n == 0:
        return

    with transaction.atomic():
        Aliquot.objects.bulk_create(
            [
                Aliquot(specimen=instance)
                for _ in range(n)
            ]
        )
