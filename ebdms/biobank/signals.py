from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Sample, Aliquot


@receiver(post_save, sender=Sample)
def create_aliquots_for_new_sample(sender, instance: Sample, created: bool, **kwargs):
    if not created:
        return

    # If you only want to create when there are none yet (extra safety):
    if instance.aliquots.exists():
        return

    # Create N aliquots
    n = max(0, int(instance.n_aliquots or 0))

    if n == 0:
        return

    with transaction.atomic():
        for _ in range(n):
            Aliquot.objects.create(
                sample=instance,
                volume_or_mass=0,                       # <-- choose your default
                prepared_date=timezone.now().date(),     # <-- choose your default
            )
