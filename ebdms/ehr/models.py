from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from django.core.exceptions import ValidationError
from django.core.validators import (
    EmailValidator,
    FileExtensionValidator,
    MaxLengthValidator,
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
    RegexValidator,
    URLValidator,
    validate_slug,
    validate_unicode_slug,
)
from django.db import models
from django.utils.dateparse import parse_date, parse_datetime
from django.utils.text import slugify

from simple_history.models import HistoricalRecords

from biobank.models import Donor


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp when this record was created.",
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        db_index=True,
        help_text="Timestamp when this record was last updated.",
    )

    class Meta:
        abstract = True


class Form(TimeStampedModel):
    name = models.CharField(
        max_length=255,
        help_text="Human-readable name of the form.",
    )
    description = models.CharField(
        null=True,
        blank=True,
        help_text="Optional description shown to users filling out the form.",
    )
    slug = models.SlugField(
        max_length=255,
        unique=True,
        editable=False,
        help_text="Unique identifier used in URLs and APIs.",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Inactive forms cannot receive new responses.",
    )
    history = HistoricalRecords()

    def clean(self) -> None:
        super().clean()
        if not self.name or not str(self.name).strip():
            raise ValidationError({"name": "Name cannot be empty."})

    def save(self, *args, **kwargs):
        self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


@dataclass(frozen=True)
class ChoiceItem:
    value: Any
    label: str | None = None


class FormField(TimeStampedModel):
    class FieldType(models.TextChoices):
        TEXT = "text", "Text"
        INTEGER = "integer", "Integer"
        DECIMAL = "decimal", "Decimal"
        BOOLEAN = "boolean", "Boolean"
        EMAIL = "email", "Email"
        URL = "url", "URL"
        DATE = "date", "Date"
        DATETIME = "datetime", "Datetime"
        CHOICE = "choice", "Choice"
        MULTICHOICE = "multichoice", "Multi-choice"
        FILE = "file", "File"

    form = models.ForeignKey(
        Form,
        on_delete=models.CASCADE,
        related_name="fields",
        help_text="Form this field belongs to.",
    )

    key = models.SlugField(
        max_length=100,
        help_text="Unique key used in Response.result JSON.",
    )
    label = models.CharField(
        max_length=255,
        help_text="Label displayed to the end user.",
    )
    help_text = models.TextField(
        blank=True,
        default="",
        help_text="Additional guidance shown to the user when filling out this field.",
    )
    field_type = models.CharField(
        max_length=20,
        choices=FieldType.choices,
        default=FieldType.TEXT,
        help_text="Type of data expected for this field.",
    )

    required = models.BooleanField(
        default=False,
        help_text="Whether this field must be provided in a response.",
    )
    order = models.PositiveIntegerField(
        default=0,
        help_text="Controls display order of fields within the form.",
    )

    # Choices
    choices = models.JSONField(
        blank=True,
        null=True,
        help_text=(
            "Used for Choice and Multi-choice fields. "
        ),
    )

    # ---------------------------
    # Validator toggles
    # ---------------------------
    use_min_length = models.BooleanField(
        default=False,
        help_text="Enable minimum length validation.",
    )
    min_length = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Minimum allowed length (used if min length validation is enabled).",
    )

    use_max_length = models.BooleanField(
        default=False,
        help_text="Enable maximum length validation.",
    )
    max_length = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum allowed length (used if max length validation is enabled).",
    )

    use_min_value = models.BooleanField(
        default=False,
        help_text="Enable minimum numeric value validation.",
    )
    min_value = models.DecimalField(
        max_digits=24,
        decimal_places=10,
        null=True,
        blank=True,
        help_text="Minimum allowed numeric value.",
    )

    use_max_value = models.BooleanField(
        default=False,
        help_text="Enable maximum numeric value validation.",
    )
    max_value = models.DecimalField(
        max_digits=24,
        decimal_places=10,
        null=True,
        blank=True,
        help_text="Maximum allowed numeric value.",
    )

    use_regex = models.BooleanField(
        default=False,
        help_text="Enable regular expression validation.",
    )
    regex_pattern = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="Regular expression pattern to validate the input.",
    )
    regex_message = models.CharField(
        max_length=255,
        blank=True,
        default="",
        help_text="Optional custom error message for regex validation.",
    )
    regex_flags = models.PositiveIntegerField(
        default=0,
        help_text="Python 're' module flags as an integer (e.g. IGNORECASE).",
    )

    use_email_validator = models.BooleanField(
        default=False,
        help_text="Validate value as an email address.",
    )
    use_url_validator = models.BooleanField(
        default=False,
        help_text="Validate value as a URL.",
    )

    # File validators
    use_file_extension_validator = models.BooleanField(
        default=False,
        help_text="Restrict uploaded files to specific extensions.",
    )
    allowed_extensions = models.JSONField(
        blank=True,
        null=True,
        help_text="List of allowed file extensions (e.g. ['pdf', 'png']).",
    )

    history = HistoricalRecords()

    class Meta:
        ordering = ["order", "id"]
        unique_together = [("form", "key")]

    # ---------------------------
    # Validation helpers
    # ---------------------------
    def _normalized_choices(self) -> list[ChoiceItem]:
        """
        Normalize `choices` into a list of ChoiceItem(value, label).
        Accepts:
          - ['a', 'b']
        """
        if self.choices in (None, ""):
            raise ValidationError({"choices": "Choices can not be empty."})

        if not isinstance(self.choices, list):
            raise ValidationError({"choices": "Choices must be a list."})

        out = []
        for idx, item in enumerate(self.choices):
            out.append(ChoiceItem(value=item, label=item))
        return out

    def _choice_values_set(self) -> set[Any]:
        return {c.value for c in self._normalized_choices()}

    def _is_blank(self, value: Any) -> bool:
        return value is None or value == "" or value == [] or value == {}

    def _coerce_numeric(self, value: Any) -> Decimal:
        if isinstance(value, bool):
            raise ValidationError("Boolean is not a valid numeric value.")
        if isinstance(value, (int, Decimal)):
            return Decimal(str(value))
        if isinstance(value, float):
            # avoid binary float surprises by round-tripping through str
            return Decimal(str(value))
        if isinstance(value, str):
            try:
                return Decimal(value.strip())
            except (InvalidOperation, AttributeError):
                raise ValidationError("Enter a valid number.")
        raise ValidationError("Enter a valid number.")

    @staticmethod
    def _coerce_integer(value: Any) -> int:
        if isinstance(value, bool):
            raise ValidationError("Enter a whole number.")
        if isinstance(value, int):
            return value
        if isinstance(value, Decimal):
            if value % 1 != 0:
                raise ValidationError("Enter a whole number.")
            return int(value)
        if isinstance(value, str):
            s = value.strip()
            if s == "":
                raise ValidationError("Enter a whole number.")
            try:
                i = int(s)
            except ValueError:
                raise ValidationError("Enter a whole number.")
            return i
        raise ValidationError("Enter a whole number.")

    @staticmethod
    def _coerce_boolean(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            s = value.strip().lower()
            if s in ("true", "1", "yes", "y", "on"):
                return True
            if s in ("false", "0", "no", "n", "off"):
                return False
        raise ValidationError("Enter a valid boolean.")

    @staticmethod
    def _coerce_date(value: Any):
        if value is None:
            return None
        if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day") and not hasattr(
            value, "hour"
        ):
            return value  # likely a datetime.date
        if isinstance(value, str):
            d = parse_date(value.strip())
            if d is None:
                raise ValidationError("Enter a valid date (YYYY-MM-DD).")
            return d
        raise ValidationError("Enter a valid date (YYYY-MM-DD).")

    @staticmethod
    def _coerce_datetime(value: Any):
        if value is None:
            return None
        if hasattr(value, "year") and hasattr(value, "month") and hasattr(value, "day") and hasattr(value, "hour"):
            return value  # likely a datetime.datetime
        if isinstance(value, str):
            dt = parse_datetime(value.strip())
            if dt is None:
                raise ValidationError("Enter a valid datetime (ISO 8601).")
            return dt
        raise ValidationError("Enter a valid datetime (ISO 8601).")

    @staticmethod
    def _file_name_from_value(value: Any) -> str | None:
        """
        For FILE fields, accept a string filename or a dict containing:
          - name, filename, or path
        """
        if value is None:
            return None
        if isinstance(value, str):
            return value.strip() or None
        if isinstance(value, dict):
            for k in ("name", "filename", "path"):
                v = value.get(k)
                if isinstance(v, str) and v.strip():
                    return v.strip()
            return None
        return None

    def get_value_validators(self) -> list:
        """
        Build Django validator callables based on toggles.
        These validators are applied after basic type/shape checks.
        """
        validators: list = []

        if self.use_min_length:
            if self.min_length is None:
                raise ValidationError({"min_length": "min_length must be set if use_min_length is enabled."})
            validators.append(MinLengthValidator(int(self.min_length)))

        if self.use_max_length:
            if self.max_length is None:
                raise ValidationError({"max_length": "max_length must be set if use_max_length is enabled."})
            validators.append(MaxLengthValidator(int(self.max_length)))

        if self.use_min_value:
            if self.min_value is None:
                raise ValidationError({"min_value": "min_value must be set if use_min_value is enabled."})
            validators.append(MinValueValidator(self.min_value))

        if self.use_max_value:
            if self.max_value is None:
                raise ValidationError({"max_value": "max_value must be set if use_max_value is enabled."})
            validators.append(MaxValueValidator(self.max_value))

        if self.use_regex:
            if not self.regex_pattern:
                raise ValidationError({"regex_pattern": "regex_pattern must be set if use_regex is enabled."})
            validators.append(
                RegexValidator(
                    regex=self.regex_pattern,
                    message=self.regex_message or None,
                    flags=int(self.regex_flags or 0),
                )
            )

        if self.use_email_validator:
            validators.append(EmailValidator())

        if self.use_url_validator:
            validators.append(URLValidator())

        if self.use_file_extension_validator:
            if not self.allowed_extensions or not isinstance(self.allowed_extensions, list):
                raise ValidationError(
                    {"allowed_extensions": "allowed_extensions must be a list if use_file_extension_validator is enabled."}
                )
            allowed = [str(x).lstrip(".").lower() for x in self.allowed_extensions if str(x).strip()]
            if not allowed:
                raise ValidationError({"allowed_extensions": "allowed_extensions cannot be empty."})
            validators.append(FileExtensionValidator(allowed_extensions=allowed))

        return validators

    def validate_value(self, value: Any) -> None:
        """
        Validate a single submitted value for this field.
        Raises ValidationError with a user-friendly message.
        """
        # Required / blank
        if self.required and self._is_blank(value):
            raise ValidationError("This field is required.")
        if self._is_blank(value):
            return  # not required and blank -> OK

        # Field-type shape and coercion checks
        # (We don't mutate stored JSON here; just validate.)
        if self.field_type == self.FieldType.TEXT:
            if not isinstance(value, str):
                raise ValidationError("Enter a valid text value.")
            coerced = value

        elif self.field_type == self.FieldType.EMAIL:
            if not isinstance(value, str):
                raise ValidationError("Enter a valid email address.")
            coerced = value

        elif self.field_type == self.FieldType.URL:
            if not isinstance(value, str):
                raise ValidationError("Enter a valid URL.")
            coerced = value

        elif self.field_type == self.FieldType.INTEGER:
            i = self._coerce_integer(value)
            coerced = Decimal(i)  # for Min/MaxValueValidator compatibility

        elif self.field_type == self.FieldType.DECIMAL:
            d = self._coerce_numeric(value)
            coerced = d

        elif self.field_type == self.FieldType.BOOLEAN:
            self._coerce_boolean(value)
            coerced = value  # validators generally not used for bool

        elif self.field_type == self.FieldType.DATE:
            self._coerce_date(value)
            coerced = value

        elif self.field_type == self.FieldType.DATETIME:
            self._coerce_datetime(value)
            coerced = value

        elif self.field_type == self.FieldType.CHOICE:
            values = self._choice_values_set()
            if not values:
                raise ValidationError("Field has no configured choices.")
            if value not in values:
                raise ValidationError("Select a valid choice.")
            coerced = value

        elif self.field_type == self.FieldType.MULTICHOICE:
            values = self._choice_values_set()
            if not values:
                raise ValidationError("Field has no configured choices.")
            if not isinstance(value, list):
                raise ValidationError("Enter a list of choices.")
            invalid = [v for v in value if v not in values]
            if invalid:
                raise ValidationError("One or more selected choices are invalid.")
            coerced = value

        elif self.field_type == self.FieldType.FILE:
            # We validate extensions against a filename if present.
            name = self._file_name_from_value(value)
            if name is None:
                # allow storing metadata-only dicts, but required already handled above
                coerced = ""
            else:
                coerced = name

        else:
            raise ValidationError("Unsupported field type.")

        # Apply toggle validators (where applicable)
        validators = self.get_value_validators()

        # Some validators expect strings; some expect numbers.
        # For MULTICHOICE we apply string validators to each element if enabled.
        try:
            if self.field_type == self.FieldType.MULTICHOICE:
                for item in value:
                    for v in validators:
                        v(item)
            elif self.field_type == self.FieldType.FILE:
                # FileExtensionValidator expects a filename-like string
                if isinstance(coerced, str) and coerced:
                    for v in validators:
                        v(coerced)
            else:
                for v in validators:
                    v(coerced)
        except ValidationError as e:
            raise ValidationError(e.messages)

    def clean(self) -> None:
        """
        Validate the field configuration itself.
        """
        super().clean()

        # key must be a slug (SlugField will do it too, but keep error nice)
        try:
            validate_slug(self.key)
        except ValidationError:
            raise ValidationError({"key": "Key must be a valid slug (letters, numbers, underscores or hyphens)."})

        # Min/max consistency
        if self.use_min_length and self.use_max_length and self.min_length is not None and self.max_length is not None:
            if int(self.min_length) > int(self.max_length):
                raise ValidationError({"min_length": "min_length cannot be greater than max_length."})

        if self.use_min_value and self.use_max_value and self.min_value is not None and self.max_value is not None:
            if Decimal(self.min_value) > Decimal(self.max_value):
                raise ValidationError({"min_value": "min_value cannot be greater than max_value."})

        # Choice requirements
        if self.field_type in (self.FieldType.CHOICE, self.FieldType.MULTICHOICE):
            normalized = self._normalized_choices()
            if not normalized:
                raise ValidationError({"choices": "Choices must be set for Choice and Multi-choice fields."})

        # File extension requirements
        if self.use_file_extension_validator:
            if not self.allowed_extensions or not isinstance(self.allowed_extensions, list):
                raise ValidationError({"allowed_extensions": "allowed_extensions must be a list when enabled."})

        # Ensure toggle-driven validators are well-formed
        _ = self.get_value_validators()

    def __str__(self) -> str:
        return f"{self.form.slug}:{self.key}"


class Response(TimeStampedModel):
    donor = models.ForeignKey(
        Donor,
        on_delete=models.PROTECT,
        help_text="Donor who submitted this response.",
    )
    form = models.ForeignKey(
        Form,
        on_delete=models.PROTECT,
        help_text="Form that was filled out.",
    )
    result = models.JSONField(
        null=False,
        blank=False,
        help_text="Submitted form data as a JSON object keyed by FormField.key.",
    )

    history = HistoricalRecords()

    def clean(self) -> None:
        super().clean()

        if self.form_id is None:
            raise ValidationError({"form": "Form is required."})

        if not isinstance(self.result, dict):
            raise ValidationError({"result": "Result must be a JSON object (dictionary) keyed by field keys."})

        # Gather fields for the form
        fields = list(self.form.fields.all())
        field_by_key = {f.key: f for f in fields}

        errors: dict[str, list[str]] = {}

        # Unknown keys provided
        for key in self.result.keys():
            if key not in field_by_key:
                errors.setdefault(key, []).append("Unknown field key for this form.")

        # Missing required keys
        for f in fields:
            if f.required:
                if f.key not in self.result or f._is_blank(self.result.get(f.key)):
                    errors.setdefault(f.key, []).append("This field is required.")

        # Validate values for known keys
        for key, value in self.result.items():
            f = field_by_key.get(key)
            if not f:
                continue
            try:
                f.validate_value(value)
            except ValidationError as e:
                # e.messages is a list
                for msg in e.messages:
                    errors.setdefault(key, []).append(msg)

        if errors:
            raise ValidationError({"result": errors})

    def save(self, *args, **kwargs):
        # Enforce validation on every save (including admin / API)
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"Response({self.form.slug}, donor_id={self.donor_id}, id={self.id})"
