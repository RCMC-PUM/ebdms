from __future__ import annotations

from typing import Any

from django import forms
from django.urls import path, reverse
from django.utils.html import format_html
from django.contrib import admin, messages
from django.http import HttpRequest, HttpResponse
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render

from unfold.admin import ModelAdmin, StackedInline

from .models import Form, FormField, Response
from biobank.models import Donor


# ---------- Inline editor for form fields ----------
class FormFieldInline(StackedInline):
    model = FormField
    extra = 0
    fields = (
        "order",
        "key",
        "label",
        "field_type",
        "required",
        "help_text",
        "choices",
        "use_min_length",
        "min_length",
        "use_max_length",
        "max_length",
        "use_min_value",
        "min_value",
        "use_max_value",
        "max_value",
        "use_regex",
        "regex_pattern",
        "regex_message",
        "regex_flags",
        "use_email_validator",
        "use_url_validator",
        "use_slug_validator",
        "use_unicode_slug_validator",
        "use_file_extension_validator",
        "allowed_extensions",
    )
    ordering = ("order", "id")


# ---------- Dynamic form builder ----------
class DynamicResponseAdminForm(forms.Form):
    """
    Builds fields at runtime from FormField rows.
    Adds Unfold-friendly widget classes so they look like native Unfold forms.
    """

    donor = forms.ModelChoiceField(
        queryset=Donor.objects.all(),
        required=True,
        help_text="Select the donor submitting this response.",
    )

    def __init__(self, *args, form_obj: Form, **kwargs):
        self.form_obj = form_obj
        super().__init__(*args, **kwargs)

        # Style donor field widget
        self._apply_unfold_widget_classes(self.fields["donor"])

        # Build dynamic fields
        for ff in self.form_obj.fields.all().order_by("order", "id"):
            f = self._build_django_field(ff)
            self.fields[ff.key] = f

    # ---- Unfold widget styling helpers ----
    def _apply_unfold_widget_classes(self, field: forms.Field) -> None:
        """
        Unfold is Tailwind-based; these classes blend well with Unfold default UI.
        If your Unfold config uses different classes, this still looks consistent.
        """
        w = field.widget
        base = "w-full"

        # Inputs
        if isinstance(
            w,
            (
                forms.TextInput,
                forms.EmailInput,
                forms.URLInput,
                forms.NumberInput,
                forms.DateInput,
                forms.DateTimeInput,
                forms.Textarea,
                forms.Select,
                forms.SelectMultiple,
            ),
        ):
            w.attrs.setdefault(
                "class",
                " ".join(
                    [
                        base,
                        "rounded-lg",
                        "border",
                        "border-gray-200",
                        "bg-white",
                        "px-3",
                        "py-2",
                        "text-sm",
                        "shadow-sm",
                        "focus:outline-none",
                        "focus:ring-2",
                        "focus:ring-primary-500",
                        "focus:border-primary-500",
                        "dark:bg-gray-900",
                        "dark:border-gray-700",
                    ]
                ),
            )

        # Checkbox
        if isinstance(w, forms.CheckboxInput):
            w.attrs.setdefault(
                "class",
                "h-4 w-4 rounded border-gray-300 text-primary-600 focus:ring-primary-500 dark:border-gray-700",
            )

    def _apply_input_type_defaults(self, field: forms.Field, ff: FormField) -> None:
        # Provide nicer HTML5 input types
        if ff.field_type == FormField.FieldType.INTEGER:
            field.widget = forms.NumberInput()
        elif ff.field_type == FormField.FieldType.DECIMAL:
            field.widget = forms.NumberInput(attrs={"step": "any"})
        elif ff.field_type == FormField.FieldType.DATE:
            field.widget = forms.DateInput(attrs={"type": "date"})
        elif ff.field_type == FormField.FieldType.DATETIME:
            field.widget = forms.DateTimeInput(attrs={"type": "datetime-local"})

    # ---- dynamic field creation ----
    def _build_django_field(self, ff: FormField) -> forms.Field:
        required = bool(ff.required)
        help_text = ff.help_text or ""

        def normalize_choices(raw: Any) -> list[tuple[str, str]]:
            out: list[tuple[str, str]] = []
            if not raw or not isinstance(raw, list):
                return out
            for item in raw:
                if isinstance(item, dict):
                    val = item.get("value")
                    lab = item.get("label", val)
                    out.append((str(val), str(lab)))
                else:
                    out.append((str(item), str(item)))
            return out

        if ff.field_type == FormField.FieldType.TEXT:
            field: forms.Field = forms.CharField(required=required, help_text=help_text)

        elif ff.field_type == FormField.FieldType.INTEGER:
            field = forms.IntegerField(required=required, help_text=help_text)

        elif ff.field_type == FormField.FieldType.DECIMAL:
            field = forms.DecimalField(required=required, help_text=help_text)

        elif ff.field_type == FormField.FieldType.BOOLEAN:
            # checkbox
            field = forms.BooleanField(required=False, help_text=help_text)

        elif ff.field_type == FormField.FieldType.EMAIL:
            field = forms.EmailField(required=required, help_text=help_text)

        elif ff.field_type == FormField.FieldType.URL:
            field = forms.URLField(required=required, help_text=help_text)

        elif ff.field_type == FormField.FieldType.DATE:
            field = forms.DateField(required=required, help_text=help_text)

        elif ff.field_type == FormField.FieldType.DATETIME:
            field = forms.DateTimeField(required=required, help_text=help_text)

        elif ff.field_type == FormField.FieldType.CHOICE:
            choices = normalize_choices(ff.choices)
            field = forms.ChoiceField(required=required, help_text=help_text, choices=choices)

        elif ff.field_type == FormField.FieldType.MULTICHOICE:
            choices = normalize_choices(ff.choices)
            field = forms.MultipleChoiceField(required=required, help_text=help_text, choices=choices)

        elif ff.field_type == FormField.FieldType.FILE:
            # JSON storage - keep as string identifier
            field = forms.CharField(
                required=required,
                help_text=help_text or "Enter file name/path or identifier (stored in JSON).",
            )

        else:
            field = forms.CharField(required=required, help_text=help_text)

        field.label = ff.label

        # Improve widgets (date/datetime/number)
        self._apply_input_type_defaults(field, ff)
        self._apply_unfold_widget_classes(field)

        # Apply your FormField.validate_value() at the field level too
        def _validator(value: Any) -> None:
            ff.validate_value(value)

        field.validators.append(_validator)
        return field

    def to_result_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for ff in self.form_obj.fields.all().order_by("order", "id"):
            value = self.cleaned_data.get(ff.key)

            if value is None:
                result[ff.key] = None
                continue

            if ff.field_type == FormField.FieldType.DATE:
                result[ff.key] = value.isoformat()
            elif ff.field_type == FormField.FieldType.DATETIME:
                result[ff.key] = value.isoformat()
            elif ff.field_type == FormField.FieldType.DECIMAL:
                result[ff.key] = str(value)  # preserve precision
            else:
                result[ff.key] = value

        return result


# ---------- Admin registrations ----------
@admin.register(Response)
class ResponseAdmin(ModelAdmin):
    list_display = ("id", "form", "donor", "created_at")
    list_filter = ("form", "created_at")
    search_fields = ("form__name", "donor__id")


@admin.register(Form)
class FormAdmin(ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at", "updated_at", "fill_form_link")
    search_fields = ("name", "slug")
    list_filter = ("is_active", "created_at")

    inlines = [FormFieldInline]

    def fill_form_link(self, obj: Form) -> str:
        url = reverse("admin:ehr_form_fill", args=[obj.pk])
        # Unfold button classes
        return format_html('<a class="btn btn-outline-secondary" href="{}">Fill form</a>', url)

    fill_form_link.short_description = "Fill"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<path:object_id>/fill/",
                self.admin_site.admin_view(self.fill_view),
                name="ehr_form_fill",
            ),
        ]
        return custom + urls

    def fill_view(self, request: HttpRequest, object_id: str, *args, **kwargs) -> HttpResponse:
        form_obj = get_object_or_404(Form, pk=object_id)

        if not form_obj.is_active:
            messages.warning(
                request,
                "This form is inactive; you can still fill it, but consider re-activating it.",
            )

        if request.method == "POST":
            dyn_form = DynamicResponseAdminForm(request.POST, form_obj=form_obj)
            if dyn_form.is_valid():
                donor = dyn_form.cleaned_data["donor"]
                result = dyn_form.to_result_dict()
                response = Response(donor=donor, form=form_obj, result=result)

                try:
                    response.full_clean()
                    response.save()
                except ValidationError as e:
                    dyn_form.add_error(None, "Validation failed while saving Response.")
                    if hasattr(e, "message_dict"):
                        for k, v in e.message_dict.items():
                            dyn_form.add_error(None, f"{k}: {v}")
                    else:
                        dyn_form.add_error(None, str(e))
                else:
                    messages.success(request, "Response saved.")
                    return redirect(reverse("admin:ehr_response_change", args=[response.pk]))
        else:
            dyn_form = DynamicResponseAdminForm(form_obj=form_obj)

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "form_obj": form_obj,
            "dynamic_form": dyn_form,
            "title": f"Fill form: {form_obj.name}",
            "media": self.media + dyn_form.media,
        }
        return render(request, "admin/forms/form/fill_ehr.html", context)


@admin.register(FormField)
class FormFieldAdmin(ModelAdmin):
    list_display = ("form", "order", "key", "label", "field_type", "required")
    list_filter = ("form", "field_type", "required")
    search_fields = ("form__name", "key", "label")
    ordering = ("form", "order", "id")
