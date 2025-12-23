from pathlib import Path

from django.core.validators import FileExtensionValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db import models

from projects.models import Project


def order_upload_to(instance, filename):
    ext = Path(filename).suffix.lower()
    return f"orders/{timezone.now():%Y/%m}/order_{instance.pk or 'new'}{ext}"


class Order(models.Model):
    order_internal_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        unique=True,
        help_text="Order internal (unique) ID."
    )

    person_responsible = models.CharField(
        max_length=255,
        help_text="Person responsible for this particular order."
    )

    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Select the project this order belongs to."
    )

    order_list = models.FileField(
        upload_to=order_upload_to,
        blank=True,
        null=True,
        validators=[FileExtensionValidator(["xlsx"])],
        help_text="The excel list of items/services to order, upload to fill order automatically."
    )

    total_price = models.DecimalField(
        decimal_places=2,
        max_digits=12,
        editable=False,
        blank=True,
        null=True,
        help_text="Total price estimated for this particular order."
    )

    description = models.TextField(
        null=True,
        blank=True,
        help_text="Order description."
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Order creation date"
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Order"
        verbose_name_plural = "Orders"

    def __str__(self):
        return f"{self.order_internal_id} | {self.person_responsible}"


class StockItem(models.Model):
    class ItemType(models.TextChoices):
        CHEMISTRY = "CHEMISTRY", "CHEMISTRY"
        PLASTICS = "PLASTICS", "PLASTICS"
        SERVICE = "SERVICE", "SERVICE"

    order = models.ForeignKey(
        Order,
        related_name="stock_items",
        on_delete=models.CASCADE,
        help_text="Order ID."
    )

    name = models.CharField(
        max_length=255,
        help_text="Product name."
    )

    item_type = models.CharField(
        max_length=10,
        choices=ItemType.choices,
        help_text="Product category, either PLASTICS, CHEMISTRY or SERVICE."
    )

    provider = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text="Product provider e.g. Illumina"
    )

    catalog_number = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text="Product catalog number."
    )

    unit_price_gross = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        null=True,
        blank=True,
        help_text="Product gross price."
    )

    available = models.BooleanField(
        default=False,
        help_text="Indicator whether the product has been delivered and is available."
    )

    lot = models.CharField(
        unique=True,
        blank=True,
        null=True,
        help_text="Product-specific (unique) LOT number."
    )

    expiration_waring_date = models.IntegerField(
        default=30,
        help_text="Number of days (default 30) before the expiration date when a warning should be triggered."
    )

    expiration_date = models.DateField(
        blank=True,
        null=True,
        help_text="Product's expiration date."
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Record creation date."
    )

    class Meta:
        ordering = ["expiration_date"]
        verbose_name = "Stock items"
        verbose_name_plural = "Stock items"

    def clean(self):
        if self.available and self.item_type != self.ItemType.SERVICE and not self.lot:
            raise ValidationError({"lot": f"If the product is available please provide LOT number!"})

        if self.available and self.item_type == self.ItemType.CHEMISTRY and not self.expiration_date:
            raise ValidationError({"expiration_date": f"If the chemistry is available please specify expiration date!"})

    def __str__(self):
        return f"Product: {self.name} ({self.provider})"


class Tag(models.Model):
    class Color(models.TextChoices):
        GREEN = "green", "Green"
        BLUE = "blue", "Blue"
        YELLOW = "yellow", "Yellow"
        RED = "red", "Red"

    name = models.CharField(
        max_length=24,
        unique=True,
    )
    color = models.CharField(max_length=10, choices=Color.choices, default=Color.BLUE)

    def __str__(self) -> str:
        return str(self.name)

    class Meta:
        ordering = ("name",)


class LNotebook(models.Model):
    name = models.CharField(unique=True, max_length=512)
    content = models.TextField(null=True, blank=True)

    tags = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="notebooks",
        through="LNotebookTag",
    )

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self) -> str:
        if self.tags:
            joined_tags = " ".join([t.name for t in self.tags.all()])
            return f"{self.name} → {joined_tags}"
        return str(self.name)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "Laboratory notebook"
        verbose_name_plural = "Laboratory notebooks"


class LNotebookTag(models.Model):
    notebook = models.ForeignKey(LNotebook, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        unique_together = (("notebook", "tag"),)
        verbose_name = "Notebook tag"
        verbose_name_plural = "Notebook tags"

    def __str__(self) -> str:
        return f"{self.notebook} → {self.tag}"


def notebook_upload_to(instance, filename: str) -> str:
    nb = instance.notebook_id or "unassigned"
    return f"notebooks/{nb}/{filename}"


class Document(models.Model):
    notebook = models.ForeignKey(
        LNotebook,
        on_delete=models.CASCADE,
        related_name="documents",
    )

    name = models.CharField(max_length=255, blank=True, unique=True)
    file = models.FileField(
        upload_to=notebook_upload_to,
        validators=[FileExtensionValidator(allowed_extensions=["pdf", "xls", "xlsx", "doc", "docx", "csv"])],
    )

    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)

    def __str__(self) -> str:
        return str(self.name)
