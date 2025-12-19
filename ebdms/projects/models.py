from django.db import models
from django.utils import timezone
from simple_history.models import HistoricalRecords


class Institution(models.Model):
    name = models.CharField(max_length=1024)
    department = models.CharField(max_length=1024, null=True, blank=True)

    address = models.CharField(max_length=1024, unique=True, blank=True, null=True)
    code = models.CharField(max_length=12, unique=True)
    history = HistoricalRecords()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "department"],
                name="unique_institution_name_department",
            )
        ]

    def __str__(self):
        return f"{self.department} ({self.name})"


class PrincipalInvestigator(models.Model):
    name = models.CharField(max_length=512)
    surname = models.CharField(max_length=512)

    email = models.EmailField()
    phone = models.CharField(max_length=22, blank=True, null=True)

    institution = models.ForeignKey(Institution, on_delete=models.PROTECT)
    history = HistoricalRecords()

    def __str__(self):
        return f"{self.name} {self.surname} ({self.institution})"


class Project(models.Model):
    name = models.CharField(max_length=512, unique=True)
    code = models.CharField(max_length=6, unique=True)

    description = models.CharField()
    principal_investigator = models.ForeignKey(PrincipalInvestigator, on_delete=models.PROTECT)
    status = models.BooleanField(default=True)

    start_date = models.DateTimeField()
    end_date = models.DateTimeField(blank=True, null=True)
    history = HistoricalRecords()

    class Meta:
        ordering = ["start_date"]

    @property
    def is_active(self):
        if self.status and self.end_date > timezone.now():
            return True
        return False

    def __str__(self):
        return self.name
