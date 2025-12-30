from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from crispy_forms.layout import Layout, Field, HTML
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout

from unfold.widgets import (
    UnfoldAdminTextInputWidget,
    UnfoldAdminDateWidget,
    UnfoldAdminSplitDateTimeWidget,
    UnfoldAdminSelectWidget,
    UnfoldAdminSelectMultipleWidget,
    UnfoldBooleanWidget,
)


def _clean_choices(value):
    if value in (None, ""):
        return []
    if not isinstance(value, str):
        raise ValidationError(_("Choices must be a comma-separated string."))
    items = [v.strip() for v in value.split(",") if v.strip()]
    if not items:
        raise ValidationError(_("Choices string is empty."))
    return [(v, v) for v in items]


EXPECTED_TYPE_LABELS = {
    "text": "Text",
    "integer": "Integer",
    "decimal": "Decimal number",
    "boolean": "Yes / No",
    "date": "Date (YYYY-MM-DD)",
    "datetime": "Date & time",
    "choice": "Single choice",
    "multichoice": "Multiple choice",
}


def enrich_help_text(original: str, field_type: str) -> str:
    label = EXPECTED_TYPE_LABELS.get(field_type)
    if not label:
        return original or ""
    return f"{original} | {label}" if original else f"Expected type: {label}"


def build_django_form_class(form_obj, assignment=None, *, page=1, page_size=5) -> forms.Form:
    declared = {}
    field_order = []

    qs = form_obj.fields.all().order_by("order", "id")
    start = (page - 1) * page_size
    end = start + page_size
    page_fields = qs[start:end]

    for page_field in page_fields:
        params = {
            "label": page_field.label,
            "help_text": enrich_help_text(page_field.help_text or "", page_field.field_type),
            "required": bool(page_field.required),
        }

        field_type = page_field.field_type
        if field_type == "text":
            field = forms.CharField(**params, widget=UnfoldAdminTextInputWidget())
        elif field_type == "integer":
            field = forms.IntegerField(**params, widget=UnfoldAdminTextInputWidget())
        elif field_type == "decimal":
            field = forms.DecimalField(
                max_digits=18,
                decimal_places=6,
                **params,
                widget=UnfoldAdminTextInputWidget(),
            )
        elif field_type == "boolean":
            field = forms.BooleanField(
                required=False,
                label=page_field.label,
                help_text=params["help_text"],
                widget=UnfoldBooleanWidget(),
            )
        elif field_type == "date":
            field = forms.DateField(**params, widget=UnfoldAdminDateWidget())
        elif field_type == "datetime":
            field = forms.SplitDateTimeField(**params, widget=UnfoldAdminSplitDateTimeWidget())
        elif field_type == "choice":
            choices = _clean_choices(page_field.choices)
            field = forms.ChoiceField(
                **params,
                choices=choices,
                widget=UnfoldAdminSelectWidget(choices=choices),
            )
        elif field_type == "multichoice":
            choices = _clean_choices(page_field.choices)
            field = forms.MultipleChoiceField(
                **params,
                choices=choices,
                widget=UnfoldAdminSelectMultipleWidget(choices=choices),
            )
        else:
            raise ValueError(f"Unknown field_type: {field_type}")

        declared[page_field.key] = field
        field_order.append(page_field.key)

    DynamicForm = type(f"DynamicForm_{form_obj.pk}", (forms.Form,), declared)

    def __init__(self, *args, **kwargs):
        super(DynamicForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.template_pack = "unfold_crispy"
        self.helper.form_method = "post"
        self.helper.form_tag = False

        hr = HTML('<hr class="my-6" />')
        layout_items = []

        for i, name in enumerate(field_order):
            layout_items.append(Field(name))
            if i != len(field_order) - 1:
                layout_items.append(hr)

        self.helper.layout = Layout(*layout_items)

    DynamicForm.__init__ = __init__
    DynamicForm.form_obj = form_obj
    DynamicForm.assignment = assignment

    return DynamicForm
