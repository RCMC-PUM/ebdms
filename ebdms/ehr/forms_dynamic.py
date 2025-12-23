from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

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
        raise ValidationError(_("Choices must be a comma-separated string e.g., 'male,female,other'."))
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
    type_label = EXPECTED_TYPE_LABELS.get(field_type)
    if not type_label:
        return original or ""

    if original:
        return f"{original} | {type_label}"
    return f"Expected type: {type_label}"


def build_django_form_class(form_obj, assignment=None):
    declared = {}
    field_order = []

    for ff in form_obj.fields.all().order_by("order", "id"):
        params = {
            "label": ff.label,
            "help_text": enrich_help_text(ff.help_text or "", ff.field_type),
            "required": bool(ff.required),
        }

        ft = ff.field_type

        if ft == "text":
            field = forms.CharField(**params, widget=UnfoldAdminTextInputWidget())

        elif ft == "integer":
            field = forms.IntegerField(**params, widget=UnfoldAdminTextInputWidget())

        elif ft == "decimal":
            field = forms.DecimalField(
                max_digits=18,
                decimal_places=6,
                **params,
                widget=UnfoldAdminTextInputWidget(),
            )

        elif ft == "boolean":
            field = forms.BooleanField(
                required=False,
                label=ff.label,
                help_text=params["help_text"],
                widget=UnfoldBooleanWidget(),
            )

        elif ft == "date":
            field = forms.DateField(**params, widget=UnfoldAdminDateWidget())

        elif ft == "datetime":
            field = forms.SplitDateTimeField(**params, widget=UnfoldAdminSplitDateTimeWidget())

        elif ft == "choice":
            choices = _clean_choices(ff.choices)
            field = forms.ChoiceField(
                **params,
                choices=choices,
                widget=UnfoldAdminSelectWidget(choices=choices),
            )

        elif ft == "multichoice":
            choices = _clean_choices(ff.choices)
            field = forms.MultipleChoiceField(
                **params,
                choices=choices,
                widget=UnfoldAdminSelectMultipleWidget(choices=choices),
            )

        else:
            raise ValueError(f"Unknown field_type: {ft}")

        declared[ff.key] = field
        field_order.append(ff.key)

    DynamicForm = type(f"DynamicForm_{form_obj.pk}", (forms.Form,), declared)

    def __init__(self, *args, **kwargs):
        super(DynamicForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_tag = False

        # IMPORTANT: keep buttons INSIDE layout, not floating via helper.add_input
        # This avoids the “submit on the far right of the screen” look.
        self.helper.layout = Layout(*field_order)

    DynamicForm.__init__ = __init__
    DynamicForm.form_obj = form_obj
    DynamicForm.assignment = assignment

    return DynamicForm
